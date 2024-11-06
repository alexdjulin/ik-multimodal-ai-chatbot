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
import helpers
import models

# import config
from config_loader import get_config

# define logger
from logger import get_logger
LOG = get_logger(Path(__file__).stem)

# get config dict
config = get_config()

# setup csv file to store chat history
CHAT_HISTORY_CSV = Path(__file__).parent / Path(config['chat_history'])
os.makedirs(os.path.dirname(CHAT_HISTORY_CSV), exist_ok=True)
if os.path.exists(CHAT_HISTORY_CSV) and config['clear_history']:
    with open(CHAT_HISTORY_CSV, 'w'):
        pass

# load names
USER_NAME = config['user_name']
CHATBOT_NAME = config['chatbot_name']


class AiLibrarian:
    '''
    This class defines an AI librarian to converse with using the web interface.
    '''

    def __init__(self) -> None:
        ''' Create class instance '''

        # langchain agent
        self.agent = None

    def create_worker_agent(self) -> None:
        '''
        Create langchain agent
        '''

        self.agent = models.llm_agent()

    def generate_model_answer(self, user_message: str) -> None:
        '''Send new message and get answer from the LLM, stores it in class variable.

        Args:
            message (str): message to send to the LLM
        '''

        # add message to prompt and chat history
        helpers.write_to_csv(CHAT_HISTORY_CSV, USER_NAME, user_message)
        LOG.debug(f'{USER_NAME}: {user_message}')

        # invoke langchain worker and get answer
        answer = self.agent.invoke({"input": user_message})

        # extract answer from dict when using an agent
        if isinstance(answer, dict):
            if 'output' in answer:
                answer = answer['output']

        # write answer to chat history
        helpers.write_to_csv(CHAT_HISTORY_CSV, CHATBOT_NAME, answer)
        LOG.debug(f'{CHATBOT_NAME}: {answer}')

        # store answer to class variable
        return answer
