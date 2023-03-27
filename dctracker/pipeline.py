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

from dctracker.dctracker import DCTracker
from dctracker.dctracker import InvalidCentroidError
from dctracker.colocalize import Colocalize
from dctracker.log import Logger

class Pipeline():
    """
    This class runs DCTracker analysis pipeline
    """

    def __init__(self, params):
        # Run the pipeline in multiprocessing
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            pool.map(self.run_analysis, params)


    def run_analysis(self, params):
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
