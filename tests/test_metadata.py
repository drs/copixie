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

"""Tests CoPixie metadata file handling"""

import unittest
import pathlib
import tempfile

from copixie.metadata import Metadata


class MetadataCases(unittest.TestCase):
    """Test the metadata file parser"""

    def test_metadata_missing(self):
        """Test parsing non-existing metadata file"""
        path = "/dummy/file"
        file = pathlib.Path(path).resolve()

        with self.assertRaises(RuntimeError) as e:
            Metadata(file=file)
        self.assertEqual(str(e.exception), "Metadata file not found.")

    def test_metadata_empty(self):
        """Test parsing empty metadata file"""
        with tempfile.NamedTemporaryFile() as tmp:
            file = pathlib.Path(tmp.name).resolve()
            with self.assertRaises(RuntimeError) as e:
                Metadata(file=file)
            self.assertEqual(str(e.exception), "Metadata file is empty.")

    def test_metadata(self):
        """Test parsing metadata file"""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write("""POT1WT,1,/analysis/POT1WT/Rep1
POT1WT,2,/analysis/POT1WT/Rep1""".encode())
            tmp.seek(0)
            file = pathlib.Path(tmp.name).resolve()
            metadata = Metadata(file=file)
            self.assertEqual(len(metadata.assays), 2)
            self.assertEqual(metadata.assays[0].qualifiers["description"], "POT1WT,1")
            self.assertEqual(metadata.assays[0].path, pathlib.Path("/analysis/POT1WT/Rep1"))
            self.assertEqual(metadata.assays[1].qualifiers["description"], "POT1WT,2")
            self.assertEqual(metadata.assays[1].path, pathlib.Path("/analysis/POT1WT/Rep1"))

    def test_metadata_header(self):
        """Test parsing metadata file, header"""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write("""#cell line,replicate,path
POT1WT,1,/analysis/POT1WT/Rep1
POT1WT,2,/analysis/POT1WT/Rep1""".encode())
            tmp.seek(0)
            file = pathlib.Path(tmp.name).resolve()
            metadata = Metadata(file=file)
            self.assertEqual(len(metadata.assays), 2)
            self.assertEqual(metadata.assays[0].qualifiers["cell line"], "POT1WT")
            self.assertEqual(metadata.assays[0].qualifiers["replicate"], "1")
            self.assertEqual(metadata.assays[0].path, pathlib.Path("/analysis/POT1WT/Rep1"))
            self.assertEqual(metadata.assays[1].qualifiers["cell line"], "POT1WT")
            self.assertEqual(metadata.assays[1].qualifiers["replicate"], "2")
            self.assertEqual(metadata.assays[1].path, pathlib.Path("/analysis/POT1WT/Rep1"))

    def test_sample_list(self):
        """Test parsing sample file"""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write("""/analysis/BeadsFiles/20240210
/analysis/BeadsFiles/20240211""".encode())
            tmp.seek(0)
            file = pathlib.Path(tmp.name).resolve()
            metadata = Metadata(file=file)
            self.assertEqual(len(metadata.assays), 2)
            self.assertEqual(metadata.assays[0].path, pathlib.Path("/analysis/BeadsFiles/20240210"))
            self.assertEqual(metadata.assays[1].path, pathlib.Path("/analysis/BeadsFiles/20240211"))

    def test_input_dir(self):
        """Test metadata from input directory"""
        in_dir = "/analysis/BeadsFiles/20240210"
        metadata = Metadata(in_dir=in_dir)
        self.assertEqual(len(metadata.assays), 1)
        self.assertEqual(metadata.assays[0].path, pathlib.Path("/analysis/BeadsFiles/20240210"))


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner)
