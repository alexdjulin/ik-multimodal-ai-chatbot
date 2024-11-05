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


def transcribe_audio_file(audio_file_path: str, language: str = None) -> str | None:
    ''' Transcribe an audio file and return text transcription.

    Args:
        audio_file_path (str): Path to the audio file to be transcribed.
        language (str): Language to use for transcription. Default to None.

    Return:
        (str | None): Transcribed text from the audio file.

    Raises:
        RequestError: If there is an error connecting to the Google API.
        Exception: If there is an error transcribing the audio.
    '''
    recognizer = sr.Recognizer()
    if language is None:
        language = config['chat_language']

    try:
        # Load the audio file
        with sr.AudioFile(audio_file_path) as source:
            LOG.debug("loading and processing audio")
            audio = recognizer.record(source)

        # Transcribe the audio file
        LOG.debug("transcribing audio to text")
        text = recognizer.recognize_google(audio, language=language)

        if not text:
            raise sr.UnknownValueError

        return text.capitalize()

    except sr.RequestError as e:
        LOG.debug(f"Error connecting to Google API: {e}")

    except Exception as e:
        LOG.debug(f"Error transcribing audio: {e}")


def generate_audio_from_text(text: str, language: str = None) -> str:
    ''' Generates an audio file from an input text and returns its path.

    Args:
        text (str): text to generate audio from
        language (str): the language to use for the voice. Default to None.

    Return:
        (str): Path to the generated audio file.

    Raises:
        Exception: if error generating audio from text.
    '''

    print('TRANSCRIBING AUDIO')
    if language is None:
        language = config['chat_language']

    voice = config['edgetts_voices'][language]
    audio_filepath = config['chatbot_audio_filepath']
    os.makedirs(Path(audio_filepath).parent, exist_ok=True)

    async def text_to_audio() -> None:
        """ Generate speech from text and save it to a file """
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=config['tts_rate'],
            volume=config['tts_volume'],
            pitch=config['tts_pitch']
        )

        await communicate.save(audio_filepath)

    # generate audio data
    try:
        asyncio.run(text_to_audio())

    except Exception as e:
        LOG.error(f"Error generating audio: {e}.")
        return

    return audio_filepath
