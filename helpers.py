#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: helpers.py
Description: Helper methods used by the class to perform atomic tasks.
Example: SST, TTS, CSV read/write, LLM completion, etc.
Author: @alexdjulin
Date: 2024-11-04
"""

import os
import asyncio
from pathlib import Path
import csv
from datetime import datetime
from textwrap import dedent
# TTS
import edge_tts
# STT
import speech_recognition as sr
# config loader
from config_loader import get_config
# logger
from logger import get_logger
LOG = get_logger(Path(__file__).stem)
# get config dict
config = get_config()


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
        with open(csvfile, mode='a', newline='', encoding='utf-8') as file:
            csv_writer = csv.writer(file, quoting=csv.QUOTE_ALL, doublequote=True)
            # remove tabs, line breaks and extra spaces
            safe_strings = [format_string(s) for s in strings]
            if config['add_timestamp']:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                safe_strings = [timestamp] + safe_strings
            csv_writer.writerow(safe_strings)

    except Exception as e:
        LOG.error("Error writing to CSV file: %s", e)
        return False

    return True


def log_tool_call(tool_name: str) -> None:
    ''' Logs the name of the tool that was called to a file for visual feedback in the UI.

    Args:
        tool_name (str): Name of the tool that was called
    '''

    try:
        # create folder if it doesn't exist
        log_dir = Path(__file__).parent
        log_file = log_dir / Path(config['log_filepath'])
        os.makedirs(log_file.parent, exist_ok=True)

        with open(config['log_tool_file'], "w", encoding='utf-8') as file:
            file.write(tool_name)

    except (OSError, PermissionError, FileNotFoundError) as e:
        LOG.error("Error writing to log file: %s", e)


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
        LOG.debug("Error connecting to Google API: %s", e)

    except Exception as e:
        LOG.debug("Error transcribing audio: %s", e)


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
        LOG.error("Error generating audio: %s.", e)
        return

    return audio_filepath
