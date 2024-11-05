# load api-keys to environment
from dotenv import load_dotenv
load_dotenv()
# import flask and socketio
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO
from threading import Thread
# config loader
from config_loader import load_config
config = load_config('config.yaml')
# create avatar instance
from ai_librarian_app import AiLibrarian
avatar = AiLibrarian()
avatar.create_worker_agent()
# magic strings
USER_NAME = config['user_name']
CHATBOT_NAME = config['chatbot_name']
TEMP_MESSAGE = '...thinking...'


# initialize Flask app, SocketIO and chat_history
app = Flask(__name__)
socketio = SocketIO(app)
chat_history = []


def process_answer(user_message):
    chatbot_answer = avatar.generate_model_answer(user_message)

    # Remove temporary message
    if chat_history and chat_history[-1]["message"] == TEMP_MESSAGE:
        chat_history.pop()

    # Add chatbot answer to chat history
    if chatbot_answer:
        chat_history.append({"sender": CHATBOT_NAME, "message": chatbot_answer})

    # Send the updated chat history to the client
    socketio.emit("update_chat", {"chat_history": chat_history})


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_message = request.form["user_input"]

        # ignore empty inputs
        if not user_message.strip():
            return redirect(url_for("index"))

        chat_history.append({"sender": USER_NAME, "message": user_message})

        # process answer on a background thread
        thread = Thread(target=process_answer, args=(user_message,))
        thread.start()

        # add temporary message from chatbot
        chat_history.append({"sender": CHATBOT_NAME, "message": TEMP_MESSAGE})

        return redirect(url_for("index"))

    return render_template("index.html", chat_history=chat_history)


if __name__ == "__main__":
    socketio.run(app, debug=True)
