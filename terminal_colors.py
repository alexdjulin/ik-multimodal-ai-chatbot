#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: terminal_colors.py
Description: Define terminal codes to import and use in print statements.
Example: print(f"{RED}This is red text{RESET}")
Author: @alexdjulin
Date: 2024-07-25
"""

from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Regular text colors
BLACK = Fore.BLACK
RED = Fore.RED
GREEN = Fore.GREEN
YELLOW = Fore.YELLOW
BLUE = Fore.BLUE
MAGENTA = Fore.MAGENTA
CYAN = Fore.CYAN
WHITE = Fore.WHITE
GREY = Fore.BLACK + Style.BRIGHT  # Bright black for grey

# Bold text colors
B_BLACK = Style.BRIGHT + Fore.BLACK
B_RED = Style.BRIGHT + Fore.RED
B_GREEN = Style.BRIGHT + Fore.GREEN
B_YELLOW = Style.BRIGHT + Fore.YELLOW
B_BLUE = Style.BRIGHT + Fore.BLUE
B_MAGENTA = Style.BRIGHT + Fore.MAGENTA
B_CYAN = Style.BRIGHT + Fore.CYAN
B_WHITE = Style.BRIGHT + Fore.WHITE

# Italics (using ANSI escape codes)
ITALIC = '\033[3m'
I_BLACK = '\033[3m' + Fore.BLACK
I_RED = '\033[3m' + Fore.RED
I_GREEN = '\033[3m' + Fore.GREEN
I_YELLOW = '\033[3m' + Fore.YELLOW
I_BLUE = '\033[3m' + Fore.BLUE
I_MAGENTA = '\033[3m' + Fore.MAGENTA
I_CYAN = '\033[3m' + Fore.CYAN
I_WHITE = '\033[3m' + Fore.WHITE

# Bold + Italic
B_I_BLACK = Style.BRIGHT + '\033[3m' + Fore.BLACK
B_I_RED = Style.BRIGHT + '\033[3m' + Fore.RED
B_I_GREEN = Style.BRIGHT + '\033[3m' + Fore.GREEN
B_I_YELLOW = Style.BRIGHT + '\033[3m' + Fore.YELLOW
B_I_BLUE = Style.BRIGHT + '\033[3m' + Fore.BLUE
B_I_MAGENTA = Style.BRIGHT + '\033[3m' + Fore.MAGENTA
B_I_CYAN = Style.BRIGHT + '\033[3m' + Fore.CYAN
B_I_WHITE = Style.BRIGHT + '\033[3m' + Fore.WHITE

# Dim text colors
DIM = Style.DIM
D_BLACK = Style.DIM + Fore.BLACK
D_RED = Style.DIM + Fore.RED
D_GREEN = Style.DIM + Fore.GREEN
D_YELLOW = Style.DIM + Fore.YELLOW
D_BLUE = Style.DIM + Fore.BLUE
D_MAGENTA = Style.DIM + Fore.MAGENTA
D_CYAN = Style.DIM + Fore.CYAN
D_WHITE = Style.DIM + Fore.WHITE

# Additional colors (24-bit or extended colors)
L_BLACK = '\033[90m'
L_RED = '\033[91m'
L_GREEN = '\033[92m'
L_YELLOW = '\033[93m'
L_BLUE = '\033[94m'
L_MAGENTA = '\033[95m'
L_CYAN = '\033[96m'
L_WHITE = '\033[97m'

# Additional background colors
BG_L_BLACK = '\033[90m' + Style.BRIGHT
BG_L_RED = '\033[91m' + Style.BRIGHT
BG_L_GREEN = '\033[92m' + Style.BRIGHT
BG_L_YELLOW = '\033[93m' + Style.BRIGHT
BG_L_BLUE = '\033[94m' + Style.BRIGHT
BG_L_MAGENTA = '\033[95m' + Style.BRIGHT
BG_L_CYAN = '\033[96m' + Style.BRIGHT
BG_L_WHITE = '\033[97m' + Style.BRIGHT

# Underline (using ANSI escape codes)
UNDERLINE = '\033[4m'

# Reset formatting
RESET = Style.RESET_ALL

# Clear line (override with 100 blank spaces) and go back to line start
CLEAR = f'\r{100*" "}\r'
