#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: ai_chatbot.py
Description: Defines the AiChatbot class to chat with the avatar using the command line interface.
Author: @alexdjulin
Date: 2024-07-25
"""

import os
from pathlib import Path
from time import sleep
import helpers
import models
import keyboard
import threading
from langchain_core.messages import HumanMessage, AIMessage

# import config
from config_loader import get_config
config = get_config()

# define logger
from logger import get_logger
LOG = get_logger(Path(__file__).stem)

# load user and chatbot names
USER_NAME = config['user_name']
CHATBOT_NAME = config['chatbot_name']

# load terminal colors
from terminal_colors import CYAN, MAGENTA, GREY, RESET, CLEAR

# load user and chatbot colors dynamically from config
from importlib import import_module
terminal_colors_md = import_module('terminal_colors')
USER_CLR = getattr(terminal_colors_md, config['user_color'], CYAN)
AI_CLR = getattr(terminal_colors_md, config['ai_color'], MAGENTA)

# setup csv file to store chat history
CHAT_HISTORY_CSV = Path(__file__).parent / Path(config['chat_history'])
os.makedirs(os.path.dirname(CHAT_HISTORY_CSV), exist_ok=True)
if os.path.exists(CHAT_HISTORY_CSV) and config['clear_history']:
    with open(CHAT_HISTORY_CSV, 'w'):
        pass


class AiLibrarian:
    '''
    This class defines an AI librarian to converse with.
    '''

    def __init__(self) -> None:
        ''' Create class instance '''

        # flags
        self.recording = False
        self.exit_chat = {'value': False}  # use a dict to pass flag by reference to helpers

        # thread object to handle chat tasks
        self.chat_thread = None

        # chat settings (can be overridden by command line arguments)
        self.input_method = config['input_method']
        self.language = config['chat_language']

        # langchain worker agent
        self.worker = None

    def create_worker_agent(self) -> None:
        '''
        Create langchain agent
        '''

        self.worker = models.llm_agent()

    def chat_with_avatar(self, input_method: str = None, language: str = None) -> None:
        '''Entry point to chat with the avatar.

        Args:
            input_method (str): overrides input method defined in config if passed to main as argument
            language (str): overrides chat language defined in config

        Raises:
            ValueError: if worker is not defined before starting chat
        '''

        if self.worker is None:
            LOG.error('self.worker is None. Call create_worker_agent before chat_with_avatar.')
            raise ValueError('Worker not defined. Please create a worker agent before starting chat.')

        # override input method if provided and checked if valid
        if input_method:
            self.input_method = input_method

        valid_input_methods = {'text', 'voice', 'voice_k'}
        if self.input_method not in valid_input_methods:
            LOG.error(f"Invalid input method {self.input_method}. Chose from {valid_input_methods}")
            raise ValueError(f'Invalid input method. Chose from: {valid_input_methods}')

        LOG.debug(f'Input method: {self.input_method}')

        # override language if provided and checked if valid
        if language:
            self.language = language

        valid_languages = list(config['edgetts_voices'].keys())
        if self.language not in valid_languages:
            LOG.error(f"Invalid language '{self.language}'. Chose from {valid_languages}")
            raise ValueError(f"Invalid language '{self.language}'. Chose from {valid_languages}")

        LOG.debug(f'Language: {self.language}')

        # define keyboard event to exit chat at any time
        keyboard.on_press_key("esc", self.on_esc_pressed)

        print(f'\n{GREY}Starting chat, please wait...{RESET}')
        helpers.write_to_csv(CHAT_HISTORY_CSV, 'NEW CHAT')

        if self.exit_chat['value']:
            # exit program before starting chat if esc was pressed during setup
            exit()

        print(f'\n{GREY}# CHAT STARTED #{GREY}')

        # prompt for a new user input
        print(f'\n{USER_CLR}{USER_NAME}:{RESET}')

        if self.input_method == 'text':
            while not self.exit_chat['value']:
                # get user message
                new_message = input()
                if new_message.strip() == '':
                    # skip empty message or only spaces
                    continue
                if new_message in {'quit', 'exit'}:
                    # raise exit flag and exit loop on keywords
                    self.exit_chat['value'] = True
                    break
                # send message to chatGPT and get answer on separate thread
                self.chat_thread = threading.Thread(target=self.generate_model_answer, args=[new_message])
                self.chat_thread.start()

        elif self.input_method == 'voice_k':
            # define keyboard event to trigger audio inpout
            keyboard.on_press_key("space", self.on_space_pressed)

            while not self.exit_chat['value']:
                sleep(1)  # wait 1 second before checking again

        else:  # self.input_method == 'voice'
            # use direct chat input
            while not self.exit_chat['value']:
                if self.recording is False:
                    self.record_message()
                sleep(1)  # wait 1 second before checking again

        # stop keyboard listener
        keyboard.unhook_all()

        # make sure temp files are deleted
        if os.path.exists(config['temp_audio_filepath']):
            os.remove(config['temp_audio_filepath'])

        print(f'\n{GREY}# CHAT ENDED #{GREY}')

    def on_space_pressed(self, e) -> None:
        ''' When space is pressed, start a thread to record your voice message '''
        if e.event_type == keyboard.KEY_DOWN and self.recording is False:
            self.chat_thread = threading.Thread(target=self.record_message)
            self.chat_thread.start()

    def on_esc_pressed(self, e) -> None:
        ''' When esc is pressed, raise exit_flag to terminate chat and any chat thread running '''
        if e.event_type == keyboard.KEY_DOWN and not self.exit_chat['value']:
            LOG.debug('Raising exit flag to terminate chat')
            self.exit_chat['value'] = True
            message = 'Ending chat, PRESS ENTER to close' if self.input_method == 'text' else 'Ending chat, please wait...'
            print(f'{CLEAR}{GREY}{message}{RESET}', flush=True)

    def record_message(self) -> None:
        ''' Record voice and transcribe message '''

        self.recording = True

        new_message = helpers.record_audio_message(self.exit_chat, input_method=self.input_method, language=self.language)

        # Process new message on success or ask user to try again if no message was recorded
        if new_message:
            self.generate_model_answer(new_message)
        else:
            self.recording = False

    def generate_model_answer(self, user_message: str) -> None:
        '''Send new message and get answer from the LLM.

        Args:
            message (str): message to send to the LLM
        '''

        # print message in speech mode
        if not self.input_method == 'text':
            print(f'{CLEAR}{USER_CLR}{user_message.capitalize()}{RESET}')

        # add message to prompt and chat history
        helpers.write_to_csv(CHAT_HISTORY_CSV, USER_NAME, user_message)
        LOG.debug(f'Human Message: {user_message}')

        # print avatar feedback
        print(f'\n{CLEAR}{AI_CLR}{CHATBOT_NAME}:{RESET}')
        print(f'{CLEAR}{GREY}(generate){RESET}', end=' ', flush=True)

        # invoke langchain worker and get answer
        answer = self.worker.invoke({"input": user_message})

        # extract answer from dict when using an agent
        if isinstance(answer, dict):
            if 'output' in answer:
                answer = answer['output']

        # remove any unwanted characters
        # ai_message = re.sub(r'[*|/|\\]', '', answer)
        ai_message = answer

        helpers.write_to_csv(CHAT_HISTORY_CSV, CHATBOT_NAME, ai_message)
        LOG.debug(f'AI Message: {ai_message}')

        if not self.input_method == 'text':
            # generate tts
            print(f'{CLEAR}{GREY}(transcribe){RESET}', end=' ', flush=True)
            helpers.generate_tts(text=ai_message, language=self.language)

        else:
            # print answer
            print(f'{CLEAR}{AI_CLR}{ai_message}{RESET}')

        # prompt for a new chat
        self.recording = False
        print(f'\n{USER_CLR}{USER_NAME}:{RESET}')
