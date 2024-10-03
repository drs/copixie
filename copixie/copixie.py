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
import logging
from platform import python_version

import configobj

from .config import Config
from .data import Experiment
from .dctracker import dctracker
from .colocalize import colocalize
from .__version__ import __version__


class CoPixie():
    """CoPixie colocalization analysis pipeline"""

    def __init__(self):
        # parse the command line arguments
        args = self._get_arguments()
        self.config_file = pathlib.Path(args.config).resolve()
        self.output_dir = pathlib.Path(args.output).resolve()
        self.metadata_file = pathlib.Path(args.metadata).resolve()
        self.threads = args.threads

        # initialize the logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s  [%(name)s]  %(levelname)s    %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # run the main analysis pipeline
        self.main()
    
    def main(self):
        # start logging
        self.logger.info("Starting CoPixie (version {})".format(__version__))
        self.logger.debug("Python version: {}".format(python_version()))

        # run the analysis pipeline
        config = self._parse_config()
        self.logger.info("Parsed the configuration file.")

        experiment = self._parse_metadata()
        experiment.create_cells(config)
        self.logger.info("Loaded the experiment from the metadata file (found {} assays).".format(len(experiment.assays)))

        self._create_output_dir()
        cells = experiment.get_cells()
        results = self._run_pipeline(cells)
        self._write_results(results)
        self.logger.info("Done.")

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
            config = Config(self.config_file)
        except configobj.ConfigObjError as e:
            msg = "Invalid configuragion file. Make sure the configuration is correct. Complete error message (for debugging): \n" + str(e)
            self.logger.error(msg)
            sys.exit(1)
        except RuntimeError as e:
            self.logger.error(e)
            sys.exit(1)

        return config

    def _parse_metadata(self):
        """parse the metadata"""

        metadata = Experiment()
        try:
            metadata.create_from_file(self.metadata_file)
        except RuntimeError as e:
            self.logger.error(e)
            sys.exit(1)
        
        return metadata

    def _create_output_dir(self):
        """create the output directory. this is done early to avoid computing the results
        if the output directory is not writable"""
        try:
            self.output_dir.mkdir(parents=True)
        except FileExistsError:
            msg = "Output path points to an existing directory."
            self.logger.error(msg)
            sys.exit(1)

    def _run_pipeline(self, cells):
        """run copixie pipeline"""
        self.logger.info("Starting CoPixie pipeline (DCTracker+Colocalize)")
        if self.threads == 1:
            result = []
            for cell in cells:
                result.append(self._pipeline_worker(cell))
        else:
            with multiprocessing.Pool(processes=self.threads) as pool:
                result = pool.map(self._pipeline_worker, cells)
        
        return result

    def _pipeline_worker(self, cell):
        """pipeline multiprocessing worker process (run each steps of the pipeline for a cell) (PRIVATE)"""
        dctracker_df = dctracker(cell)
        colocalize_df = colocalize(cell, dctracker_df)
        return (cell, colocalize_df)

    def _write_results(self, results):
        """write dctracker and colocalize tables (PRIVATE)"""
        with open(pathlib.Path(self.output_dir, "CoPixie.csv"), "w") as h:
            for result in results:
                cell = result[0][0]
                colocalize_df = result[1]

                # create the qualifier description string
                descr_str = "# LABEL:{} \n".format(cell.label)
                if cell.qualifiers:
                    for k,v in cell.qualifiers.items():
                        descr_str += "{}: {} ".format(k,v)
                descr_str = descr_str[:-1] # remove the last space
                
                h.write(descr_str)
                colocalize_df.to_csv(h, index=False)
