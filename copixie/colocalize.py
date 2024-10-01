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

"""Parse DCTracker colocalisation matrix to a simpler format"""

import pandas as pd

    
def colocalize(cell, dctracker):
    cell = cell[0]
    channel_names = []
    for channel in cell.channels:
        channel_names.append(channel.description)
        
    # Parse the colocalisation and generate the simplified colocalisation table
    interactions = []
    # Initial grouping with same particle ID 
    for k, g in dctracker.groupby(by = channel_names, dropna=False):   
        # Split the group when the frame are non-consecutive
        for _, sg in g.groupby(g["FRAME"].diff().gt(1).cumsum()):
            start_frame = int(sg.iloc[0]["FRAME"])
            end_frame = int(sg.iloc[-1]["FRAME"])
            length = end_frame-start_frame
            interactions.append(list(k) + [str(start_frame), str(end_frame)])
    colocalisation = pd.DataFrame(interactions)
    colocalisation.columns = channel_names + ["Start.Frame", "End.Frame"]

    # Change the particle ID type to Int64 (to accept NaN) to simplify the output
    for col in channel_names:
        colocalisation[col] = colocalisation[col].astype('Int64')

    return colocalisation
