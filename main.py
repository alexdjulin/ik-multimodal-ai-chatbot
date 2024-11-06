#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: main.py
Description: Starting point for the AI Librarian defining the command line arguments
and starting a new chat.
Author: @alexdjulin
Date: 2024-11-02
"""

import sys
import argparse
from config_loader import load_config
# load api keys from .env file
from dotenv import load_dotenv
load_dotenv()


# parse command line arguments
parser = argparse.ArgumentParser(description='Chat with an AI chatbot.')
parser.add_argument('--config', '-c', type=str, default='config.yaml', help='Path to configuration file.')
parser.add_argument('--input', '-i', type=str, help='Overrides input method to use: {text, voice, voice_k}.')
parser.add_argument('--language', '-l', type=str, help='Overrides chat language (Example: en-US, fr-FR, de-DE). A matching voice should be defined in edgetts_voice, in the config file.')
args = parser.parse_args()


if __name__ == '__main__':

    # parse arguments
    config_file = args.config
    input_method = args.input
    language = args.language

    # load config file
    load_config(config_file)

    try:
        # Create avatar instance and agent
        from ai_librarian_cmd import AiLibrarian
        avatar = AiLibrarian()
        avatar.create_worker_agent()
        # Initiate chat
        avatar.chat_with_avatar(input_method, language)

    except Exception as e:
        print(f"Error occurred in command line mode: {e}", file=sys.stderr)
        sys.exit(1)
