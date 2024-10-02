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

"""Configuration file parser"""

import io 

from configobj import ConfigObj, flatten_errors
from validate import Validator, VdtValueError, VdtTypeError

CONFIG_SPECS = """
[General]
PixelSize = float
FrameInterval = float

[Input]
    [[__many__]]
    Static = option('y', 'yes', 'Yes', 'n', 'no', 'No', default='no')
    TrackFile = string
    Radius = float(default=None)
    MaskFile = string(default=None)
"""

class Config():
    """class to parse a config file and store the parameters for the CoPixie analysis"""

    def __init__(self, cfg_file):
        """constructor for the Config class"""
        cfg = self._load_config(cfg_file)
        self.pixel_size = cfg['General']['PixelSize']
        self.frame_interval = cfg['General']['FrameInterval']

        self.post_processing = None
        if 'Post-processing' in cfg:
            self.post_processing = cfg['Post-processing']['Command']
        
        self.channels = []
        for k,v in cfg['Input'].items():
            self.channels.append(ChannelConfig(k,v))

    def _load_config(self, cfg_file): 
        """load a configuration file using ConfigObj. The file is validated using the spec
        described in CONFIG_SPECS (PRIVATE)"""

        # validate that the config file exists 
        if not cfg_file.is_file():
            msg = "Configuration file not found."
            raise RuntimeError(msg)
        
        # parse the configuration file
        config = ConfigObj(str(cfg_file), configspec=io.StringIO(CONFIG_SPECS))
        if not config:
            msg = "Configuration file is empty."
            raise RuntimeError(msg)
        validator = Validator()
        results = config.validate(validator, preserve_errors=True)

        # configuration must contains at least two inputs
        if len(self._list_particle_key(config)) < 2:
            msg = "Configuration file does not contain two input sections."
            raise RuntimeError(msg)

        # validate that either a mask or radius is provided for each particle
        for particle in self._list_particle_key(config):
            if not config['Input'][particle]["Radius"] and not config['Input'][particle]["MaskFile"]: 
                msg = "No mask file or particle radius is provided in the configuration for the particle \"{}\".".format(particle)
                raise RuntimeError(msg)

        # return explicit error messages from the validator results. Only VdtTypeError and
        # VdtValueError are caught as there are no validation that would return
        # VdtValueTooSmallError, VdtValueTooBigError, VdtValueTooShortError or VdtValueTooLongError
        for entry in flatten_errors(config, results):
            section_list, key, error = entry
            if error == False:
                msg = "Required parameter \"{}\" is missing from the config file.".format(self._section_key_string(section_list, key))
                raise RuntimeError(msg)

            if key is not None:
                key_string = self._config_item(config, section_list, key)

                if isinstance(error, VdtValueError):
                    option_string = self._config_item(config.configspec, section_list, key)[7:-1]
                    msg = "Parameter \"{}\" is set to \"{}\" which is not one of the allowed values. Please set the value to be one of the following options : \"{}\"".format(self._section_key_string(section_list, key), key_string, option_string)
                    raise RuntimeError(msg)

                if isinstance(error, VdtTypeError):
                    type_string = self._config_item(config.configspec, section_list, key)
                    msg = "Parameter \"{}\" is set to \"{}\" which is not one of the allowed types. Please set the value to be of type : \"{}\"".format(self._section_key_string(section_list, key), key_string, type_string)
                    raise RuntimeError(msg)

        return config

    def _list_particle_key(self, config):
        """returns a list of the input sub-sections keys (i.e., the particules labels) (PRIVATE)"""
        return [i for i in config['Input'] if isinstance(config['Input'][i], dict)]

    def _section_key_string(self, section_list, key):
        """returns a string with the complete section and key for a config item. Sections are 
        separated by backslash. (PRIVATE)"""
        return '/'.join([x for x in section_list + [key] if x is not None])

    def _config_item(self, config, section_list, key):
        """extract an item from the config based on it's section list and key (PRIVATE)"""
        d = config
        for s in section_list+[key]:
            try:
                d = d[s]
            except KeyError:
                d = d["__many__"]
        return d 


class ChannelConfig():
    """class to store the channel configuration"""

    def __init__(self, descr, values):
        """constructor for the ChannelConfig class"""
        self.description = descr
        self.static = True if values['Static'] in ['y', 'yes', 'Yes'] else False
        self.radius = values['Radius']
        self.track_file = values['TrackFile']
        self.mask_file = values['MaskFile']
