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

from copixie.data import Experiment, Assay, Cell
from copixie.config import Config

TEST_CONFIG_DIR="beads/config"
TEST_TRACKING_DIR="beads/tracking"
TEST_METADATA_DIR="beads/metadata"

def get_config_file(filename):
    """Return the path of a test file."""
    return pathlib.Path(TEST_CONFIG_DIR, filename).resolve()

def get_metadata_file(filename):
    """Return the path of a test file."""
    return pathlib.Path(TEST_METADATA_DIR, filename).resolve()


class ExperimentCases(unittest.TestCase):
    """Test the metadata file parser"""

    def test_experiment_metadata_missing(self):
        """Test parsing non-existing metadata file"""
        path = "/dummy/file"
        file = pathlib.Path(path).resolve()

        with self.assertRaises(RuntimeError) as e:
            Experiment().create_from_file(file)
        self.assertEqual(str(e.exception), "Metadata file not found.")

    def test_expreriment_metadata_parsing(self):
        """Test parsing metadata file"""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write("""POT1WT,1,/analysis/POT1WT/Rep1
POT1WT,2,/analysis/POT1WT/Rep1""".encode())
            tmp.seek(0)
            file = pathlib.Path(tmp.name).resolve()
            experiment = Experiment()
            experiment.create_from_file(file)
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
            experiment = Experiment()
            experiment.create_from_file(file)
            self.assertEqual(len(experiment), 2)
            assay = next(experiment)
            self.assertEqual(assay.qualifiers["cell line"], "POT1WT")
            self.assertEqual(assay.qualifiers["replicate"], "1")
            self.assertEqual(assay.path, pathlib.Path("/analysis/POT1WT/Rep1"))
            assay = next(experiment)
            self.assertEqual(assay.qualifiers["cell line"], "POT1WT")
            self.assertEqual(assay.qualifiers["replicate"], "2")
            self.assertEqual(assay.path, pathlib.Path("/analysis/POT1WT/Rep1"))

    def test_expreriment_sample_list(self):
        """Test parsing sample file"""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write("""/analysis/BeadsFiles/20240210
/analysis/BeadsFiles/20240211""".encode())
            tmp.seek(0)
            file = pathlib.Path(tmp.name).resolve()
            experiment = Experiment()
            experiment.create_from_file(file)
            self.assertEqual(len(experiment), 2)
            self.assertEqual(experiment[0].path, pathlib.Path("/analysis/BeadsFiles/20240210"))
            self.assertEqual(experiment[1].path, pathlib.Path("/analysis/BeadsFiles/20240211"))

    def test_experiment_input_dir(self):
        """Test metadata from input directory"""
        in_dir = "/analysis/BeadsFiles/20240210"
        experiment = Experiment()
        experiment.create_from_dir(in_dir)
        self.assertEqual(len(experiment), 1)
        self.assertEqual(experiment[0].path, pathlib.Path("/analysis/BeadsFiles/20240210"))


