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
import logging
import itertools
import re 
from platform import python_version

import configobj
from ansi2html import Ansi2HTMLConverter
import pandas as pd

try:
    from PyQt6 import QtCore
    from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt
    from PyQt6.QtWidgets import QApplication, QWidget, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMainWindow, QFileDialog, QTextEdit, QStyle
except ModuleNotFoundError:
    pass

from dctracker.pipeline import Pipeline, UnhandledPostprocessingError, CalledProcessError
from dctracker.log import Logger, ColoredFormatter
from dctracker.config import *
from dctracker.version import __version__


class InvalidInputError(Exception):
    """Raise if an input unit does not contain a file described in the config"""

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
        self.CONTEXT = "Main"
    
    def main(self):
        # Set the content and start logging at this point (everything logged before is fatal errors)
        self.logger.info("Starting DCTracker (version {})".format(__version__), extra={'context': self.CONTEXT})
        self.logger.debug("Python version: {}".format(python_version()), extra={'context': self.CONTEXT})

        # Validate that the inputs and output exists and are readable or writable
        self.validate_user_parameters()

        # Parse the configuration and handle the configuration errors
        try:
            self.config = parse_config(self.config_file)
        except configobj.ConfigObjError as e:
            raise HaltException("Invalid configuragion file. Make sure the configuration is correct. Complete error message (for debugging): \n" + str(e))
        except ConfigError as e:
            raise HaltException(e.args[0])
        except ConfigValueError as e:
            raise HaltException(e.args[0])
        except ConfigTypeError as e:
            raise HaltException(e.args[0])

        self.logger.info("Found a valid configuration.", extra={'context': self.CONTEXT})

        # Parse the metadata
        try:
            self.metadata = self.parse_metadata()
        except RuntimeError as e:
            raise HaltException(e)

        self.logger.info("Found a valid metadata file.".format(len(self.metadata)), extra={'context': self.CONTEXT})

        # Run DCTracker in parallel
        params = self.prepare_run()

        if 'Postprocessing' in self.config:
            if 'Command' in self.config['Postprocessing']:
                try:
                    Pipeline(params, [self.output_dir, self.config['Postprocessing']['Command']])
                except FileNotFoundError:
                    msg = "The command file \"{}\" was not found. Make sure that this program is in the PATH or that the path in the configuration file is correct.".format(self.config['Postprocessing']['Command'])
                    raise HaltException(msg)
                except CalledProcessError as e:
                    raise HaltException(e)
                except UnhandledPostprocessingError as e:
                    msg = "An error occured during the execution of the postprocessing step. This is not handled by DCTracker, but here is the error message to help with the debugging : \n{}".format(e)
                    raise HaltException(msg)
            else:
                Pipeline(params)
        else:
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
                for particle in self.config['Input']:
                    if self.config['Input'][particle]['TrackFile']:
                        expected_files.append(self.config['Input'][particle]['TrackFile'])
                    if self.config['Input'][particle]['MaskFile']:
                        expected_files.append(self.config['Input'][particle]['MaskFile'])

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
                    # Generate the cell dictionary 
                    cell = dict()
                    label = ""
                    if label_start > 0:
                        label = '/'.join(folder.parts[label_start:])
                    
                    cell['Condition'] = condition
                    cell['Replicate'] = replicate
                    cell['Label'] = label
                    full_output_path = pathlib.Path(self.output_dir, re.sub('[^0-9a-zA-Z-]+', '_', condition), re.sub('[^0-9a-zA-Z-]+', '_', replicate[0]), *folder.parts[label_start:])
                    cell['Output'] = full_output_path
                    cell['PixelSize'] = self.config['General']['PixelSize']
                    cell['FrameInterval'] = self.config['General']['FrameInterval']
                        
                    try:
                        particles = self.parse_cell(folder)
                        dctracker_args.append([cell] + particles)
                    except InvalidInputError as e:
                        self.logger.warning("Folder \"{}\" does not contain the file \"{}\".".format(folder, e), extra={'context': self.CONTEXT})

        # Handle invalid input
        if no_analysis_directory:
            raise HaltException("Filestructure does not contain any valid directory. This is likely due to an error in the configuration file or the metadata.")
        if not dctracker_args:
            raise HaltException("Filestructure does not contain any valid file. This is likely due to an error in the configuration file or the metadata.")

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
            'Radius': 0.0, # Optional but required if no mask
            'Static': False,
        }

        # Fetch the general informations from the configuration file
        particles = [] 

        for particle_name in list_particle_key(self.config):
            particle = particle_dict.copy()
            particle['Name'] = particle_name
                            
            particle_config = self.config['Input'][particle_name]

            # Config options for true are : 'y', 'yes', 'Yes'
            if particle_config['Static'] in ['y', 'yes', 'Yes']:
                particle['Static'] = True
            else:
                particle['Static'] = False
            
            # Every cell must at least contain a spot file that contains the centroid 
            # regardless of the analysis type
            track_path = pathlib.Path(path, particle_config['TrackFile'])
            if not track_path.is_file():
                raise InvalidInputError(particle_config['TrackFile'])
            particle['TrackFile'] = track_path

            # Cells can have either a mask or a particle raduis (no mask)
            if particle_config['MaskFile']:
                mask_path = pathlib.Path(path, particle_config['MaskFile'])
                if not mask_path.is_file():
                    raise InvalidInputError(particle_config['MaskFile'])
                particle['MaskFile'] = mask_path
            else:
                particle['Radius'] = particle_config['Radius']
            particles.append(particle)
        
        return particles
        

    def validate_user_parameters(self):
        # Check that the input variable are not empty (necessary for GUI only as command line
        # already validates)
        if not self.output_dir:
            raise HaltException("No output directory was provided.")
        if not self.metadata_file:
            raise HaltException("No metadata file was provided.")
        if not self.config_file:
            raise HaltException("No configuration file was provided.")
        
        # Check that input files and directory exists and are readable
        # (readabily is not reported as it's not expected to occur during normal use)
        if not os.access(self.config_file, os.R_OK):
            raise HaltException("Configuration path points to a non-existing file.")
        if not os.access(self.metadata_file, os.R_OK):
            raise HaltException("Metadata path points to a non-existing file.")

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


