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

"""Main module for CoPixie"""

import argparse
import sys
import pathlib
import datetime 
import multiprocessing
import json
from platform import python_version

import configobj

from .log import Logger
from .config import Config
from .metadata import Metadata
from .dctracker import DCTracker, InvalidCentroidError
from .colocalize import Colocalize
from .__version__ import __version__


class CoPixie():
    """
    This class contains the general code to run DCTracker regardless of it's 
    execution mode (CLI or GUI). 
    """

    def __init__(self):
        # parse the command line arguments
        args = self._get_arguments()
        self.config_file = pathlib.Path(args.config).resolve()
        self.output_dir = pathlib.Path(args.output).resolve()
        self.metadata_file = pathlib.Path(args.metadata).resolve()
        self.threads = args.threads

        # initialize the logger
        self.logger = Logger().logger
        self.CONTEXT = "CoPixie"

        # run the main analysis pipeline
        self.main()
    
    def main(self):
        # start logging
        self.logger.info("Starting CoPixie (version {})".format(__version__), extra={'context': self.CONTEXT})
        self.logger.debug("Python version: {}".format(python_version()), extra={'context': self.CONTEXT})

        # run the analysis pipeline
        self._parse_config()
        self._parse_metadata()
        cells = self._prepare_pipeline()
        self._run_pipeline(cells)
        self.logger.info("Done.", extra={'context': self.CONTEXT})

    def _get_arguments(self):
        """parse the command line arguments (PRIVATE)"""

        parser = argparse.ArgumentParser(description="DualCam Particle Tracking Analysis")
        parser.add_argument('-c', '--config', type=pathlib.Path, required=True, 
                            help='Configuration file')
        parser.add_argument('-m', '--metadata', type=pathlib.Path, required=True, 
                            help="Metadate file")
        parser.add_argument('-t', '--threads', type=int, default=multiprocessing.cpu_count(), 
                            help='Number of threads to use (default: all available)'),
        parser.add_argument('-o', '--output', type=pathlib.Path, default="DCTracker-{}".format(datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")), 
                            help='Output directory')

        # if no arguments were passed, print the entire help
        if len(sys.argv) == 1:
            parser.print_help(file=sys.stderr)
            sys.exit(1)
        args = parser.parse_args()

        return args

    def _parse_config(self):
        """parse the configuration"""
        
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

    def _parse_metadata(self):
        """parse the metadata"""

        try:
            self.metadata = Metadata(self.metadata_file)
        except RuntimeError as e:
            self.logger.error(e, extra={'context': self.CONTEXT})
            sys.exit(1)
        self.logger.info("Parsed a metadata file ({} assays).".format(len(self.metadata.assays)), extra={'context': self.CONTEXT})

    def _prepare_pipeline(self):
        """prepare a list of each cells for each assay for the pipeline (PRIVATE)"""

        cells = []
        for assay in self.metadata.assays:
            assay.process_file_structure(self.config, self.output_dir)
            for cell in assay.cells:
                cells.append((cell, assay))
        return cells

    def _run_pipeline(self, cells):
        """run copixie pipeline"""
        self.logger.info("Starting CoPixie pipeline (DCTracker+Colocalize)", extra={'context': self.CONTEXT})
        if self.threads == 1:
            for cell in cells:
                self._pipeline_worker(cell)
        else:
            with multiprocessing.Pool(processes=self.threads) as pool:
                pool.map(self._pipeline_worker, cells)

    def _pipeline_worker(self, cell):
        """pipeline multiprocessing worker process (run each steps of the pipeline for a cell) (PRIVATE)"""
        
        try:
            DCTracker(cell)
            Colocalize(cell)
            self._write_json(cell)
        except InvalidCentroidError:
            self.logger.warning("Mask and tracking does not match for cell \"{}\".".format(cell.label), extra={'context': self.CONTEXT})


    def _write_json(self, cell):
        """write the cell information in JSON format in the output directory (PRIVATE)"""

        # Generate a dict that contains the JSON object
        metadata = {
            'Condition': cell[1].condition,
            'Replicate': cell[1].replicate[0], 
            'Label': cell[0].label,
            'PixelSize': self.config.pixel_size,
            'FrameInterval': self.config.frame_interval
        }

        # Write the metadata
        full_json_file_path = pathlib.Path(cell[0].output, 'Metadata.json')
        with open(full_json_file_path, "w") as h:
            json.dump(metadata, h, indent = 4)
