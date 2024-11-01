#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: helpers.py
Description: Helper methods used by the class to perform atomic tasks.
Example: SST, TTS, CSV read/write, LLM completion, etc.
Author: @alexdjulin
Date: 2024-07-25
"""

import os
from pathlib import Path
import sys
import csv
import json
from datetime import datetime
from time import sleep
from textwrap import dedent
# TTS
import edge_tts
import asyncio
# Audio playback
from pydub import AudioSegment
from pydub.playback import play
# STT
import speech_recognition as sr
# langchain
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.docstore.document import Document
from langchain.memory import ConversationBufferWindowMemory
# config loader
from config_loader import get_config
config = get_config()
# logger
from logger import get_logger
LOG = get_logger(Path(__file__).stem)
# terminal colors, chatbot color dynamically loaded from config
from terminal_colors import MAGENTA, GREY, CLEAR, RESET
from importlib import import_module
terminal_colors_md = import_module('terminal_colors')
AI_CLR = getattr(terminal_colors_md, config['ai_color'], MAGENTA)


def format_string(prompt: str) -> str:
    ''' Removes tabs, line breaks and extra spaces from strings. This is useful
    when formatting prompts to send to chatGPT or to save to a csv file

    Args:
        prompt (str): string to format

    Return:
        (str): formatted string
    '''

    # remove tabs and line breaks
    prompt = dedent(prompt).replace('\n', ' ').replace('\t', ' ')

    # remove extra spaces
    while '  ' in prompt:
        prompt = prompt.replace('  ', ' ')

    # remove leading and trailing spaces
    prompt = prompt.strip()

    return prompt


def write_to_csv(csvfile: str, *strings: list) -> bool:
    ''' Adds chat messages to a csv file on a new row.

    Args:
        csvfile (str): path to csv file
        *strings (list): strings to add as columns to csv file

    Return:
        (bool): True if successful, False otherwise

    Raises:
        Exception: if error writing to csv file
    '''

    try:
        with open(csvfile, mode='a', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL, doublequote=True)
            # remove tabs, line breaks and extra spaces
            safe_strings = [format_string(s) for s in strings]
            if config['add_timestamp']:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                safe_strings = [timestamp] + safe_strings
            csv_writer.writerow(safe_strings)

    except Exception as e:
        LOG.error(f"Error writing to CSV file: {e}")
        return False

    return True


def load_prompt_messages(prompt_filepath: str = None) -> list[tuple[str, str]]:
    ''' Loads messages from a jsonl file and returns them as a list of tuples.

    Args:
        prompt_filepath (str): path to jsonl file. Default to None.

    Return:
        (list[tuple[str, str]]): list of tuples with role and content
    '''

    # load prompt file from config if not provided
    if prompt_filepath is None:
        # concatenate current path with prompt file path
        prompt_filepath = os.path.join(Path(__file__).parent, config['prompt_filepath'])

    # check if prompt file exists
    if not os.path.exists(prompt_filepath):
        LOG.error(f"Prompt file not found: {prompt_filepath}")
        return []

    messages = []

    # Open and read the file line by line
    with open(prompt_filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                message = json.loads(line)  # Parse JSON only once
                # Ensure both 'role' and 'content' are present before appending
                if 'role' in message and 'content' in message:
                    messages.append((message['role'], message['content']))
            except json.JSONDecodeError:
                LOG.warning(f"Skipping invalid JSON line: {line.strip()}")
                continue

    return messages


def load_openai() -> ChatOpenAI:
    ''' Loads a gpt model and returns it.

    Return:
        (ChatOpenAI): the gpt model instance
    '''

    model = ChatOpenAI(
        model=config['generative_model'],
        api_key=os.environ['OPENAI_API_KEY'],
        temperature=config['openai_temperature']
    )

    return model


def build_agent(placeholders: list[str] = None) -> AgentExecutor:
    ''' Defines a langchain agent with access to a list of tools to perform a task.

    Args:
        placeholders (list): optional list of placeholder variables added to the prompt

    Return:
        (AgentExecutor): the agent instance
    '''

    # import tools module
    try:
        sys.path.append(os.path.dirname(config['tools_filepath']))
        import tools

    except ImportError as e:
        LOG.error(f"Error importing tools module: {e}. Add a tool-")
        raise

    # load llm
    llm = load_openai()

    # create prompt
    messages = load_prompt_messages()

    # add default placeholders
    messages.append(("placeholder", "{chat_history}"))
    messages.append(("human", "{input}"))
    messages.append(("placeholder", "{agent_scratchpad}"))

    # add custom placeholders
    if placeholders:
        for placeholder in placeholders:
            messages.append(("placeholder", "{" + placeholder + "}"))

    # create prompt
    prompt = ChatPromptTemplate.from_messages(messages)

    # create langchain agent
    agent = create_tool_calling_agent(
        tools=tools.agent_tools,
        llm=llm,
        prompt=prompt
    )

    memory = ConversationBufferWindowMemory(memory_key='chat_history', return_messages=True)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools.agent_tools,
        verbose=config['agent_verbose'],
        handle_parsing_errors=True,
        memory=memory
    )

    return agent_executor


def summarizer(context: str, input: str = None) -> str:
    """Summarize a text using a summarizer model.

    Args:
        context (str): text to summarize
        input (str, optional): input question to orientate the summary. Defaults to None.

    Returns:
        str: summary of the text
    """

    prompt_text = "Write a concise summary of the following text:\n{context}\nto help answer the following question:\n{input}"

    prompt = ChatPromptTemplate.from_messages(
        [("system", prompt_text),]
    )

    llm = ChatOpenAI(temperature=0, model_name=config["summarizer_model"], api_key=os.getenv("OPENAI_API_KEY"))

    chain = create_stuff_documents_chain(llm, prompt)
    document = Document(page_content=context)
    return chain.invoke({"context": [document], "input": input})


def generate_tts(text: str, language: str = None) -> None:
    ''' Generates audio from text using edge_tts API and plays it

    Args:
        text (str): text to generate audio from
        language (str): the language to use for the voice

    Raises:
        Exception: if error generating and playing audio
    '''

    voice = config['edgetts_voices'][language]
    audio_file = config['temp_audio_filepath']
    os.makedirs(Path(audio_file).parent, exist_ok=True)

    async def text_to_audio() -> None:
        """ Generate speech from text and save it to a file """
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=config['tts_rate'],
            volume=config['tts_volume'],
            pitch=config['tts_pitch']
        )

        await communicate.save(audio_file)

    # generate audio data
    try:
        asyncio.run(text_to_audio())

    except Exception as e:
        LOG.error(f"Error generating and playing audio: {e}. Voice deactivated.")
        # print answer and exit
        print(f'{CLEAR}{AI_CLR}{text}')
        return

    # print answer
    print(f'{CLEAR}{AI_CLR}{text}')

    # play and delete audio file
    audio = AudioSegment.from_file(audio_file)
    play(audio)

    # deleve temporary audio file
    os.remove(audio_file)


def record_audio_message(exit_chat: dict, input_method: str, language: str) -> str | None:
    ''' Record voice and return text transcription.

    Args:
        exit_chat (dict): chat exit flag {'value': bool} passed by reference as mutable dicts so it can be modified on keypress and updated here.
        input_method (str): input method to use for transcription
        language (str): language to use for transcription

    Return:
        (str | None): text transcription

    Raises:
        UnknownValueError: if audio could not be transcribed
        RequestError: if error connecting to Google API
    '''

    text = ''
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    try:

        with microphone as source:

            if not exit_chat['value']:
                print(f"{CLEAR}{GREY}(listening){RESET}", end=' ', flush=True)
                audio = recognizer.listen(source, timeout=config['speech_timeout'], phrase_time_limit=config['phrase_time_out'])

            if not exit_chat['value']:
                print(f"{CLEAR}{GREY}(transcribing){RESET}", end=' ', flush=True)
                text = recognizer.recognize_google(audio, language=language)

            if not text:
                raise sr.UnknownValueError

            return text.capitalize()

    except sr.WaitTimeoutError:
        if input_method == 'voice_k':
            print(f"{CLEAR}{GREY}Can't hear you. Please try again.{RESET}", end=' ', flush=True)
        else:
            if not exit_chat['value']:
                # start listening again
                record_audio_message(exit_chat, input_method, language)

    except sr.UnknownValueError:
        if not exit_chat['value']:
            print(f"{CLEAR}{GREY}Can't understand audio. Please try again.{RESET}", end=' ', flush=True)
        sleep(0.5)

    except sr.RequestError:
        if not exit_chat['value']:
            print(f"{CLEAR}{GREY}Error connecting to Google API. Please try again.{RESET}", end=' ', flush=True)
        sleep(0.5)

    return None
