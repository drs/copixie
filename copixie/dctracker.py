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

"""DCTracker module that generate a colocalisation matrix from the tracks and masks. """

import logging 

import numpy as np 
import pandas as pd

pd.options.mode.chained_assignment = None # Ignore 182: SettingWithCopyWarning
pd.options.display.max_rows = None

# get the logger
logger = logging.getLogger(__name__)

def DCTracker(cell):
    assert len(cell.channels) > 1
    df = cell.channels[0].get_table()
    i = 1
    while i < len(cell.channels):
        if cell.channels[i].static:
            df = pd.merge(df, cell.channels[i].get_table(), how="outer", on=["X", "Y"])
        else:
            df = pd.merge(df, cell.channels[i].get_table(), how="outer", on=["X", "Y", "FRAME"])
        i += 1

    # keep the particle combinaisons with/without interaction
    df.drop(["X", "Y"], axis=1, inplace=True)
    df.drop_duplicates(inplace=True)

    # order the dataframe with frame as the first column
    cols = list(df.columns.values) 
    order = [cols[1]] + [cols[0]] + cols[2:]   
    df = df.reindex(columns=order)
    df.sort_values(by=order, inplace=True)

    # remove rows with NA in the frame (static images with no colocalisation)
    df.dropna(subset=['FRAME'], inplace=True)

    # keep rows with NaN in any columns only if the values in the other columns are not present elsewhere in the table
    frames = []
    for _,g in df.groupby(by="FRAME"):
        # create a boolean mask of rows that have NaN values
        nan_mask = g.isna().any(axis=1)

        # create a boolean mask of rows that have unique values in at least one column
        unique_masks = []
        for col in g.columns[1:]:
            unique_mask = g[col].isin(g[col].value_counts()[g[col].value_counts()==1].index)
            unique_masks.append(unique_mask)
        keep_mask = np.any(unique_masks, axis=0)

        # combine the masks and apply them to the DataFrame
        keep = ~nan_mask | keep_mask
        g = g[keep].reset_index(drop=True)
        frames.append(g)
    df = pd.concat(frames, axis=0)

    # Change the particle ID type to Int64 (to accept NaN) to simplify the output
    for col in cols:
        df[col] = df[col].astype('Int64')

    return df
