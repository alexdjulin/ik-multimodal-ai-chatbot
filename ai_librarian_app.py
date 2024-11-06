#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: ai_librarian_app.py
Description: Defines the AiChatbot class to chat with the avatar using the web interface.
Author: @alexdjulin
Date: 2024-11-05
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
    This class defines an AI librarian to converse with using the web interface.
    '''

    def __init__(self) -> None:
        ''' Create class instance '''

        # flags
        self.recording = False

        # thread object to handle chat tasks
        self.chat_thread = None
        self.ai_answer = None

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

    def generate_model_answer(self, user_message: str) -> None:
        '''Send new message and get answer from the LLM, stores it in class variable.

        Args:
            message (str): message to send to the LLM
        '''

        # print user message
        print(f"\n{USER_CLR}{config['user_name']}: {user_message.capitalize()}{RESET}")

        # add message to prompt and chat history
        helpers.write_to_csv(CHAT_HISTORY_CSV, USER_NAME, user_message)
        LOG.debug(f'{USER_NAME}: {user_message}')

        # invoke langchain worker and get answer
        answer = self.worker.invoke({"input": user_message})

        # extract answer from dict when using an agent
        if isinstance(answer, dict):
            if 'output' in answer:
                answer = answer['output']

        # write answer to chat history
        helpers.write_to_csv(CHAT_HISTORY_CSV, CHATBOT_NAME, answer)
        LOG.debug(f'{CHATBOT_NAME}: {answer}')

        # print answer when not in verbose mode
        if not config['agent_verbose']:
            print(f"{AI_CLR}{config['chatbot_name']}: {answer.capitalize()}{RESET}")

        # store answer to class variable
        return answer
