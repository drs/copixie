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


import pathlib
import pandas


class Colocalize:
    """
    Parse DCTracker colocalisation matrix to a simpler format
    """

    def __init__(self, params):
        self.description = params[0]
        self.particles = params[1:]
        self.main()

    
    def main(self):
        full_dctracker_file_path = pathlib.Path(self.description['Output'], 'DCTracker.csv')
        dctracker = pandas.read_csv(full_dctracker_file_path, sep=',', comment='#')

        particle_names = []
        for particle in self.particles:
            particle_names.append(particle["Name"])
        
        # Parse the colocalisation and generate the simplified colocalisation table
        interactions = []
        # Initial grouping with same particle ID 
        for k, g in dctracker.groupby(by = particle_names, dropna=False):   
            # Split the group when the frame are non-consecutive
            for _, sg in g.groupby(g["FRAME"].diff().gt(1).cumsum()):
                start_frame = int(sg.iloc[0]["FRAME"])
                end_frame = int(sg.iloc[-1]["FRAME"])
                length = end_frame-start_frame
                interactions.append(list(k) + [str(start_frame), str(end_frame)])
        colocalisation = pandas.DataFrame(interactions)
        colocalisation.columns = particle_names + ["Start.Frame", "End.Frame"]

        # Change the particle ID type to Int64 (to accept NaN) to simplify the output
        for col in particle_names:
            colocalisation[col] = colocalisation[col].astype('Int64')
        
        # Write the output
        full_output_file_path = pathlib.Path(self.description['Output'], 'Colocalize.csv')
        with open(full_output_file_path, 'w', newline='') as f:
            colocalisation.to_csv(f, index=False)
