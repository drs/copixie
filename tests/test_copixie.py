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

"""Tests CoPixie colocalization analysis"""

import unittest
import os

import pandas as pd
import numpy as np

from copixie.config import Config
from copixie.data import Cell
from copixie.dctracker import DCTracker
from copixie.colocalize import Colocalize

TEST_DIR = "data"

def get_path(name):
    """return the path of a test data file or directory"""
    return os.path.join(TEST_DIR, name)


class TestDCTracker(unittest.TestCase):
    """Test DCTracker particle colocalisation analysis"""

    def test_dctracker_centroid_centroid(self):
        """Test DCTracker, centroid centroid"""
        config = Config(get_path("488_561.cfg"))
        cell_dir = get_path("Tracking_0202_Matching")
        cell = Cell(cell_dir, config, qualifiers=None, label="")
        dctracker_df = DCTracker(cell)
        columns = ["FRAME", "488ch", "561ch"]
        data = [(0, 0, 1),
                (1, 0, 1),
                (2, 0, 1),
                (3, 0, 1),
                (4, 0, 1),
                (5, 0, 1),
                (6, 0, 1),]
        expected_df = pd.DataFrame(data, columns=columns).astype('Int32')
        pd.testing.assert_frame_equal(expected_df, dctracker_df.reset_index(drop=True))

    def test_dctracker_centroid_mask(self):
        """Test DCTracker, centroid mask"""
        config = Config(get_path("hTR_hTERT.cfg"))
        cell_dir = get_path("15_5TT_pot1-WT_puro-01_AcquisitionBlock1_pt1/cell1")
        cell = Cell(cell_dir, config, qualifiers=None, label="")
        dctracker_df = DCTracker(cell)
        columns = ["FRAME", "hTR", "Telomere"]
        data = [(0, 0, 0),
                (1, 0, 0),
                (2, 0, 0),
                (3, 0, 0),
                (4, 0, 0)]
        expected_df = pd.DataFrame(data, columns=columns).astype('Int32')
        pd.testing.assert_frame_equal(expected_df, dctracker_df.reset_index(drop=True))

    def test_dctracker_centroid_centroid_mask(self):
        """Test DCTracker, centroid centroid mask"""
        config = Config(get_path("488_561_border.cfg"))
        cell_dir = get_path("Tracking_0202_Matching")
        cell = Cell(cell_dir, config, qualifiers=None, label="")
        dctracker_df = DCTracker(cell)
        columns = ["FRAME", "488ch", "561ch", "region"]
        data = [(0, 0, 1),
                (1, 0, 1),
                (2, 0, 1),
                (3, 0, 1, 2222),
                (4, 0, 1, 2222),
                (5, 0, 1, 2222),
                (6, 0, 1, 2222),
                ]
        expected_df = pd.DataFrame(data, columns=columns).astype('Int32')
        pd.testing.assert_frame_equal(expected_df, dctracker_df.reset_index(drop=True))


class TestColocalize(unittest.TestCase):
    """Test Colocalize particle colocalisation analysis"""

    def test_colocalize_centroid_centroid(self):
        """Test Colocalize, centroid centroid"""
        config = Config(get_path("488_561.cfg"))
        cell_dir = get_path("Tracking_0202_Matching")
        cell = Cell(cell_dir, config, qualifiers=None, label="")
        colocalize_df = Colocalize(cell, DCTracker(cell))
        columns = ["488ch", "561ch", "Start.Frame", "End.Frame"]
        data = [(0, 1, 0, 6)]
        expected_df = pd.DataFrame(data, columns=columns).astype('Int32')
        pd.testing.assert_frame_equal(expected_df, colocalize_df.reset_index(drop=True))

    def test_colocalize_centroid_mask(self):
        """Test Colocalize, centroid mask"""
        config = Config(get_path("hTR_hTERT.cfg"))
        cell_dir = get_path("15_5TT_pot1-WT_puro-01_AcquisitionBlock1_pt1/cell1")
        cell = Cell(cell_dir, config, qualifiers=None, label="")
        colocalize_df = Colocalize(cell, DCTracker(cell))
        columns = ["hTR", "Telomere", "Start.Frame", "End.Frame"]
        data = [(0, 0, 0, 4)]
        expected_df = pd.DataFrame(data, columns=columns).astype('Int32')
        pd.testing.assert_frame_equal(expected_df, colocalize_df.reset_index(drop=True))

    def test_colocalize_centroid_centroid_mask(self):
        """Test Colocalize, centroid centroid mask"""
        config = Config(get_path("488_561_border.cfg"))
        cell_dir = get_path("Tracking_0202_Matching")
        cell = Cell(cell_dir, config, qualifiers=None, label="")
        colocalize_df = Colocalize(cell, DCTracker(cell))
        columns = ["488ch", "561ch", "region", "Start.Frame", "End.Frame"]
        data = [(0, 1, 2222, 3, 6),
                (0, 1, np.nan, 0, 2)]
        expected_df = pd.DataFrame(data, columns=columns).astype('Int32')
        pd.testing.assert_frame_equal(expected_df, colocalize_df.reset_index(drop=True))

    def test_colocalize_multiple(self):
        """Test Colocalize, multiple particles"""
        config = Config(get_path("488_561_circle.cfg"))
        cell_dir = get_path("Beads")
        cell = Cell(cell_dir, config, qualifiers=None, label="")
        colocalize_df = Colocalize(cell, DCTracker(cell))
        columns = ["488ch", "561ch", "region", "Start.Frame", "End.Frame"]
        data = [(0, 0, 999, 0, 7),
                (0, 6, 999, 8, 19),
                (1, np.nan, 999, 0, 6),
                (4, 5, np.nan, 0, 6),
                (7, np.nan, np.nan, 7, 13),
                (8, 7, np.nan, 8, 17),
                (14, 10, np.nan, 13, 19),
                (14, np.nan, np.nan, 12, 12),
                (15, np.nan, np.nan, 11, 17),
                (np.nan, 2, np.nan, 0, 12),
                (np.nan, 3, np.nan, 0, 7),
                (np.nan, 7, np.nan, 7, 7),
                (np.nan, 9, np.nan, 13, 19)]
        expected_df = pd.DataFrame(data, columns=columns).astype('Int32')
        pd.testing.assert_frame_equal(expected_df, colocalize_df.reset_index(drop=True))



if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner)
