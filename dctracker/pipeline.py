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

import multiprocessing
import os
import json
import subprocess
import logging 

from dctracker.dctracker import DCTracker
from dctracker.dctracker import InvalidCentroidError
from dctracker.colocalize import Colocalize
from dctracker.log import Logger


class UnhandledPostprocessingError(RuntimeError):
    """Raise if an unhandled exception occurs during the postprocessing""" 


class CalledProcessError(RuntimeError):
    """Raise if the post-processing process exits with a non-zero error code""" 


class Pipeline():
    """
    This class runs DCTracker analysis pipeline
    """

    def __init__(self, params, postprocessing=[]):
        # Start the logger
        self.logger = logging.getLogger()
        self.CONTEXT = "Pipeline"

        # Run the pipeline in multiprocessing
        self.logger.info("Starting DCTracker pipeline (DCTracker+Colocalize)", extra={'context': self.CONTEXT})
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            pool.map(self.run_dctracker, params)

        # Run the post-processing tasks
        if postprocessing:
            self.logger.info("Running post-processing tasks", extra={'context': self.CONTEXT})
            output_dir = postprocessing[0]
            postprocessing_cmd = postprocessing[1]
            self.run_postprocessing(params, output_dir, postprocessing_cmd)


    def run_dctracker(self, params):
        """
        Run the complete analysis pipeline : DCTracker, Colocalize and write the cell JSON file

        Arguments:
            params: DCTracker module parameters
        """

        try:
            DCTracker(params)
            Colocalize(params)
            self.write_json(params)
        except InvalidCentroidError:
            Logger().logger.warning("Mask and tracking does not match for cell \"{}\".".format(params[0]['Label']), extra={'context': self.context})


    def write_json(self, params):
        """Write the cell information in JSON format in the output directory"""

        # Generate a dict that contains the JSON object
        description = params[0]
        metadata = {
            'Condition': description['Condition'],
            'Replicate': description['Replicate'][0], 
            'Label': description['Label'],
            'PixelSize': description['PixelSize'],
            'FrameInterval': description['FrameInterval']
        }

        # Write the metadata
        full_json_file_path = os.path.join(description['Output'], 'Metadata.json')
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
                cells.append(cell[0]['Output'])
            
            # Try to run the postprocessing command
            try:
                result = subprocess.run(cmd.split(' ') + [output_dir, ','.join(cells)], capture_output=True)
            except FileNotFoundError as e:
                raise
            except Exception as e: # Not handled in this version, will be handled by the main program
                raise UnhandledPostprocessingError(e)
            
            if result.returncode != 0:
                msg = "Post-processing command failed with the error {}.".format(result.stderr.decode('utf-8'))
                raise CalledProcessError(msg)
