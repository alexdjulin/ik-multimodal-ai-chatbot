#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: app.py
Description: Main application file to run the Flask web server and chat with the avatar.
Author: @alexdjulin
Date: 2024-11-04
"""

# Standard library imports
import os
import sys
from pathlib import Path
from threading import Thread

# Third-party imports
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO
from pydub import AudioSegment

# First-party imports
import helpers
from config_loader import get_config
from ai_librarian import AiLibrarian

avatar = AiLibrarian()
avatar.create_worker_agent()
# get config dict
config = get_config()

# load names and colors
USER_NAME = config['user_name']
CHATBOT_NAME = config['chatbot_name']

# initialize Flask app, SocketIO and chat_history
app = Flask(__name__)
socketio = SocketIO(app)
chat_history = []
TOOL_CALLS_LOG = Path(__file__).parent / config['log_tool_file']


@app.route("/", methods=["GET", "POST"])
def index():
    """Main endpoint to render the chat interface and handle user input.

    Returns:
        render_template: Rendered HTML template with chat history.
    """
    if request.method == "POST":
        user_message = request.form["user_input"]

        # print user message to console
        if user_message:
            print(f"\n{USER_NAME}: {user_message.capitalize()}")

        # CHAT HIDDEN COMMANDS FOR DEBUGGING
        # exit program if user types 'exit'
        if user_message.lower() == '#exit':
            print("Exiting program.")
            sys.exit()
        # clear chat history if user types 'clear'
        elif user_message.lower() == '#clear':
            chat_history.clear()
            socketio.emit("update_chat", {"chat_history": chat_history})
            return redirect(url_for("index"))
        # ignore empty inputs
        if not user_message.strip():
            return redirect(url_for("index"))

        # add user message and chatbot temporary message
        chat_history.append({"sender": config['user_name'], "message": user_message})
        chat_history.append({"sender": config['chatbot_name'],
                             "message": config['thinking_message']})
        socketio.emit("update_chat", {"chat_history": chat_history})

        # process answer on a background thread
        thread = Thread(target=process_audio_answer, args=(user_message,))
        thread.start()

        return redirect(url_for("index"))

    return render_template("index.html", chat_history=chat_history)


@app.route("/process_audio", methods=["POST"])
def process_audio_input():
    """Endpoint to handle audio upload and processing.

    Returns:
        jsonify: JSON response with processing status.
    """
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    webm_path = config['user_webm_filepath']
    audio_file.save(webm_path)

    # convert audio file to wav format
    wav_path = config['user_wav_filepath']
    wav_file = AudioSegment.from_file(webm_path, format="webm")
    wav_file.export(wav_path, format="wav")

    # Start the transcription thread
    thread = Thread(target=process_audio_message, args=(wav_path,))
    thread.start()

    return jsonify({"status": "Processing started"}), 200


def process_audio_message(audio_path: str) -> None:
    """Thread 1: Transcribe audio and update chatbox with user message.

    Args:
        audio_path (str): Path to the audio file.
    """

    # transcribe audio file into a text message
    user_message = helpers.transcribe_audio_file(audio_path)
    if user_message:
        print(f"\n{USER_NAME}: {user_message.capitalize()}")

    # delete temp audio files
    for file in [config['user_webm_filepath'], config['user_wav_filepath']]:
        if os.path.exists(file):
            os.remove(file)

    if user_message:
        # update chat history with user message and add temporary message from chatbot
        chat_history.append({"sender": config['user_name'], "message": user_message})
        chat_history.append({"sender": config['chatbot_name'],
                             "message": config['thinking_message']})
        socketio.emit("update_chat", {"chat_history": chat_history})
        # Start the agent response process in a new thread
        thread = Thread(target=process_audio_answer, args=(user_message,))
        thread.start()


def process_audio_answer(user_message: str) -> None:
    """Thread 2: Send user text to agent, generate response, and update chatbox.

    Args:
        user_message (str): User message to send to the agent.
    """

    chatbot_answer = avatar.generate_model_answer(user_message)

    # print answer when not in verbose mode
    if not config['agent_verbose']:
        print(f"{CHATBOT_NAME}: {chatbot_answer.capitalize()}")

    # Generate and play audio for Alice's response
    if chatbot_answer:
        audio_path = helpers.generate_audio_from_text(chatbot_answer)
        # Update chat history with chatbot answer
        if chat_history and chat_history[-1]["message"] == config['thinking_message']:
            chat_history.pop()
        chat_history.append({"sender": config['chatbot_name'], "message": chatbot_answer})
        socketio.emit("update_chat", {"chat_history": chat_history})
        # Send the chatbot audio response to the client
        if audio_path:
            socketio.emit("new_audio_response", {"audio_path": audio_path})

    # Empty tool call log to remove logo from UI
    if config.get('log_tool_call', False) and os.path.isfile(TOOL_CALLS_LOG):
        with open(TOOL_CALLS_LOG, "w"):
            pass


@app.route('/delete_audio', methods=['POST'])
def delete_audio():
    """Endpoint to delete audio file.

    Returns:
        jsonify: JSON response with deletion status.
    """
    audio_path = request.json.get('audio_path')
    if audio_path and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
            return jsonify({"status": "success", "message": "Audio file deleted."})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to delete audio file: {e}"})
    return jsonify({"status": "error", "message": "Invalid or missing audio path."}), 400


@app.route('/log_tool_call', methods=['GET'])
def log_toll_call():
    """Endpoint to display the current tool call logged to file on the UI.

    Returns:
        jsonify: JSON tool call.
    """

    tool_call = ""
    img_base_url = config.get('image_base_url', '/static/tool_imgs/')

    # Define image mapping for each tool call
    tool_call_imgs = {
        "search_wikipedia": "tool_wikipedia.png",
        "search_database_for_book_information": "tool_chroma.png",
        "search_database_for_book_reviews": "tool_chroma.png",
        "YoutubeSearchTool": "tool_youtube.png",
        "retrieve_youtube_transcript_from_url": "tool_youtube.png",
        "get_information_about_yourself": "tool_alice.png",
    }

    if config.get('log_tool_call', False):
        try:
            with open(TOOL_CALLS_LOG, "r") as file:
                tool_call = file.read().strip()
        except FileNotFoundError:
            tool_call = ""

    # Map tool call to image filename
    img_filename = tool_call_imgs.get(tool_call, "")
    image_path = img_base_url + img_filename if img_filename else ""

    return jsonify({"image_path": image_path})


if __name__ == "__main__":
    socketio.run(app, debug=config['debug_mode'])
