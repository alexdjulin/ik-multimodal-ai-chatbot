#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: config_loader.py
Description: Loads and provides the contents of the YAML configuration file to all modules.
Author: @alexdjulin
Date: 2024-11-04
"""

from typing import Optional, Dict
import yaml

# Initialize the global config variable as None
_config: Optional[Dict] = None
DEFAULT_CONFIG_FILE = "config.yaml"


def load_config(config_file: str = DEFAULT_CONFIG_FILE) -> Dict:
    '''Load config file with all the project settings and return it as a dictionary.

    Args:
        config_file (str): Path to the config file. Default is DEFAULT_CONFIG_FILE.

    Returns:
        Dict: The loaded configuration as a dictionary.

    Raises:
        FileNotFoundError: If config file is not found.
        ValueError: If there's an error parsing the YAML file.
    '''

    global _config
    try:
        with open(config_file, "r", encoding='utf-8') as file:
            _config = yaml.safe_load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Config file '{config_file}' not found.") from exc
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file: {e}") from e

    return _config


def get_config() -> Dict:
    '''Return the loaded config dict. Load it if not already loaded.

    Returns:
        Dict: The configuration dictionary.

    Raises:
        ValueError: If config file is not loaded and no path is provided.
    '''

    global _config
    if _config is None:
        # If _config is None, load it with the provided or default path
        _config = load_config()

    return _config