class GUIRunner(Runner):

    def __init__(self):
        # Initialize the global variable from parent class 
        super().__init__()
    
        # Import PyQt6 module here so DCTracker can be used from command line without installing PyQt6
        try:
            from PyQt6 import QtCore 
        except ModuleNotFoundError as e:
            # Warn the user if PyQt6 is not installed (only on Windows for now, MacOS or Linux user should be able to figure
            # it out by themselves ¯\_(ツ)_/¯ )
            if sys.platform == 'win32':
                import ctypes
                MessageBox = ctypes.windll.user32.MessageBoxW
                MessageBox(None, 'Cannot start DCTracker from GUI. PyQt6 module is not installed.', 'DCTracker', 0)

        # Create the main window widget 
        app = QApplication(sys.argv)
        self.initUI()
        app.exec()


    def initUI(self):
        # Prepare the application
        self.main_window = QMainWindow()
        self.main_window.setGeometry(0, 0, 350, 400)
        self.main_window.setWindowTitle("DCTracker GUI")

        # Folder icon 
        pixmapi = QStyle.StandardPixmap.SP_DirIcon
        icon = self.main_window.style().standardIcon(pixmapi)

        # Initialize the widgets 
        # Configuration related widgets
        self.config_layout = QHBoxLayout()
        self.config_label = QLabel('Configuration')
        self.config_field = PathLineEdit()
        self.config_button = QPushButton()
        self.config_button.setIcon(icon)
        self.config_layout.addWidget(self.config_field)
        self.config_layout.addWidget(self.config_button)
        self.config_button.clicked.connect(self.open_config_file)

        # Metadata related widgets
        self.metadata_layout = QHBoxLayout()
        self.metadata_label = QLabel("Metadata")
        self.metadata_field = PathLineEdit()
        self.metadata_button = QPushButton()
        self.metadata_button.setIcon(icon)
        self.metadata_layout.addWidget(self.metadata_field)
        self.metadata_layout.addWidget(self.metadata_button)
        self.metadata_button.clicked.connect(self.open_metadata_file)

        # Output related widgets
        self.output_layout = QHBoxLayout()
        self.output_label = QLabel("Output Directory")
        self.output_field = PathLineEdit()
        self.output_button = QPushButton()
        self.output_button.setIcon(icon)
        self.output_layout.addWidget(self.output_field)
        self.output_layout.addWidget(self.output_button)
        self.output_button.clicked.connect(self.open_output_dir)

        # Console handler
        self.textedit_logger = TextEditLogger()
        logging.getLogger().addHandler(self.textedit_logger)
        logging.getLogger().setLevel(logging.DEBUG)        
        self.textedit_logger.signal_logging.connect(self.insert_html)

        self.worker = Worker(self.main, ())
        self.worker.finished.connect(self.restore_ui)
        self.worker.terminate()
        
        # Run button
        self.run_layout = QHBoxLayout()
        self.run_button = QPushButton("Run DCTracker")
        self.run_layout.addWidget(self.run_button)
        self.run_button.clicked.connect(self.run_main)

        # Generate the layout
        self.main_layout = QFormLayout()
        self.main_layout.addRow(self.config_label, self.config_layout)
        self.main_layout.addRow(self.metadata_label, self.metadata_layout)
        self.main_layout.addRow(self.output_label, self.output_layout)
        self.main_layout.addRow(self.textedit_logger.widget)
        self.main_layout.addRow(self.run_button)

        # Configure the window
        self.central_widget = QWidget()
        self.main_window.setCentralWidget(self.central_widget)
        self.central_widget.setLayout(self.main_layout)
        self.main_window.show()


    def main(self):
        # Set variables 
        self.config_file = pathlib.Path(self.config_field.text()).resolve()
        self.output_dir = pathlib.Path(self.output_field.text()).resolve() 
        self.metadata_file = pathlib.Path(self.metadata_field.text()).resolve()

        try:
            super().main()
        except HaltException as e:
            self.logger.critical(e, extra={'context': self.CONTEXT})
        except Exception as e:
            self.logger.critical("An unhandled except occured during DCTracker run. Please consider reporting the issue to help DCTracker development." , extra={'context': self.CONTEXT})
            self.logger.critical(e, exc_info=True, extra={'context': self.CONTEXT})


    # Button signals handling functions 
    def open_config_file(self):
        file_name = QFileDialog.getOpenFileName(self.main_window, "Select Configuration File", "", "Configuration Files (*.cfg)")
        if file_name:
            self.config_field.setText(file_name[0])


    def open_metadata_file(self):
        file_name = QFileDialog.getOpenFileName(self.main_window, "Select Metadata File", "", "CSV Files (*.csv)")
        if file_name:
            self.metadata_field.setText(file_name[0])


    def open_output_dir(self):
        file_name = QFileDialog.getExistingDirectory(self.main_window, "Select Output Directory")
        if file_name:
            self.output_field.setText(file_name)


    def run_main(self):
        self.textedit_logger.widget.clear()
        self.run_button.setEnabled(False)
        self.worker.start()


    def restore_ui(self):
        self.run_button.setEnabled(True)


    def insert_html(self, msg):
        self.textedit_logger.widget.insertHtml(msg)
        self.textedit_logger.widget.insertHtml("<br>")
        self.textedit_logger.widget.ensureCursorVisible()


class TextEditLogger(logging.Handler, QObject):
    signal_logging = pyqtSignal(object)
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

        self.widget = QTextEdit()
        self.widget.setReadOnly(True)

        formatter = ColoredFormatter('%(asctime)s  [%(context)s]  %(levelname)s    %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        conv = Ansi2HTMLConverter(dark_bg=False)
        html = conv.convert(msg)
        self.signal_logging.emit(html)

        
class Worker(QThread):
    def __init__(self, func, args):
        super(Worker, self).__init__()
        self.func = func
        self.args = args

    def run(self):
        self.func(*self.args)


class PathLineEdit(QLineEdit):

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)


    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()


    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.setText(event.mimeData().urls()[0].toLocalFile())
            event.accept()
        else:
            event.ignore()
