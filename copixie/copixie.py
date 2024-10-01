"""
Copyright (C) 2023-2024 Samuel Prince <samuel.prince-drouin@umontreal.ca>

This file is a part of CoPixie.

This file may be used under the terms of the GNU General Public License
version 3 as published by the Free Software Foundation and appearing in
the file LICENSE included in the packaging of this file.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import argparse
import os
import sys
import pathlib
import datetime 
import multiprocessing
from platform import python_version

import configobj
import pandas as pd

from .pipeline import Pipeline, UnhandledPostprocessingError, CalledProcessError
from .log import Logger, ColoredFormatter
from .config import Config
from .metadata import Metadata
from .__version__ import __version__

class HaltException(Exception): 
    """Raise if a critical error is encountered to allow CLI/GUI specific handling of critical errors"""


class Runner():
    """
    This class contains the general code to run DCTracker regardless of it's 
    execution mode (CLI or GUI). 
    """

    def __init__(self):
        # Start the logger
        self.logger = Logger().logger
        self.CONTEXT = "CoPixie"
    
    def main(self):
        # Set the content and start logging at this point (everything logged before is fatal errors)
        self.logger.info("Starting CoPixie (version {})".format(__version__), extra={'context': self.CONTEXT})
        self.logger.debug("Python version: {}".format(python_version()), extra={'context': self.CONTEXT})

        # Validate that the inputs and output exists and are readable or writable
        self.validate_user_parameters()

        # Parse the configuration and handle the configuration errors
        try:
            self.config = Config(self.config_file)
        except configobj.ConfigObjError as e:
            msg = "Invalid configuragion file. Make sure the configuration is correct. Complete error message (for debugging): \n" + str(e)
            self.logger.error(msg, extra={'context': self.CONTEXT})
            sys.exit(1)
        except RuntimeError as e:
            self.logger.error(e, extra={'context': self.CONTEXT})
            sys.exit(1)

        self.logger.info("Parsed the configuration file.", extra={'context': self.CONTEXT})

        # Parse the metadata
        try:
            self.metadata = Metadata(self.metadata_file)
        except RuntimeError as e:
            self.logger.error(e, extra={'context': self.CONTEXT})
            sys.exit(1)

        self.logger.info("Parsed a metadata file ({} assays).".format(len(self.metadata.assays)), extra={'context': self.CONTEXT})

        # we're getting a list of each cells for each assay 
        cells = []
        for assay in self.metadata.assays:
            assay.process_file_structure(self.config, self.output_dir)
            for cell in assay.cells:
                cells.append((cell, assay))

        # if 'Postprocessing' in self.config:
        #     if 'Command' in self.config['Postprocessing']:
        #         try:
        #             Pipeline(params, [self.output_dir, self.config['Postprocessing']['Command']])
        #         except FileNotFoundError:
        #             msg = "The command file \"{}\" was not found. Make sure that this program is in the PATH or that the path in the configuration file is correct.".format(self.config['Postprocessing']['Command'])
        #             raise HaltException(msg)
        #         except CalledProcessError as e:
        #             raise HaltException(e)
        #         except UnhandledPostprocessingError as e:
        #             msg = "An error occured during the execution of the postprocessing step. This is not handled by CoPixie, but here is the error message to help with the debugging : \n{}".format(e)
        #             raise HaltException(msg)
        #     else:
        #         Pipeline(params)
        # else:
        #     Pipeline(params)
        Pipeline(cells)

        self.logger.info("Done.", extra={'context': self.CONTEXT})


    def prepare_run(self):
        """
        Generate a list of list that will be used to initiate the multiprocessing map for DCTracker parallel processes. 

        Returns: 
            list: of inputs to run the DCTracker module in parallel
        """
        # Variable to handle incorrect paths error
        # Initially set at True, and must be changed to False if valid input are encountered 
        no_analysis_directory = True 

        # Prepare the datastructue for the DCTracker module
        dctracker_args = []

        if not dctracker_args:
            raise HaltException("Filestructure does not contain any valid file. This is likely due to an error in the configuration file or the metadata.")

        return dctracker_args
        

    def validate_user_parameters(self):
        # Check that the input variable are not empty (necessary for GUI only as command line
        # already validates)
        if not self.output_dir:
            raise HaltException("No output directory was provided.")
        
        
        # Check if the output directory exists and is writable
        # This is done to avoid running the computation if the output cannot be written
        # If the output directory exist, make sure it's empty and writable
        if self.output_dir.exists():
            if self.output_dir.is_dir(): 
                if os.access(self.output_dir, os.W_OK):
                    if len(list(self.output_dir.glob('*'))) > 0:
                        raise HaltException("Output path points to an existing non-empty directory.")
                else:
                    raise HaltException("Output path points to a non-writable directory.")
            else:
                raise HaltException("Output path points to an existing file.")
        # Make sure that the parent directory is writable
        else:
            parent_dir = pathlib.Path(self.output_dir).parents[0]
            if not os.access(parent_dir, os.W_OK):
                raise HaltException("Output path points to a non-writable directory.")


class CLIRunner(Runner):

    def __init__(self):
        # Initialize the global variable from parent class 
        super().__init__()

        # Parse the command line arguments
        args = self.get_arguments()

        # Generate the global variable from the command line arguments that are used 
        # in the parent class code
        self.config_file = pathlib.Path(args.config).resolve()
        self.output_dir = pathlib.Path(args.output).resolve()
        self.metadata_file = pathlib.Path(args.metadata).resolve()

        # Run the main analysis pipeline
        self.main()

    
    def main(self):
        try:
            super().main()
        except HaltException as e:
            self.logger.error(e, extra={'context': self.CONTEXT})
            sys.exit(1)
        

    def get_arguments(self):
        """
        Parse the command line arguments.
        """
        parser = argparse.ArgumentParser(description="DualCam Particle Tracking Analysis")
        parser.add_argument('-c', '--config', type=pathlib.Path, required=True, 
                            help='Configuration file')
        parser.add_argument('-m', '--metadata', type=pathlib.Path, required=True, 
                            help="Metadate file")
        parser.add_argument('-o', '--output', type=pathlib.Path, default="DCTracker-{}".format(datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")), 
                            help='Output directory')

        # If no arguments were used, print the entire help
        if len(sys.argv) == 1:
            parser.print_help(file=sys.stderr)
            sys.exit(1)
        args = parser.parse_args()

        return args
