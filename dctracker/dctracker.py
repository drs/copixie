#!/usr/bin/env python3 

"""
Dual-Cam Live Cell Tracking Software
Samuel Drouin 2021
Version 0.0.0 | May 31, 2021
"""

import os
import sys
import configparser
import itertools
import operator
import math

from skimage import io
import numpy as np 
import pandas as pd

pd.options.mode.chained_assignment = None # Ignore 182: SettingWithCopyWarning
pd.options.display.max_rows = None


class DCTracker:
    """Run DCTracker from the command line"""

    def __init__(self, params):
        self.description = params[0]
        self.particles = params[1:]
        self.main()


    def main(self):
        # Process the input files to generate the tables
        i = 0
        tables = list()
        for particle in self.particles:
            name = particle['Name']

            if particle['MaskFile']:
                if particle['Static']:
                    table = self.mask_to_table(track_file=particle['TrackFile'], mask_file=particle['MaskFile'], pixel_size=particle['PixelSize'], static=True)
                else:
                    table = self.mask_to_table(track_file=particle['TrackFile'], mask_file=particle['MaskFile'], pixel_size=particle['PixelSize'])

                # Make sure the static image contains a single image 
                # Otherwise discard all but the first frame 
                if particle['Static']:
                    table = self.make_static(table, name)

                table.rename({'TRACK_ID': name}, axis=1, inplace=True)
            else:
                table = self.centroid_to_table(track_file=particle['TrackFile'], radius=particle['Radius'], pixel_size=particle['PixelSize'])

                if particle['Static']:
                    table = self.make_static(table, name)

                table.rename({'TRACK_ID': name}, axis=1, inplace=True)

            tables.append(table)

            i += 1

        # Count dict 
        count = dict()

        # Merge the tables 
        df = tables[0]
        name = list(df.columns.values)[2]
        count[name] = len(df[name].unique())

        i = 1
        for table in tables[1:]:
            name = list(table.columns.values)[2]
            count[name] = len(table[name].unique())
            if self.particles[i]['Static']:
                df = pd.merge(df, table, how="left", on=["X", "Y"], suffixes=("", "_y"))
                df.drop("FRAME_y", inplace=True, axis=1)
            else:
                df = pd.merge(df, table, how="left", on=["X", "Y", "FRAME"])
            i += 1

        df.drop(["X", "Y"], axis=1, inplace=True)

        cols = list(df.columns.values) 
        order = [cols[1]] + [cols[0]] + cols[2:]   

        df.drop_duplicates(inplace=True)

        df.sort_values(by=cols, inplace=True)
        df = pd.concat([df[df.fillna(method='ffill').duplicated(keep='last')], df[~df.fillna(method='ffill').duplicated(keep=False)]]) # ajouter les non-NaN
        df.sort_values(by=cols, inplace=True)
        df = df.reindex(columns=order)
        
        # Write the output 
        os.makedirs(self.description['Output'], exist_ok=True)
        full_output_file_path = os.path.join(self.description['Output'], 'DCTracker.csv')
        with open(full_output_file_path, 'w') as f:
            for name, c in count.items():
                f.write('#'+name+' '+str(c)+'\n')
            
            df.to_csv(f, index=False)


    def make_static(self, table, name):
        """Make a dataframe static by removing tracks with frame that are not 0"""

        if not table[table['FRAME'] > 0].empty:
            print("WARNING. Expected a static image but found multiple time frame for '{}'".format(name))
        table = table[table['FRAME'] == 0]
        return table


    def mask_to_table(self, track_file, mask_file, pixel_size, static=False):
        """Generate a hash from a mask"""

        tracks = self.parse_trackmate(track_file)
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
                try:
                    if mask[track_time][track_y][track_x] != 0: 
                        visited.add((track_x, track_y))
                except IndexError:
                    print(track)
                    print(mask_file)
                    print(track_time)
                    print(track_y)
                    print(track_x)
                    raise 

            completed = set()

            # Add each positive positions to the completed list
            while visited: # Done when there are no new nodes to visit
                v = visited.pop()
                completed.add(v)
                neighbour = [tuple(map(operator.add, v, x)) for x in neighbour_dist]
                for n in neighbour:
                    if not n in completed:
                        if static:
                            if mask[int(n[1])][int(n[0])] != 0:
                                visited.add(n)
                        else:
                            if mask[track_time][int(n[1])][int(n[0])] != 0:
                                visited.add(n)
            
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
            for k, g in duplicated.groupby(by = ['X', 'Y', 'FRAME']):
                selected.append(g.sort_values(by = ['DISTANCE']).iloc[0]) # Keep the track were the centroid is closer to the point 
            
            selected_df = pd.DataFrame(selected)
            selected_df.drop(labels='DISTANCE', axis=1, inplace=True)
            selected_df = selected_df.astype(int)
            frames = [unique, selected_df]
            df = pd.concat(frames)
        else:  
            df = unique

        return df 


    def parse_trackmate(self, track_file):
        """Parse a trackmate file"""

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


    def centroid_to_table(self, track_file, radius, pixel_size):
        """Generate a hash from a list of centroids"""
        tracks = self.parse_trackmate(track_file)

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


