# Copyright (C) 2023-2024 Samuel Prince <samuel.prince-drouin@umontreal.ca>
# 
# This file is a part of CoPixie.
# 
# This file may be used under the terms of the GNU General Public License
# version 3 as published by the Free Software Foundation and appearing in
#the file LICENSE included in the packaging of this file.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Logging module"""

import logging 
import os


class ColoredFormatter(logging.Formatter):
    """
    Colored formatted for logging, adapted from https://stackoverflow.com/a/56944256
    """
    
    YELLOW = '\x1b[33m'
    RED = '\x1b[31m'
    BOLD_RED = '\x1b[31;1m'
    RESET = '\x1b[0m'

    def __init__(self, fmt, datefmt):
        super().__init__()
        self.fmt = fmt
        self.datefmt = datefmt
        # Add ANSI escape code if supported by the console 
        self.FORMATS = None
        if self.console_supports_ansi():
            self.FORMATS = {
                logging.DEBUG: self.fmt,
                logging.INFO: self.fmt,
                logging.WARNING: self.YELLOW + self.fmt + self.RESET,
                logging.ERROR: self.BOLD_RED + self.fmt + self.RESET,
                logging.CRITICAL: self.BOLD_RED + self.fmt + self.RESET
            }
        

    def format(self, record):
        if self.FORMATS:
            log_fmt = self.FORMATS.get(record.levelno)
        else:
            log_fmt = self.fmt
        
        formatter = logging.Formatter(log_fmt, datefmt=self.datefmt)
        return formatter.format(record)

    
    def console_supports_ansi(self):
        """
        Returns true if the console supports ANSI escape codes

        Someone suggested to use Django function https://stackoverflow.com/a/22254892
        that is probably be more complete but was not done to avoid license integration 
        (https://github.com/django/django/blob/main/django/core/management/color.py)
        In case issues are observed, this function could be improved using this code
        """
        # On Windows, check if the ANSICON environment variable is present
        if os.name == 'nt':
            return 'ANSICON' in os.environ
        # For Linux and other POSIX-compliant systems, it checks if the TERM 
        # environment variable is set and if it contains the string 'xterm' 
        # (indicating that the terminal supports ANSI escape codes).
        elif os.name == 'posix':
            return 'TERM' in os.environ and 'xterm' in os.environ['TERM']
        else:
            return False


class Logger():

    def __init__(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)

        formatter = ColoredFormatter('%(asctime)s  [%(context)s]  %(levelname)s    %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)