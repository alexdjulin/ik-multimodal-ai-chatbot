#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: config_loader.py
Description: Loads and provides the contents of the yaml configuration file to all modules.
Author: @alexdjulin
Date: 2024-07-25
"""

import yaml
from typing import Optional, Dict

_config: Optional[Dict] = None


def load_config(config_file: str) -> Dict:
    ''' Load config file and return it as a dictionary 

    Args:
        config_file (str): path to the config file

    Returns:
        (Dict): the loaded configuration as a dictionary

    Raises:
        FileNotFoundError: if config file is not found
        ValueError: if error parsing the YAML file
    '''

    global _config

    if _config is None:
        try:
            with open(config_file, "r") as file:
                _config = yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file {config_file} not found.")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")

    return _config


def get_config() -> Dict:
    ''' Return the loaded config dict

    Raises:
        ValueError: if config is not loaded
    '''

    if _config is None:
        raise ValueError("Config not loaded. Call 'load_config' first.")

    return _config
