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

"""Tests CoPixie data handling"""

import unittest
import pathlib
import tempfile
import shutil
import os

import pandas as pd

from copixie.data import Experiment, Assay, Cell, Channel
from copixie.config import Config

TEST_DIR = "data"
MOCK_BEADS = {
        "Beads/Tracking_0102Non-matching/488": ["spots.csv"],
        "Beads/Tracking_0102Non-matching/561": ["spots.csv"],
        "Beads/Tracking_0202Matching/488": ["spots.csv"],
        "Beads/Tracking_0202Matching/561": ["spots.csv"],
        "Beads/Tracking_0202Matching/border": ["border.tif", "border.csv"],
    }

def get_path(name):
    """return the path of a test data file or directory"""
    return os.path.join(TEST_DIR, name)


class ExperimentCases(unittest.TestCase):
    """Test the metadata file parser"""

    def test_experiment_metadata_missing(self):
        """Test parsing non-existing metadata file"""
        path = "/dummy/file"
        file = pathlib.Path(path).resolve()

        with self.assertRaises(RuntimeError) as e:
            Experiment().from_file(file, None)
        self.assertEqual(str(e.exception), "Metadata file not found.")

    def test_experiment_metadata_parsing(self):
        """Test parsing metadata file"""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write("""POT1WT,1,/analysis/POT1WT/Rep1
POT1WT,2,/analysis/POT1WT/Rep1""".encode())
            tmp.seek(0)
            file = pathlib.Path(tmp.name).resolve()
            experiment = Experiment.from_file(file, None)
            self.assertEqual(len(experiment), 2)
            assay = next(experiment)
            self.assertEqual(assay.qualifiers["description"], "POT1WT,1")
            self.assertEqual(assay.path, pathlib.Path("/analysis/POT1WT/Rep1"))
            assay = next(experiment)
            self.assertEqual(assay.qualifiers["description"], "POT1WT,2")
            self.assertEqual(assay.path, pathlib.Path("/analysis/POT1WT/Rep1"))

    def test_experiment_metadata_parsing_header(self):
        """Test parsing metadata file, header"""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write("""#cell line,replicate,path
POT1WT,1,/analysis/POT1WT/Rep1
POT1WT,2,/analysis/POT1WT/Rep1""".encode())
            tmp.seek(0)
            file = pathlib.Path(tmp.name).resolve()
            experiment = Experiment.from_file(file, None)
            self.assertEqual(len(experiment), 2)
            assay = next(experiment)
            self.assertEqual(assay.qualifiers["cell line"], "POT1WT")
            self.assertEqual(assay.qualifiers["replicate"], "1")
            self.assertEqual(assay.path, pathlib.Path("/analysis/POT1WT/Rep1"))
            assay = next(experiment)
            self.assertEqual(assay.qualifiers["cell line"], "POT1WT")
            self.assertEqual(assay.qualifiers["replicate"], "2")
            self.assertEqual(assay.path, pathlib.Path("/analysis/POT1WT/Rep1"))

    def test_experiment_sample_list(self):
        """Test parsing sample file"""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write("""/analysis/BeadsFiles/20240210
/analysis/BeadsFiles/20240211""".encode())
            tmp.seek(0)
            file = pathlib.Path(tmp.name).resolve()
            experiment = Experiment.from_file(file, None)
            self.assertEqual(len(experiment), 2)
            self.assertEqual(experiment[0].path, pathlib.Path("/analysis/BeadsFiles/20240210"))
            self.assertEqual(experiment[1].path, pathlib.Path("/analysis/BeadsFiles/20240211"))
    
    def test_experiment_input_dir(self):
        """Test metadata from input directory"""
        in_dir = "/analysis/BeadsFiles/20240210"
        experiment = Experiment.from_dir(in_dir, None)
        self.assertEqual(len(experiment), 1)
        self.assertEqual(experiment[0].path, pathlib.Path("/analysis/BeadsFiles/20240210"))