class AssayCases(unittest.TestCase):
    """Test the assay file structure construction"""

    def test_assay_file_structure(self):
        """Test the assay file structure analysis"""
        config = Config(get_config_file("488-561.cfg"))
        assay = Assay("beads/tracking")
        assay.process_file_structure(config)

        self.assertEqual(assay.path, pathlib.Path(TEST_TRACKING_DIR))
        self.assertEqual(len(assay), 2)

        cell = next(assay)
        self.assertEqual(cell.pixel_size, 0.133)
        self.assertEqual(cell.frame_interval, 0.06)
        self.assertEqual(cell.label, "Tracking_0102Non-matching")
        channel = cell.channels[0]
        self.assertEqual(channel.description, "488ch")
        self.assertEqual(channel.track_file, pathlib.Path(TEST_TRACKING_DIR, cell.label, "488/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)
        channel = cell.channels[1]
        self.assertEqual(channel.description, "561ch")
        self.assertEqual(channel.track_file, pathlib.Path(TEST_TRACKING_DIR, cell.label, "561/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)

        cell = next(assay)
        self.assertEqual(cell.pixel_size, 0.133)
        self.assertEqual(cell.frame_interval, 0.06)
        self.assertEqual(cell.label, "Tracking_0202Matching")
        channel = cell.channels[0]
        self.assertEqual(channel.description, "488ch")
        self.assertEqual(channel.track_file, pathlib.Path(TEST_TRACKING_DIR, cell.label, "488/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)
        channel = cell.channels[1]
        self.assertEqual(channel.description, "561ch")
        self.assertEqual(channel.track_file, pathlib.Path(TEST_TRACKING_DIR, cell.label, "561/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)   

    def test_assay_file_structure_empty(self):
        """Test the assay file structure analysis, one cell with missing files"""
        config = Config(get_config_file("488-561.cfg"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tracking_dir = pathlib.Path(tmp_dir)            
            assay = Assay(tmp_tracking_dir)

            with self.assertLogs('copixie') as cm:
                assay.process_file_structure(config)
                self.assertEqual(cm.output, ["WARNING:copixie.data:No valid cell folder were found in folder \"{}\".".format(tmp_tracking_dir)])

    def test_assay_file_structure_invalid(self):
        """Test the assay file structure analysis"""
        config = Config(get_config_file("488-561.cfg"))
        assay = Assay("/dummy/path")
        with self.assertLogs('copixie') as cm:
            assay.process_file_structure(config)
            self.assertEqual(cm.output, ["WARNING:copixie.data:No valid cell folder were found in folder \"/dummy/path\"."])


class CellCases(unittest.TestCase):
    """Test the cell construction"""

    def test_cell(self):
        """Test the cell construction"""
        config = Config(get_config_file("488-561.cfg"))
        cell = Cell(str(pathlib.Path(TEST_TRACKING_DIR, "Tracking_0102Non-matching")), 
                    config, qualifiers=None, label="Tracking_0102Non-matching")
        
        self.assertEqual(cell.pixel_size, 0.133)
        self.assertEqual(cell.frame_interval, 0.06)
        self.assertEqual(cell.label, "Tracking_0102Non-matching")
        self.assertIsNone(cell.qualifiers)
        channel = cell.channels[0]
        self.assertEqual(channel.description, "488ch")
        self.assertEqual(channel.track_file, pathlib.Path(TEST_TRACKING_DIR, cell.label, "488/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)
        channel = cell.channels[1]
        self.assertEqual(channel.description, "561ch")
        self.assertEqual(channel.track_file, pathlib.Path(TEST_TRACKING_DIR, cell.label, "561/spots.csv"))
        self.assertIsNone(channel.mask_file)
        self.assertEqual(channel.radius, 0.1)
        self.assertFalse(channel.static)

    def test_cell_no_track(self):
        """Test the cell construction, missing track file"""
        config = Config(get_config_file("488-561.cfg"))
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tracking_dir = pathlib.Path(tmp_dir, TEST_TRACKING_DIR)
            shutil.copytree(TEST_TRACKING_DIR, tmp_tracking_dir, dirs_exist_ok=True)
            os.remove(pathlib.Path(tmp_tracking_dir, "Tracking_0102Non-matching/488/spots.csv"))
            
            with self.assertRaises(RuntimeError):
                with self.assertLogs('copixie') as cm:
                    Cell(str(pathlib.Path(tmp_tracking_dir, "Tracking_0102Non-matching")), 
                         config, qualifiers=None, label="Tracking_0102Non-matching")
                    self.assertEqual(cm.output, ['WARNING:copixie.data:Folder "{}/Tracking_0102Non-matching" does not contain the file "488/spots.csv".'.format(tmp_tracking_dir)])
            
    def test_cell_no_mask(self):
        """Test the cell construction, missing mask file"""
        config = Config(get_config_file("488-561-withcircle.cfg"))
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tracking_dir = pathlib.Path(tmp_dir, TEST_TRACKING_DIR)
            shutil.copytree(TEST_TRACKING_DIR, tmp_tracking_dir, dirs_exist_ok=True)
            os.remove(pathlib.Path(tmp_tracking_dir, "Tracking_0202Matching/center/circle.tif"))
            
            with self.assertRaises(RuntimeError):
                with self.assertLogs('copixie') as cm:
                    Cell(str(pathlib.Path(tmp_tracking_dir, "Tracking_0202Matching")), 
                         config, qualifiers=None, label="Tracking_0202Matching")
                    self.assertEqual(cm.output, ['WARNING:copixie.data:Folder "{}/Tracking_0102Non-matching" does not contain the file "center/circle.tif".'.format(tmp_tracking_dir)])


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner)
