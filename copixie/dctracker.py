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

"""initial DCTracker software that analyse tracks and masks to generate a colocalisation matrix. """

import itertools
import operator
import math
import logging 

from skimage import io
import numpy as np 
import pandas as pd

pd.options.mode.chained_assignment = None # Ignore 182: SettingWithCopyWarning
pd.options.display.max_rows = None

# TODO: handle cases where the centroid is outside of the image

# get the logger
logger = logging.getLogger(__name__)

def dctracker(cell):
    cell = cell[0]
    # Determine the number of frames in the movie. This information is required to process static particles properly
    # It is expected (but not required) that non-static particle have the same number of frame
    frame_count = []
    for channel in cell.channels:
        if not channel.static:
            tracks = _parse_trackmate(track_file=channel.track_file)
        frame_count.append(tracks['FRAME'].max()+1)
        
    if frame_count:
        frame_count = max(frame_count)
    else: # Should only occur if not particle are movies 
        frame_count = 1 

    # Process the input files to generate the tables
    i = 0
    tables = list()
    for channel in cell.channels:
        name = channel.description

        if channel.mask_file:
            if channel.static:
                table = _mask_to_table(track_file=channel.track_file, mask_file=channel.mask_file, pixel_size=cell.pixel_size, static=True)
                table = _make_static(table, name) # Remove tracks where frame is not 0
                table = _expand_static_table(table, frame_count)
            else:
                table = _mask_to_table(track_file=channel.track_file, mask_file=channel.mask_file, pixel_size=cell.pixel_size)
        else:
            table = centroid_to_table(track_file=channel.track_file, radius=channel.radius, pixel_size=cell.pixel_size)

        table.rename({'TRACK_ID': name}, axis=1, inplace=True)
        tables.append(table)
        i += 1

    # Merge the tables 
    df = tables[0]
    name = list(df.columns.values)[2]

    i = 1
    for table in tables[1:]:
        name = list(table.columns.values)[2]
        df = pd.merge(df, table, how="outer", on=["X", "Y", "FRAME"])
        i += 1

    # Keep the particle combinaisons with/without interaction
    df.drop(["X", "Y"], axis=1, inplace=True)
    df.drop_duplicates(inplace=True)

    # Order the dataframe with frame as the first column
    cols = list(df.columns.values) 
    order = [cols[1]] + [cols[0]] + cols[2:]   
    df = df.reindex(columns=order)
    df.sort_values(by=order, inplace=True)

    # Keep rows with NaN in any columns only if the values in the other columns are not present elsewhere in the table
    frames = []
    for k,g in df.groupby(by="FRAME"):
        # Create a boolean mask of rows that have NaN values
        nan_mask = g.isna().any(axis=1)

        # Create a boolean mask of rows that have unique values in at least one column
        unique_masks = []
        for col in g.columns[1:]:
            unique_mask = g[col].isin(g[col].value_counts()[g[col].value_counts()==1].index)
            unique_masks.append(unique_mask)
        keep_mask = np.any(unique_masks, axis=0)

        # Combine the masks and apply them to the DataFrame
        keep = ~nan_mask | keep_mask
        g = g[keep].reset_index(drop=True)
        frames.append(g)
    df = pd.concat(frames, axis=0)

    # Change the particle ID type to Int64 (to accept NaN) to simplify the output
    for col in cols:
        df[col] = df[col].astype('Int64')

    return df


def _mask_to_table(track_file, mask_file, pixel_size, static=False):
    """Generate a hash from a mask (PRIVATE)"""

    tracks = _parse_trackmate(track_file)
    mask = io.imread(mask_file)

    x = []
    y = []
    ids = []
    times = []
    centroids = dict()

    neighbour_dist = [(-1, 0), (0, -1), (0, 0), (0, 1), (1, 0)] # Neighbour distances are +/- 1 excluding diagonals
    for track in tracks.iterrows():
        track_id = int(track[1]['TRACK_ID'])
        track_time = int(track[1]['FRAME'])
        track_x = int(round(track[1]['POSITION_X']/pixel_size))
        track_y = int(round(track[1]['POSITION_Y']/pixel_size))

        if not track_time in centroids:
            centroids[track_time] = dict()
        centroids[track_time][track_id] = (track_x, track_y)

        visited = set()
            
        # Ignore centroids when the mask does not contain a particle at the centroid center
        if static:
            if mask[track_y][track_x] != 0:
                visited.add((track_x, track_y))
        else:
            if mask[track_time][track_y][track_x] != 0: 
                visited.add((track_x, track_y))

        completed = set()

        # Add each positive positions to the completed list
        while visited: # Done when there are no new nodes to visit
            v = visited.pop()
            completed.add(v)
            neighbour = [tuple(map(operator.add, v, x)) for x in neighbour_dist]
            for n in neighbour:
                if not n in completed:
                    if static:
                        try:
                            if mask[int(n[1])][int(n[0])] != 0:
                                visited.add(n)
                        except IndexError:
                            pass 
                    else:
                        try:
                            if mask[track_time][int(n[1])][int(n[0])] != 0:
                                visited.add(n)
                        except IndexError:
                            pass

        # Add the results to the lists
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

    return df 


def _make_static(table, name):
    """make a dataframe static by removing tracks with frame that are not 0 (PRIVATE)"""
    if not table[table['FRAME'] > 0].empty:
        logger.warning("Expected a static image but found multiple time frame for '{}'".format(name))
    table = table[table['FRAME'] == 0]
    return table


def _expand_static_table(table, frame_count):
    """expand a static table (with a singe frame) to match the number of frame of the movie (PRIVATE)"""
    df = pd.concat([table]*frame_count, ignore_index=True)
    frame = []
    for i in range(0,frame_count):
        frame.extend([i]*len(table))
    df["FRAME"] = frame 

    return df


def _parse_trackmate(track_file):
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


def centroid_to_table(track_file, radius, pixel_size):
    """generate a hash from a list of centroids (PRIVATE)"""
    tracks = _parse_trackmate(track_file)

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
        
    df = pd.DataFrame(list(zip(x, y, ids, times)), columns=['X', 'Y', 'TRACK_ID', 'FRAME'])
    return df 