class AssayCases(unittest.TestCase):
    """Test the assay file structure construction"""
    def setUp(self):
        """setup the test"""
        # create a mock beads file structure
        self.test_dir = tempfile.TemporaryDirectory().name
        for directory, files in MOCK_BEADS.items():
            path = pathlib.Path(self.test_dir, directory)
            path.mkdir(parents=True)
            for file in files:
                file_path = pathlib.Path(self.test_dir, directory, file)
                open(file_path, 'w').close()
        # load the config 
        self.config = Config(get_path("488_561.cfg"))

    def tearDown(self):
        """clean up the test"""
        shutil.rmtree(self.test_dir)

    def test_assay_file_structure(self):
        """Test the assay file structure analysis"""
        assay = Assay(self.test_dir, config=self.config)

        self.assertEqual(assay.path, pathlib.Path(self.test_dir))
        self.assertEqual(len(assay), 2)

        cell = next(assay)
        self.assertEqual(cell.pixel_size, 0.133)
        self.assertEqual(cell.frame_interval, 0.06)
        self.assertEqual(cell.label, "Beads/Tracking_0102Non-matching")
        channel = cell.channels[0]
        self.assertEqual(channel.description, "488ch")
        self.assertEqual(channel.track_file, pathlib.Path(self.test_dir, cell.label, "488/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)
        channel = cell.channels[1]
        self.assertEqual(channel.description, "561ch")
        self.assertEqual(channel.track_file, pathlib.Path(self.test_dir, cell.label, "561/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)

        cell = next(assay)
        self.assertEqual(cell.pixel_size, 0.133)
        self.assertEqual(cell.frame_interval, 0.06)
        self.assertEqual(cell.label, "Beads/Tracking_0202Matching")
        channel = cell.channels[0]
        self.assertEqual(channel.description, "488ch")
        self.assertEqual(channel.track_file, pathlib.Path(self.test_dir, cell.label, "488/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)
        channel = cell.channels[1]
        self.assertEqual(channel.description, "561ch")
        self.assertEqual(channel.track_file, pathlib.Path(self.test_dir, cell.label, "561/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)   

    def test_assay_file_structure_empty(self):
        """Test the assay file structure analysis, one cell with missing files"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tracking_dir = pathlib.Path(tmp_dir)
            with self.assertLogs('copixie') as cm:
                Assay(tmp_tracking_dir, config=self.config)
                self.assertEqual(cm.output, ["WARNING:copixie.data:No valid cell folder were found in folder \"{}\".".format(tmp_tracking_dir)])

    def test_assay_file_structure_invalid(self):
        """Test the assay file structure analysis"""
        with self.assertLogs('copixie') as cm:
            assay = Assay("/dummy/path", config=self.config)
            self.assertEqual(cm.output, ["WARNING:copixie.data:No valid cell folder were found in folder \"/dummy/path\"."])


class CellCases(unittest.TestCase):
    """Test the cell construction"""

    def setUp(self):
        """setup the test"""
        # create a mock beads file structure
        self.test_dir = tempfile.TemporaryDirectory().name
        for directory, files in MOCK_BEADS.items():
            path = pathlib.Path(self.test_dir, directory)
            path.mkdir(parents=True)
            for file in files:
                file_path = pathlib.Path(self.test_dir, directory, file)
                open(file_path, 'w').close()

    def tearDown(self):
        """clean up the test"""
        shutil.rmtree(self.test_dir)


    def test_cell(self):
        """Test the cell construction"""
        config = Config(get_path("488_561.cfg"))
        cell = Cell(pathlib.Path(self.test_dir, "Beads/Tracking_0102Non-matching"), 
                    config, qualifiers=None, label="Beads/Tracking_0102Non-matching")
        
        self.assertEqual(cell.pixel_size, 0.133)
        self.assertEqual(cell.frame_interval, 0.06)
        self.assertEqual(cell.label, "Beads/Tracking_0102Non-matching")
        self.assertIsNone(cell.qualifiers)
        channel = cell.channels[0]
        self.assertEqual(channel.description, "488ch")
        self.assertEqual(channel.track_file, pathlib.Path(self.test_dir, cell.label, "488/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)
        channel = cell.channels[1]
        self.assertEqual(channel.description, "561ch")
        self.assertEqual(channel.track_file, pathlib.Path(self.test_dir, cell.label, "561/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)

    def test_cell_no_track(self):
        """Test the cell construction, missing track file"""
        config = Config(get_path("488_561.cfg"))
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tracking_dir = pathlib.Path(tmp_dir, self.test_dir)
            os.remove(pathlib.Path(self.test_dir, "Beads/Tracking_0102Non-matching/488/spots.csv"))
            
            with self.assertRaises(RuntimeError):
                with self.assertLogs('copixie') as cm:
                    Cell(pathlib.Path(tmp_tracking_dir, "Tracking_0102Non-matching"), 
                         config, qualifiers=None, label="Tracking_0102Non-matching")
                    self.assertEqual(cm.output, ['WARNING:copixie.data:Folder "{}/Tracking_0102Non-matching" does not contain the file "488/spots.csv".'.format(tmp_tracking_dir)])
            
    def test_cell_no_mask(self):
        """Test the cell construction, missing mask file"""
        config = Config(get_path("488_561_border.cfg"))
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tracking_dir = pathlib.Path(tmp_dir, self.test_dir)
            os.remove(pathlib.Path(self.test_dir, "Beads/Tracking_0202Matching/border/border.tif"))
            
            with self.assertRaises(RuntimeError):
                with self.assertLogs('copixie') as cm:
                    Cell(pathlib.Path(tmp_tracking_dir, "Tracking_0202Matching"), 
                         config, qualifiers=None, label="Tracking_0202Matching")
                    self.assertEqual(cm.output, ['WARNING:copixie.data:Folder "{}/Tracking_0102Non-matching" does not contain the file "center/circle.tif".'.format(tmp_tracking_dir)])


class ChannelCases(unittest.TestCase):
    """Test the channel"""

    def test_radius_table_radius_1px(self):
        """Test table construction from track and radius, radius 1px"""
        track_filename = "spots_0102_track_4.csv"
        track_file = get_path(track_filename)
        channel = Channel("488ch", track_file, 0.133, radius=0.01)

        self.assertEqual(channel.description, "488ch")
        self.assertEqual(channel.track_file, track_file)
        self.assertEqual(channel.pixel_size, 0.133)
        self.assertEqual(channel.radius, 0.01)
        self.assertFalse(channel.static)

        table = channel.get_table()
        columns = ["X", "Y", "488ch", "FRAME"]
        data = [(127, 87, 4, 3), (127, 85, 4, 13)]
        df = pd.DataFrame(data, columns=columns)
        pd.testing.assert_frame_equal(table, df)

    def test_radius_table_radius_3px(self):
        """Test table construction from track and radius, radius 3px"""
        track_filename = "spots_0102_track_4.csv"
        track_file = get_path(track_filename)
        channel = Channel("488ch", track_file, 0.133, radius=0.1)

        self.assertEqual(channel.description, "488ch")
        self.assertEqual(channel.track_file, track_file)
        self.assertEqual(channel.pixel_size, 0.133)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)

        table = channel.get_table()
        columns = ["X", "Y", "488ch", "FRAME"]
        data = [(126, 86, 4, 3),
                (126, 87, 4, 3),
                (126, 88, 4, 3),
                (127, 86, 4, 3),
                (127, 87, 4, 3), 
                (127, 88, 4, 3),
                (128, 86, 4, 3),
                (128, 87, 4, 3),
                (128, 88, 4, 3),
                (126, 84, 4, 13),
                (126, 85, 4, 13),
                (126, 86, 4, 13),
                (127, 84, 4, 13),
                (127, 85, 4, 13),
                (127, 86, 4, 13),
                (128, 84, 4, 13),
                (128, 85, 4, 13),
                (128, 86, 4, 13)]
        df = pd.DataFrame(data, columns=columns)
        pd.testing.assert_frame_equal(table, df)

    def test_mask_table(self):
        """Test table construction from track and mask"""
        track_filename = "telo_centroid.csv"
        track_file = get_path(track_filename)
        mask_filename = "telo_mask.tif"
        mask_file = get_path(mask_filename)
        channel = Channel("Telomere", track_file, 0.133, mask_file=mask_file)

        self.assertEqual(channel.description, "Telomere")
        self.assertEqual(channel.track_file, track_file)
        self.assertEqual(channel.pixel_size, 0.133)
        self.assertEqual(channel.mask_file, mask_file)
        self.assertFalse(channel.static)

        table = channel.get_table()
        columns = ["X", "Y", "Telomere", "FRAME"]
        data = [(2, 4, 1, 0),
                (1, 2, 1, 0),
                (3, 4, 1, 0),
                (2, 1, 1, 0),
                (4, 3, 1, 0),
                (3, 1, 1, 0),
                (1, 4, 1, 0),
                (4, 2, 1, 0),
                (2, 3, 1, 0),
                (3, 3, 1, 0),
                (2, 2, 1, 0),
                (3, 2, 1, 0),
                (1, 3, 1, 0),
                (2, 1, 1, 1),
                (4, 3, 1, 1),
                (3, 1, 1, 1),
                (4, 2, 1, 1),
                (2, 3, 1, 1),
                (3, 3, 1, 1),
                (2, 2, 1, 1),
                (3, 2, 1, 1)]
        df = pd.DataFrame(data, columns=columns)
        pd.testing.assert_frame_equal(table, df)

    def test_mask_table_static(self):
        """Test table construction from track and mask, static"""
        track_filename = "telo_centroid.csv"
        track_file = get_path(track_filename)
        mask_filename = "telo_mask.tif"
        mask_file = get_path(mask_filename)
        channel = Channel("Telomere", track_file, 0.133, mask_file=mask_file, static=True)

        self.assertEqual(channel.description, "Telomere")
        self.assertEqual(channel.track_file, track_file)
        self.assertEqual(channel.pixel_size, 0.133)
        self.assertEqual(channel.mask_file, mask_file)
        self.assertTrue(channel.static)

        table = channel.get_table()
        columns = ["X", "Y", "Telomere"]
        data = [(2, 4, 1),
                (1, 2, 1),
                (3, 4, 1),
                (2, 1, 1),
                (4, 3, 1),
                (3, 1, 1),
                (1, 4, 1),
                (4, 2, 1),
                (2, 3, 1),
                (3, 3, 1),
                (2, 2, 1),
                (3, 2, 1),
                (1, 3, 1)]
        df = pd.DataFrame(data, columns=columns)
        pd.testing.assert_frame_equal(table, df)

    def test_mask_table_edge(self):
        """Test table construction from track and mask, static, at the edge of the frame"""
        track_filename = "telo_centroid.csv"
        track_file = get_path(track_filename)
        mask_filename = "telo_mask_edge.tif"
        mask_file = get_path(mask_filename)
        channel = Channel("Telomere", track_file, 0.133, mask_file=mask_file, static=True)

        self.assertEqual(channel.description, "Telomere")
        self.assertEqual(channel.track_file, track_file)
        self.assertEqual(channel.pixel_size, 0.133)
        self.assertEqual(channel.mask_file, mask_file)
        self.assertTrue(channel.static)

        table = channel.get_table()
        columns = ["X", "Y", "Telomere"]
        data = [(1, 2, 1),
                (2, 1, 1),
                (4, 1, 1),
                (3, 1, 1),
                (1, 1, 1),
                (2, 0, 1),
                (4, 2, 1),
                (3, 0, 1),
                (2, 3, 1),
                (3, 3, 1),
                (2, 2, 1),
                (3, 2, 1),
                (1, 3, 1)]
        df = pd.DataFrame(data, columns=columns)
        pd.testing.assert_frame_equal(table, df)

    def test_mask_table_centroid_outside(self):
        """Test table construction from track and mask, centroid outside of the mask"""
        track_filename = "telo_centroid_outside.csv"
        track_file = get_path(track_filename)
        mask_filename = "telo_mask.tif"
        mask_file = get_path(mask_filename)
        channel = Channel("Telomere", track_file, 0.133, mask_file=mask_file)

        self.assertEqual(channel.description, "Telomere")
        self.assertEqual(channel.track_file, track_file)
        self.assertEqual(channel.pixel_size, 0.133)
        self.assertEqual(channel.mask_file, mask_file)
        self.assertFalse(channel.static)

        with self.assertRaises(IndexError):
            channel.get_table()


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner)
