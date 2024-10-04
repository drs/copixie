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
import itertools
import operator
import math

import imageio.v3 as iio
import pandas as pd


class Experiment():
    """the experiment class contains all the assay of a CoPixie analysis.
    the experiment is cerated from a metadata file or a directory"""

    def __init__(self, assays=[], config=None):
        """experiment class constructor"""
        self._assays = []
        for assay in assays:
            self._assays.append(Assay(assay[0], config, qualifiers=assay[1]))

        # initialize index for iteration
        self._index = 0  

    def __iter__(self):
        """reset the iterator and return the object itself"""
        self._index = 0
        return self

    def __next__(self):
        """return the next assay or raise StopIteration"""
        if self._index < len(self._assays):
            result = self._assays[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration  # End of the list reached

    def __getitem__(self, index):
        """return the assay the a specific index"""
        return self._assays[index]

    def __len__(self):
        """return experiment length"""
        return len(self._assays)

    @classmethod
    def from_file(cls, file, config):
        """create experiment from a metadata file"""
        assays = cls._parse_metadata(file)
        return cls(assays, config)
    
    @classmethod
    def from_dir(cls, in_dir, config):
        """create experiment from an input directory"""
        assays = [[in_dir, None],]
        return cls(assays, config)

    @staticmethod
    def _parse_metadata(file):
        """parse a metadata file. the metadata file is a tab separated file with 3 
        rows Condition,Replicate,Path (PRIVATE)"""
        assays = []
        header = None
        if not file.is_file():
            raise RuntimeError("Metadata file not found.")
        else:
            with open(file) as h:
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
                            assays.append([l[-1], qualifiers])
                        else:
                            assays.append([l[-1], None])

        return assays

    def get_cells(self):
        """return a list of all the cells of all the assays (PRIVATE)"""
        cells = []
        for assay in self._assays:
            for cell in assay:
                cells.append(cell)
        return cells


class Assay():
    """the assay class describes a single metadata record or input.
    an assay can include one or more cells"""

    def __init__(self, path, config=None, qualifiers=None):
        """constructor for the assay class"""
        self.logger = logging.getLogger(__name__)

        self.path = pathlib.Path(path)
        self.config = config
        self.qualifiers = qualifiers
        self._cells = []
        if config:
            self._process_file_structure()

        # initialize index for iteration
        self._index = 0

    def __iter__(self):
        """reset the iterator and return the object itself"""
        self._index = 0
        return self

    def __next__(self):
        """return the next assay or raise StopIteration"""
        if self._index < len(self._cells):
            result = self._cells[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration  # End of the list reached

    def __getitem__(self, index):
        """return the assay the a specific index"""
        return self._cells[index]

    def __len__(self):
        """return experiment length"""
        return len(self._cells)

    def _process_file_structure(self):
        """process the file structure associated with the assay (PRIVATE)"""
        # we're getting the expected file name or relative path from the config
        # for the track file, since these file are required and should be present 
        # in all cells
        track_files = [channel.track_file for channel in self.config.channels]
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
            cell_full_path = pathlib.Path(self.path, directory)
            label = str(directory)
            try:
                cell = Cell(cell_full_path, self.config, qualifiers=self.qualifiers, label=label)
            except RuntimeError:
                continue
            self._cells.append(cell)


class Cell():
    """cell class. the cells are an individual record of the assay.
    cells are constructed as described in the configuration file."""

    def __init__(self, path, config, qualifiers, label):
        """constructor for the cell class"""
        self.logger = logging.getLogger(__name__)
        self.pixel_size = config.pixel_size
        self.frame_interval = config.frame_interval
        self.label = label
        self.qualifiers = qualifiers
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

            channels.append(Channel(descr, track_file, self.pixel_size, mask_file, radius, static))
        
        return channels


class Channel():
    """class to store the channel information for the cells"""

    def __init__(self, description, track_file, pixel_size, mask_file=None, radius=None, static=False):
        self.logger = logging.getLogger(__name__)
        self.description = description
        self.track_file = track_file
        self.pixel_size = pixel_size
        self.mask_file = mask_file
        self.radius = radius
        self.static = static

    def get_table(self):
        """create and return a table for the channel from the track file, radius or mask file"""

        # create the object table using the centroid (track file) and mask file
        if self.mask_file:
            table = self._mask_to_table(track_file=self.track_file, mask_file=self.mask_file, pixel_size=self.pixel_size, static=self.static)
        # create the object table using the centroid (track file) and radius
        else:
            assert self.radius is not None
            table = self._centroid_to_table(track_file=self.track_file, radius=self.radius, pixel_size=self.pixel_size)

        table.rename({'TRACK_ID': self.description}, axis=1, inplace=True)

        return table

    def _mask_to_table(self, track_file, mask_file, pixel_size, static=False):
        """Generate a hash from a mask (PRIVATE)"""

        tracks = self._parse_trackmate(track_file)

        mask = iio.imread(mask_file)
        if static:
            # resise static mask with more than 1 frames to a single frame
            if len(mask.shape) == 3:
                mask = [mask[0]]
            # add a 3rd dimension to the mask
            else:
                mask = [mask]

        x = []
        y = []
        ids = []
        times = []
        centroids = dict()

        neighbour_dist = [(-1, 0), (0, -1), (0, 0), (0, 1), (1, 0)] # neighbour distances are +/- 1 excluding diagonals
        for track in tracks.iterrows():
            # process only the first frame of static movies
            if static and track[1]['FRAME'] > 0:
                continue

            track_id = int(track[1]['TRACK_ID'])
            track_time = int(track[1]['FRAME'])
            track_x = int(round(track[1]['POSITION_X']/pixel_size))
            track_y = int(round(track[1]['POSITION_Y']/pixel_size))

            if not track_time in centroids:
                centroids[track_time] = dict()
            centroids[track_time][track_id] = (track_x, track_y)

            visited = set()
            
            # ignore centroids when the mask does not contain a particle at the centroid center
            try:
                if mask[track_time][track_y][track_x] != 0: 
                    visited.add((track_x, track_y))
            except IndexError as e:
                raise IndexError("Centroid outside of the mask file.").with_traceback(e.__traceback__)

            completed = set()

            # add each positive positions to the completed list
            while visited: # done when there are no new nodes to visit
                v = visited.pop()
                completed.add(v)
                neighbour = [tuple(map(operator.add, v, x)) for x in neighbour_dist]
                for n in neighbour:
                    if not n in completed:
                        try:
                            if mask[track_time][int(n[1])][int(n[0])] != 0:
                                visited.add(n)
                        except IndexError:
                            pass

            # add the results to the lists
            x.extend([c[0] for c in completed])
            y.extend([c[1] for c in completed])
            ids.extend(itertools.repeat(track_id, len(completed)))
            times.extend(itertools.repeat(track_time, len(completed)))

        df = pd.DataFrame(list(zip(x, y, ids, times)), columns=['X', 'Y', 'TRACK_ID', 'FRAME'])

        # Filter overlapping particles
        unique = df.drop_duplicates(subset = ['X', 'Y', 'FRAME'], keep = False)
        duplicated = df[df.duplicated(subset = ['X', 'Y', 'FRAME'], keep = False)]

        # Distance between the potential centroid and any position attributed to the particule with the centroid
        if not duplicated.empty:
            duplicated['DISTANCE'] = duplicated.apply(lambda x: math.sqrt((x['X']-centroids[x['FRAME']][x['TRACK_ID']][0])**2 + (x['Y']-centroids[x['FRAME']][x['TRACK_ID']][1])**2), axis=1)

            selected = list()
            for _, g in duplicated.groupby(by = ['X', 'Y', 'FRAME']):
                selected.append(g.sort_values(by = ['DISTANCE']).iloc[0]) # Keep the track were the centroid is closer to the point 

            selected_df = pd.DataFrame(selected)
            selected_df.drop(labels='DISTANCE', axis=1, inplace=True)
            selected_df = selected_df.astype(int)
            frames = [unique, selected_df]
            df = pd.concat(frames)
        else:  
            df = unique

        # remove the frame column if the image is static
        if static:
            df.drop(labels='FRAME', axis=1, inplace=True)

        return df

    def _parse_trackmate(self, track_file):
        """parse a trackmate file (PRIVATE)"""

        tracks = pd.read_csv(track_file, sep=',', header = 0, usecols=['TRACK_ID', 'POSITION_X', 'POSITION_Y', 'FRAME'])
            
        # In version 7 TrackMate added three additional header rows
        # To maintain compatibility with version 6, header rows are removed by removing rows 
        # where the track id is not numeric
        # Conversion to string before numeric check to avoid error with float/int types
        tracks = tracks[tracks["TRACK_ID"].astype(str).str.isnumeric()]

        # TrackMate header changed the columns type to str. 
        # Changing numeric columns types back to int
        tracks['POSITION_X'] = pd.to_numeric(tracks['POSITION_X'])
        tracks['POSITION_Y'] = pd.to_numeric(tracks['POSITION_Y'])
        tracks['FRAME'] = pd.to_numeric(tracks['FRAME'])

        return tracks

    def _centroid_to_table(self, track_file, radius, pixel_size):
        """generate a hash table from a list of centroids (PRIVATE)"""

        tracks = self._parse_trackmate(track_file)

        x = []
        y = []
        ids = []
        times = []
        radius_px = int(round(radius/pixel_size))
        particle_sphere = list(itertools.product(range(-radius_px, radius_px+1), range(-radius_px, radius_px+1)))
            
        for track in tracks.iterrows():
            track_id = int(track[1]['TRACK_ID'])
            track_time = int(track[1]['FRAME'])
            track_x = int(round(track[1]['POSITION_X']/pixel_size))
            track_y = int(round(track[1]['POSITION_Y']/pixel_size))

            centroid = (track_x, track_y)

            particle = [tuple(map(operator.add, centroid, x)) for x in particle_sphere]

            # Add the results to the lists
            x.extend([p[0] for p in particle])
            y.extend([p[1] for p in particle])
            ids.extend(itertools.repeat(track_id, len(particle)))
            times.extend(itertools.repeat(track_time, len(particle)))
            
        return pd.DataFrame(list(zip(x, y, ids, times)), columns=['X', 'Y', 'TRACK_ID', 'FRAME']) 
