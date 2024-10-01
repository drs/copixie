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
import logging
import itertools
import re 
from platform import python_version
from dataclasses import dataclass

import configobj
import pandas as pd

from .pipeline import Pipeline, UnhandledPostprocessingError, CalledProcessError
from .log import Logger, ColoredFormatter
from .config import Config
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
            self.metadata = self.parse_metadata()
        except RuntimeError as e:
            raise HaltException(e)

        self.logger.info("Found a valid metadata file.".format(len(self.metadata)), extra={'context': self.CONTEXT})

        # Run DCTracker in parallel
        params = self.prepare_run()

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
        Pipeline(params)

        self.logger.info("Done.", extra={'context': self.CONTEXT})


    def parse_metadata(self):
        """
        Parse a metadata file with the following format : 
        - Condition,Replicate,Path
        and returns a dict with the following format : 
        - { Condition : [ [ Replicate, Path ], ... ]}
            
        Return:
            dict: Parsed metadata
        """
        metadata = dict()
        with open(self.metadata_file) as h:
            for l in h:
                # Ignore blank line and comment line (line starting with #)
                if not l.startswith("#") or l.strip() == "":
                    l = l.strip().split(",")
                    # Raise an error if the metadata does not contain the 3 columns required
                    if len(l) != 3:
                        raise RuntimeError("Metadata contains {} columns but 3 were expected. Please refer to the documentation for the metadata file format.".format(len(l)))
                    
                    # Add key to dict if it does not exist yet
                    if not l[0] in metadata:
                        metadata[l[0]] = []
                    
                    # Add the entry to the metadata dict 
                    metadata[l[0]].append([l[1], l[2]])

        return metadata


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

        # Iterate through every element of every conditions, than analyse the file structure to identify the cells 
        for condition in self.metadata:
            for replicate in self.metadata[condition]:
                # Replicate information
                replicate_id = replicate[0]
                replicate_path = pathlib.Path(replicate[1])
                
                if replicate_path.is_dir():
                    no_analysis_directory = False 
                else:
                    self.logger.warning("The directory \"{}\" does not exist. Please check that the paths in the metadata correct.".format(replicate_path), extra={'context': self.CONTEXT})

                # List the expected file name/relative path based on the configuration information
                expected_files = []
                for channel in self.config.channels:
                    if channel.track_file:
                        expected_files.append(channel.track_file)
                    if channel.mask_file:
                        expected_files.append(channel.mask_file)

                # Empty structure to list the file in the analysis filestructure
                analysis_files = {key: list() for key in expected_files}

                # Parse the analysis filestructure searching for the expected file name/relative path
                for path in replicate_path.rglob('*'):
                    if path.is_file():
                        for k in analysis_files:
                            if path.match(k):
                                # Get the cell path by removing the path from the config (this can include a file and folder)
                                suffix_len = len(pathlib.Path(k).parts)
                                cell_path = pathlib.Path(*path.parts[:-suffix_len])
                                analysis_files[k].append(cell_path)

                # Extract all the cell folder identified in the previous step
                # The folder does not need to contain all the required file (based on the config)
                # Incomplete folders will be handled after 
                cell_folders = set(itertools.chain.from_iterable(analysis_files.values()))

                if not cell_folders:
                    raise HaltException("No valid cell folder were found. Nothing to analyze.")
                
                # Identify the part in the path that varies between the cells 
                # This segment of the paths will be used as the label of the cells 
                folder_lst = []
                for folder in cell_folders:
                    folder_lst.append(folder.parts)
                df = pd.DataFrame(folder_lst)

                # Efficient solution to identify columns where all values are identical (source: https://stackoverflow.com/a/54405767)
                def unique_cols(df):
                    a = df.to_numpy() # df.values (pandas<0.24)
                    return (a[0] == a).all(0)
                
                label_start = -1
                if not unique_cols(df).all():
                    label_start = unique_cols(df).tolist().index(False)
                
                # Parse the file structure
                for folder in cell_folders:
                    label = ""
                    if label_start > 0:
                        label = '/'.join(folder.parts[label_start:])
                    output = pathlib.Path(self.output_dir, re.sub('[^0-9a-zA-Z-]+', '_', condition), re.sub('[^0-9a-zA-Z-]+', '_', replicate[0]), *folder.parts[label_start:])
                        
                    try:
                        cell = Cell(folder, output, self.config, condition=condition, replicate=replicate, label=label)
                        dctracker_args.append(cell)
                    except RuntimeWarning as w:
                        self.logger.warning(w, extra={'context': self.CONTEXT})

        # Handle invalid input
        if no_analysis_directory:
            raise HaltException("Filestructure does not contain any valid directory. This is likely due to an error in the configuration file or the metadata.")
        if not dctracker_args:
            raise HaltException("Filestructure does not contain any valid file. This is likely due to an error in the configuration file or the metadata.")

        return dctracker_args
        

    def validate_user_parameters(self):
        # Check that the input variable are not empty (necessary for GUI only as command line
        # already validates)
        if not self.output_dir:
            raise HaltException("No output directory was provided.")
        if not self.metadata_file:
            raise HaltException("No metadata file was provided.")
        
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


class Cell():
    """class to process the cells folder. each cell folder is expected to contain the files 
    described in the configuration file."""

    def __init__(self, path, output, config, condition=None, replicate=None, label=None):
        """constructor for the cell class"""
        self.output = output
        self.pixel_size = config.pixel_size
        self.frame_interval = config.frame_interval
        self.condition = condition
        self.replicate = replicate
        self.label = label
        # parse the cell folder to validate that it contains the required files
        self.channels = self._prepare_cell(path, config)

    def _prepare_cell(self, path, config):
        """fetch the cell information and validate that it's a valid input for copixie"""
        channels = []
        for channel in config.channels:
            descr = channel.description
            static = channel.static
            radius = channel.radius

            track_file = pathlib.Path(path, channel.track_file)
            if not track_file.is_file():
                raise RuntimeWarning("Folder \"{}\" does not contain the file \"{}\".".format(path, channel.track_file))
            
            mask_file = None
            if channel.mask_file:
                mask_file = pathlib.Path(path, channel.mask_file)
                if not mask_file.is_file():
                    raise RuntimeWarning("Folder \"{}\" does not contain the file \"{}\".".format(path, channel.mask_file))
            
            channels.append(Channel(descr, track_file, mask_file, radius, static))
        
        return channels

@dataclass
class Channel():
    """class to store the channel information for the cells"""
    description: str
    track_file: str
    mask_file: str
    radius: float
    static: bool
