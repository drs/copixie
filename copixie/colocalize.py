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

"""Simplify DCTracker colocalisation matrix"""

import pandas as pd

    
def Colocalize(cell, df):
    channel_names = []
    for channel in cell.channels:
        channel_names.append(channel.description)

    # Parse the colocalisation and generate the simplified colocalisation table
    interactions = []

    # initial grouping with same particle ID 
    for k, g in df.groupby(by = channel_names, dropna=False):
        # split the group when the frame are non-consecutive (diff > 1 between frames)
        # we need to bfill to include the first value of a group and fillna with one 
        # so that tables with a single frame are included
        for _, sg in g.groupby(g["FRAME"].diff().gt(1).cumsum().bfill(limit=1).fillna(1)):
            start_frame = int(sg.iloc[0]["FRAME"])
            end_frame = int(sg.iloc[-1]["FRAME"])
            interactions.append(list(k) + [str(start_frame), str(end_frame)])
    colocalisation = pd.DataFrame(interactions)
    colocalisation.columns = channel_names + ["Start.Frame", "End.Frame"]

    # cast the particle IDs to Int32 instead of int32 to accept NaN
    colocalisation = colocalisation.astype('Int32')
    colocalisation.reset_index(inplace=True, drop=True)

    return colocalisation
