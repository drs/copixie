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


from .data_structures import Assay


class Metadata():
    def __init__(self, metadata_file):
        # metadata placeholder
        self.assays = []
        self._parse_metadata(metadata_file)

    def _parse_metadata(self, metadata_file):
            """parse a metadata file. the metadata file is a tab separated file with 3 
            rows Condition,Replicate,Path (PRIVATE)"""
            if not metadata_file.is_file():
                raise RuntimeError("Configuration file not found.")
            else:
                with open(metadata_file) as h:
                    for l in h:
                        # ignore blank line and comment line (line starting with #)
                        if not l.startswith("#") or l.strip() == "":
                            l = l.strip().split(",")

                            # validate that the metadata is conform with the expected format
                            if len(l) != 3:
                                raise RuntimeError("Metadata contains {} columns but 3 were expected. Please refer to the documentation for the metadata file format.".format(len(l)))
                            #if l[0] in self.assays:
                            #    raise RuntimeError("Duplicate entry found in metadata file.")
                            
                            # Add the entry to the metadata dict 
                            self.assays.append(Assay(l[2], l[0], l[1], ','.join(l[3:])))
            
            if len(self.assays) < 1:
                raise RuntimeError("Metadata file is empty.")
