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

"""analysis metadata processing related classes"""

import pathlib
import logging
from dataclasses import dataclass


class Metadata():
    """metadata file parser"""
    def __init__(self, file=None, in_dir=None):
        """metadata class constructor"""
        # metadata placeholder
        self.assays = []

        # list of sample (no metadata) or metadata file (condition,replicate,path,description+)
        if file:
            self._parse_metadata(file)
        # single directory input
        elif in_dir:
            self.assays.append(Assay(in_dir))
        else:
            raise RuntimeError("Cannot create an assay without metadata or input directory.")

    def _parse_metadata(self, metadata_file):
            """parse a metadata file. the metadata file is a tab separated file with 3 
            rows Condition,Replicate,Path (PRIVATE)"""
            header = None
            if not metadata_file.is_file():
                raise RuntimeError("Metadata file not found.")
            else:
                with open(metadata_file) as h:
                    for l in h:
                        # process the first header line, ignore subsequent comment lines
                        if l.startswith("#"):
                            if not header:
                                header = l[1:].strip().split(",")
                        # process the data
                        else:
                            l = l.strip().split(",")
                            # create the assay qualifier dict if the input is a multi-column
                            # metadata file
                            if len(l) > 1:
                                if header:
                                    qualifiers = dict(map(lambda i,j : (i,j) , header,l))
                                else:
                                    qualifiers = {'description': ','.join(l[:-1])}
                                self.assays.append(Assay(l[-1], qualifiers))
                            else:
                                self.assays.append(Assay(l[-1]))

            if len(self.assays) < 1:
                raise RuntimeError("Metadata file is empty.")


class Assay():
    """class that contains each assay information (metadata and cells)"""

    def __init__(self, path, qualifiers=None):
        """constructor for the assay class"""
        # TODO: add a check that the path is valid
        self.logger = logging.getLogger(__name__)

        self.path = pathlib.Path(path)
        self.qualifiers = qualifiers
        self.cells = []

    def process_file_structure(self, config):
        """process the file structure associated with the assay"""
        # we're getting the expected file name or relative path from the config
        # for the track file, since these file are required and should be present 
        # in all cells
        track_files = [channel.track_file for channel in config.channels]
        cell_dirs = set()
        
        # iterate over files in the assay path and fetch the cell folders 
        # (i.e., any folder contain any of the expected track files)
        for path in self.path.rglob('*'):
            if path.is_file():
                for track_file in track_files:
                    if path.match(track_file):
                        # we're getting the cell path by removing (1) the assay path
                        # and (2) the track file path to get the high level folder 
                        # that contains the cell files
                        suffix_len = len(pathlib.Path(track_file).parts)
                        prefix_len = len(self.path.parts)
                        cell_path = pathlib.Path(*path.parts[prefix_len:-suffix_len])
                        cell_dirs.add(cell_path)

        if not cell_dirs:
            msg = "No valid cell folder were found in folder \"{}\".".format(self.path)
            self.logger.warning(msg)

        cell_dirs = list(cell_dirs)
        cell_dirs.sort()

        # Parse the file structure
        for directory in cell_dirs:
            cell_full_path = pathlib.Path.joinpath(self.path, directory)
            label = str(directory)
            try:
                cell = Cell(cell_full_path, config, qualifiers=self.qualifiers, label=label)
            except RuntimeError:
                continue
            self.cells.append(cell)


class Cell():
    """class to process the cells folder. each cell folder is expected to contain the files 
    described in the configuration file."""

    def __init__(self, path, config, qualifiers, label):
        """constructor for the cell class"""
        self.logger = logging.getLogger(__name__)
        self.pixel_size = config.pixel_size
        self.frame_interval = config.frame_interval
        self.label = label
        self.qualifiers = qualifiers
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
                msg = "Folder \"{}\" does not contain the file \"{}\".".format(path, channel.track_file)
                self.logger.warning(msg)
                raise RuntimeError
            
            mask_file = None
            if channel.mask_file:
                mask_file = pathlib.Path(path, channel.mask_file)
                if not mask_file.is_file():
                    msg = "Folder \"{}\" does not contain the file \"{}\".".format(path, channel.mask_file)
                    self.logger.warning(msg)
                    raise RuntimeError

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
