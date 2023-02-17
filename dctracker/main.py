"""
Copyright (C) 2023 Samuel Prince <samuel.prince-drouin@umontreal.ca>

This file is a part of DCTracker.

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

from dctracker.dctracker import DCTracker 
from dctracker.dctracker import InvalidCentroidError
from dctracker.log import Logger
from dctracker.config import *
from dctracker.version import __version__


class InvalidInputError(Exception):
    """Raise if an input unit does not contain a file described in the config"""


class Runner():
    """
    This class contains the general code to run DCTracker regardless of it's 
    execution mode (CLI or GUI). 
    """

    def __init__(self):
        # Start the logger
        self.logger = Logger().logger

    
    def main(self):
        # Set the content and start logging at this point (everything logged before is fatal errors)
        self.context = 'Main'
        self.logger.info("Starting DCTracker. Version {}".format(__version__), extra={'context': self.context})
        self.logger.debug("Python version: {}".format(python_version()), extra={'context': self.context})            

        # Parse the configuration and handle the configuration errors
        try:
            self.config = parse_config(self.config_file)
        except configobj.ConfigObjError as e:
            self.exit_on_error(e, self.context)
        except ConfigError as e:
            self.exit_on_error(e.args[0], self.context)
        except ConfigValueError as e:
            self.exit_on_error(e.args[0], self.context)
        except ConfigTypeError as e:
            self.exit_on_error(e.args[0], self.context)

        self.logger.info("Found a valid configuration.", extra={'context': self.context})

        # Parse the metadata
        try:
            self.metadata = self.parse_metadata()
        except ValueError as e:
            self.exit_on_error(e, self.context)

        # Run DCTracker in parallel
        params = self.prepare_run()
        #for param in params:
        #    print(param)
        #    self.run_dctracker(param)
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            pool.map(self.run_dctracker, params)


    def exit_on_error(self, message, context):
        self.logger.critical(message, extra={'context': self.context})
        sys.exit(1)


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
                        raise ValueError("Metadata contains {} columns but 3 were expected. Please refer to the documentation for the metadata file format.").format(len(l))
                    
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

        def path_to_list(path):
            return os.path.normpath(path).lstrip(os.path.sep).split(os.path.sep)

        # Prepare the datastructure for the DCTracker module
        dctracker_args = []

        # Iterate through every element of every conditions, than analyse the file structure to identify the cells 
        for condition in self.metadata:
            for replicate in self.metadata[condition]:
                # Replicate information
                replicate_id = replicate[0]
                replicate_path = replicate[1]
                full_replicate_path = os.path.join(self.input_dir, replicate_path)
                
                # Cells file structure are exclusively searched at the depth specified in Input/Depth relative 
                # to the input path in the config (the real search depth is therefore the sum of the input 
                # depth and config depth)
                start_depth = len(path_to_list(full_replicate_path))
                real_depth = start_depth + int(self.config['Input']['Depth'])

                for root, dirs, files in os.walk(full_replicate_path):
                    # Process only folders at the search depth
                    if len(path_to_list(root)) == real_depth:
                        # Generate the cell dictionary 
                        cell = dict()
                        label = '/'.join(path_to_list(root)[-int(self.config['Input']['Depth']):])
                        full_output_path = os.path.join(self.output_dir, replicate_path, label)
                        cell['Condition'] = condition
                        cell['Replicate'] = replicate
                        cell['Label'] = label
                        cell['Output'] = full_output_path
                        
                        try:
                            particles = self.parse_cell(root)
                            dctracker_args.append([cell] + particles)
                        except InvalidInputError as e:
                            self.logger.warning("Input folder \"{}\" does not contain the file \"{}\".".format(label, e), extra={'context': self.context})

        return dctracker_args


    def parse_cell(self, path):
        """Parse a cell folder and the config to retrive the information required to run DCTracker

        Exceptions:
            InvalidInputError: Raised if the cell folder does not contain all the files required for DCTracker
        
        Arguments:
            path (str): Cell folder path

        Return: 
            dict: particle dictionary for DCTracker module
        """
        # Typical particle dictionary for DCTracker module
        particle_dict = {
            'Name': '',
            'TrackFile': '',
            'MaskFile': '', # Optional
            'PixelSize': self.config['General']['PixelSize'],
            'Radius': 0.0, # Optional but required if no mask
            'Static': False,
        }

        # Fetch the general informations from the configuration file
        particles = [] 

        for particle_name in list_particle_key(self.config):
            particle = particle_dict.copy()
            particle['Particle'] = particle_name
                            
            particle_config = self.config['Input'][particle_name]

            # Config options for true are : 'y', 'yes', 'Yes'
            if particle_config['Static'] in ['y', 'yes', 'Yes']:
                particle['Static'] = True
            else:
                particle['Static'] = False
            
            # Every cell must at least contain a spot file that contains the centroid 
            # regardless of the analysis type
            track_path = os.path.join(path, particle_config['TrackFile'])
            if not os.path.isfile(track_path):
                raise InvalidInputError(particle_config['TrackFile'])
            particle['TrackFile'] = track_path

            # Cells can have either a mask or a particle raduis (no mask)
            if particle_config['MaskFile']:
                mask_path = os.path.join(path, particle_config['MaskFile'])
                if not os.path.isfile(track_path):
                    raise InvalidInputError(particle_config['MaskFile'])
                particle['MaskFile'] = mask_path
            else:
                particle['Radius'] = particle_config['Radius']
            particles.append(particle)
        
        return particles


    def run_dctracker(self, params):
        """
        Run DCTracker

        Arguments:
            params: DCTracker module parameters
        """
        try:
            DCTracker(params)
        except InvalidCentroidError:
            self.logger.warning("Mask and tracking does not match for cell \"{}\".".format(params[0]['Label']), extra={'context': self.context})


class CLIRunner(Runner):

    def __init__(self):
        # Initialize the global variable from parent class 

        super().__init__()
        # Define the content for the logger 
        self.context = 'Initialization'
        # Parse the command line arguments
        args = self.get_arguments()

        # Generate the global variable from the command line arguments that are used 
        # in the parent class code
        self.config_file = args.config
        self.input_dir = args.input 
        self.output_dir = args.output
        self.metadata_file = args.metadata

        # Run the main analysis pipeline
        super().main()
        

    def get_arguments(self):
        """
        Parse the command line arguments.
        """
        parser = argparse.ArgumentParser(description="DualCam Particle Tracking Analysis")
        parser.add_argument('-c', '--config', type=pathlib.Path, required=True, 
                            help='Configuration file')
        parser.add_argument('-i', '--input', type=pathlib.Path, required=True, 
                            help="Input directory")
        parser.add_argument('-m', '--metadata', type=pathlib.Path, required=True, 
                            help="Metadate file")
        parser.add_argument('-o', '--output', type=pathlib.Path, default="DCTracker-{}".format(datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")), 
                            help='Output directory')

        # If no arguments were used, print the entire help
        if len(sys.argv) == 1:
            parser.print_help(file=sys.stderr)
            sys.exit(1)
        args = parser.parse_args()

        # Change arguments paths to full paths
        args.config = os.path.abspath(os.path.realpath(args.config))
        args.output = os.path.abspath(os.path.realpath(args.output))
        args.input = os.path.abspath(os.path.realpath(args.input))
        args.metadata = os.path.abspath(os.path.realpath(args.metadata))

        # Check that input files and directory exists and are readable
        # (readabily is not reported as it's not expected to occur during normal use)
        if os.path.isdir(args.input):
            if not os.access(args.input, os.R_OK):
                self.exit_on_error(message="Input path points to a non-existing directory.", context=self.context)
        else:
            self.exit_on_error(message="Input path points to file. The input must be a directory.", context=self.context)
        if not os.access(args.config, os.R_OK):
            self.exit_on_error(message="Configuration path points to a non-existing file.", context=self.context)
        if not os.access(args.metadata, os.R_OK):
            self.exit_on_error(message="Metadata path points to a non-existing file.", context=self.context)

        # Check if the output directory exists and is writable
        # This is done to avoid running the computation if the output cannot be written
        # If the output directory exist, make sure it's empty and writable
        if os.path.exists(args.output):
            if os.path.isdir(args.output): 
                if os.access(args.output, os.W_OK):
                    if len(os.listdir(args.output)) > 0:
                        self.exit_on_error(message="Cowardly refusing to overwrite an existing non-empty directory.", context=self.context)
                else:
                    self.exit_on_error(message="Output path points to a non-writable directory.", context=self.context)
            else:
                self.exit_on_error(message="Cowardly refusing to overwrite an existing file.", context=self.context)
        # Make sure that the parent directory is writable
        else:
            parent_dir = pathlib.Path(args.output).parents[0]
            if not os.access(parent_dir, os.W_OK):
                self.exit_on_error(message="Output path points to a non-writable directory.", context=self.context)

        return args


class GUIRunner(Runner):
    pass