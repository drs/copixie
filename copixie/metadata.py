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

"""Metadata file parser"""

from .data_structures import Assay


class Metadata():
    def __init__(self, file=None, in_dir=None):
        # metadata placeholder
        self.assays = []

        # list of sample (no metadata) or metadata file (condition,replicate,path,description+)
        if file:
            self._parse_metadata(file)
        # single directory input
        elif in_dir:
            self.assays.append(Assay(in_dir))
        else:
            raise RuntimeError("Cannot create an assay without metadata or input directory.")

    def _parse_metadata(self, metadata_file):
            """parse a metadata file. the metadata file is a tab separated file with 3 
            rows Condition,Replicate,Path (PRIVATE)"""
            header = None
            if not metadata_file.is_file():
                raise RuntimeError("Metadata file not found.")
            else:
                with open(metadata_file) as h:
                    for l in h:
                        # process the first header line, ignore subsequent comment lines
                        if l.startswith("#"):
                            if not header:
                                header = l[1:].strip().split(",")
                        # process the data
                        else:
                            l = l.strip().split(",")
                            # create the assay qualifier dict if the input is a multi-column
                            # metadata file
                            if len(l) > 1:
                                if header:
                                    qualifiers = dict(map(lambda i,j : (i,j) , header,l))
                                else:
                                    qualifiers = {'description': ','.join(l[:-1])}
                                self.assays.append(Assay(l[-1], qualifiers))
                            else:
                                self.assays.append(Assay(l[-1]))
                
            if len(self.assays) < 1:
                raise RuntimeError("Metadata file is empty.")
