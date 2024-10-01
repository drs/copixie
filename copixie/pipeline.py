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

import multiprocessing
import json
import subprocess
import logging 
import pathlib 

from .dctracker import DCTracker, InvalidCentroidError
from .colocalize import Colocalize
from .log import Logger


class UnhandledPostprocessingError(RuntimeError):
    """Raise if an unhandled exception occurs during the postprocessing""" 


class CalledProcessError(RuntimeError):
    """Raise if the post-processing process exits with a non-zero error code""" 


class Pipeline():
    """
    This class runs DCTracker analysis pipeline
    """

    def __init__(self, cells, postprocessing=[]):
        # Start the logger
        self.logger = logging.getLogger()
        self.CONTEXT = "Pipeline"

        # Run the pipeline in multiprocessing
        self.logger.info("Starting CoPixie pipeline (CoPixie+Colocalize)", extra={'context': self.CONTEXT})
        for cell in cells:
            self.run_dctracker(cell)
        #with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        #    pool.map(self.run_dctracker, params)

        # Run the post-processing tasks
        #if postprocessing:
        #    self.logger.info("Running post-processing tasks", extra={'context': self.CONTEXT})
        #    output_dir = postprocessing[0]
        #    postprocessing_cmd = postprocessing[1]
        #    self.run_postprocessing(cells, output_dir, postprocessing_cmd)


    def run_dctracker(self, cell):
        """
        Run the complete analysis pipeline : DCTracker, Colocalize and write the cell JSON file

        Arguments:
            params: DCTracker module parameters
        """

        try:
            DCTracker(cell)
            Colocalize(cell)
            self.write_json(cell)
        except InvalidCentroidError:
            self.logger.warning("Mask and tracking does not match for cell \"{}\".".format(cell.label), extra={'context': self.CONTEXT})


    def write_json(self, cell):
        """Write the cell information in JSON format in the output directory"""

        # Generate a dict that contains the JSON object
        metadata = {
            'Condition': cell[1].condition,
            'Replicate': cell[1].replicate[0], 
            'Label': cell[0].label,
            #'PixelSize': cell[1].config.pixel_size,
            #'FrameInterval': cell[1].config.frame_interval
        }

        # Write the metadata
        full_json_file_path = pathlib.Path(cell[0].output, 'Metadata.json')
        with open(full_json_file_path, "w") as h:
            json.dump(metadata, h, indent = 4)


    def run_postprocessing(self, params, output_dir, cmd):
        """
        Run the post-processing command on DCTracker output directory
        """
        if cmd:
            # List all the cells analyzed by DCTracker 
            cells = []
            for cell in params:
                cells.append(str(cell[0]['Output']))
            
            # Try to run the postprocessing command
            try:
                result = subprocess.run(cmd.split(' ') + [output_dir, ','.join(cells)], capture_output=True)
            except FileNotFoundError as e:
                raise
            except Exception as e: # Not handled in this version, will be handled by the main program
                raise UnhandledPostprocessingError(e)
            
            if result.returncode != 0:
                msg = "Post-processing command failed with the error : \n {}.".format(result.stderr.decode('utf-8'))
                raise CalledProcessError(msg)
