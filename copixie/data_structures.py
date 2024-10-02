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

"""Data structures for assays and cells"""

import pathlib
from dataclasses import dataclass


class Assay():
    """class that contains each assay information (metadata and cells)"""

    def __init__(self, path, qualifiers=None):
        """constructor for the assay class"""
        # TODO: add a check that the path is valid
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
            raise RuntimeWarning("No valid cell folder were found. Nothing to analyze.")

        # Parse the file structure
        for directory in cell_dirs:
            cell_full_path = pathlib.Path.joinpath(self.path, directory)
            label = str(directory)
            try:
                cell = Cell(cell_full_path, config, qualifiers=self.qualifiers, label=label)
                self.cells.append(cell)
            except RuntimeWarning as w:
                # log warning that occured during a cell processing, but don't stop 
                # the program execution
                self.logger.warning(w, extra={'context': self.CONTEXT})
                pass


class Cell():
    """class to process the cells folder. each cell folder is expected to contain the files 
    described in the configuration file."""

    def __init__(self, path, config, qualifiers, label):
        """constructor for the cell class"""
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
