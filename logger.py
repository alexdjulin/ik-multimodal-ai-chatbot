#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: logger.py
Description: Creates a logger instance with the specified log level, format, and file to use in all modules.
Author: @alexdjulin
Date: 2024-07-25
"""

import os
from pathlib import Path
import logging
from config_loader import get_config
config = get_config()

# define a namespace common to all logger instances
NAMESPACE = 'ai_chatbot'
levels = {'NOTSET': 0, 'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40, 'CRITICAL': 50}

try:
    # create root logger from settings
    log_level = levels[config['log_level'].upper()]
    log_format = config['log_format']
    log_dir = Path(__file__).parent
    log_file = log_dir / Path(config['log_filepath'])
    os.makedirs(log_file.parent, exist_ok=True)
    logging.basicConfig(level=log_level, format=log_format, filename=log_file, force=True)

except Exception as e:
    print(f"Error creating logger: {e}. Using default settings.")

    # create root logger using default settings
    log_level = levels['INFO']
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_dir = Path(__file__).parent
    log_file = log_dir / Path('logs/ai_chatbot.log')
    os.makedirs(log_file.parent, exist_ok=True)
    logging.basicConfig(level=log_level, format=log_format, filename=log_file, force=True)


# empty log file if option is set
if config['empty_log']:
    with open(log_file, 'w'):
        pass


def get_logger(name: str) -> logging.Logger:
    ''' Creates child logger inside namespace '''
    return logging.getLogger(f'{NAMESPACE}.{name}')
