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

"""Tests CoPixie configuration file handling"""

import unittest
import tempfile
import os
import pathlib

from copixie.config import Config

# test case files are in the config directory
TEST_DIR = "data"

def get_file(filename):
    """Return the path of a test file."""
    return os.path.join(TEST_DIR, filename)


class ConfigCases(unittest.TestCase):
    """Test the config file parser"""

    def test_config_missing(self):
        """Test parsing non-existing config file"""
        file = "/dummy/file"

        with self.assertRaises(RuntimeError) as e:
            Config(file)
        self.assertEqual(str(e.exception), "Configuration file not found.")

    def test_config_empty(self):
        """Test parsing empty config file"""
        with tempfile.NamedTemporaryFile() as tmp:
            with self.assertRaises(RuntimeError) as e:
                Config(tmp.name)
            self.assertEqual(str(e.exception), "Configuration file is empty.")

    def test_config_single_channel(self):
        """Test parsing config, single channel (488.cfg)"""
        file = get_file("488.cfg")
        with self.assertRaises(RuntimeError) as e:
            Config(file)
        self.assertEqual(str(e.exception), "Configuration file does not contain two input sections.")

    def test_config_two_channel(self):
        """Test parsing a config, two channels (488_561.cfg)"""
        file = get_file("488_561.cfg")
        config = Config(file)
        self.assertEqual(config.pixel_size, 0.133)
        self.assertEqual(config.frame_interval, 0.06)
        self.assertEqual(len(config.channels), 2)
        self.assertEqual(config.channels[0].track_file, "488/spots.csv")
        self.assertFalse(config.channels[0].static)
        self.assertEqual(config.channels[0].radius, 0.1)
        self.assertIsNone(config.channels[0].mask_file)
        self.assertEqual(config.channels[1].track_file, "561/spots.csv")
        self.assertFalse(config.channels[1].static)
        self.assertEqual(config.channels[1].radius, 0.1)
        self.assertIsNone(config.channels[1].mask_file)

    def test_config_two_channel_postprocessing(self):
        """Test parsing a config, two channels, postprocessing (hTR_hTERT.cfg)"""
        file = get_file("hTR_hTERT.cfg")
        config = Config(file)
        self.assertEqual(config.pixel_size, 0.133)
        self.assertEqual(config.frame_interval, 0.1)
        self.assertEqual(len(config.channels), 2)
        self.assertEqual(config.channels[0].track_file, "htr/spots.csv")
        self.assertFalse(config.channels[0].static)
        self.assertEqual(config.channels[0].radius, 0.1)
        self.assertIsNone(config.channels[0].mask_file)
        self.assertEqual(config.channels[1].track_file, "telo/spots.csv")
        self.assertFalse(config.channels[1].static)
        self.assertIsNone(config.channels[1].radius)
        self.assertEqual(config.channels[1].mask_file, "../mask.tif")
        self.assertEqual(config.post_processing, "python3 /analysis/DCTracker/AggregatePy_Development/aggregate-hTR-telomere.py")

    def test_config_missing_required(self):
        """Test parsing config, missing a required parameter"""
        with tempfile.NamedTemporaryFile() as tmp:
            filename = "hTR_hTERT.cfg"
            with open(os.path.join(TEST_DIR, filename)) as r_h:
                for l in r_h:
                    if not l.startswith("PixelSize"):
                        tmp.write(l.encode())
            tmp.seek(0)
            with self.assertRaises(RuntimeError) as e:
                Config(tmp.name)
            self.assertEqual(str(e.exception), "Required parameter \"General/PixelSize\" is missing from the config file.")

    def test_config_incorrect_value(self):
        """Test parsing config, incorrect option value"""
        with tempfile.NamedTemporaryFile() as tmp:
            filename = "hTR_hTERT.cfg"
            with open(os.path.join(TEST_DIR, filename)) as r_h:
                for l in r_h:
                    if not l.startswith("    Static"):
                        tmp.write(l.encode())
                    else:
                        tmp.write(b"    Static = invalid\n")
            tmp.seek(0)
            with self.assertRaises(RuntimeError) as e:
                Config(tmp.name)
            self.assertEqual(str(e.exception), 
                             "Parameter \"Input/Telomere/Static\" is set to \"invalid\" which is not one of the allowed values. Please set the value to be one of the following options : \"'y', 'yes', 'Yes', 'n', 'no', 'No', default='no'\""
            )
        
    def test_config_incorrect_type(self):
        """Test parsing config, incorrect option type"""
        with tempfile.NamedTemporaryFile() as tmp:
            filename = "hTR_hTERT.cfg"
            with open(os.path.join(TEST_DIR, filename)) as r_h:
                for l in r_h:
                    if not l.startswith("PixelSize"):
                        tmp.write(l.encode())
                    else:
                        tmp.write(b"PixelSize = invalid\n")
            tmp.seek(0)
            with self.assertRaises(RuntimeError) as e:
                Config(tmp.name)
            self.assertEqual(str(e.exception), 
                             "Parameter \"General/PixelSize\" is set to \"invalid\" which is not one of the allowed types. Please set the value to be of type : \"float\""
            )


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner)
