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

import io 
import pathlib

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


class ConfigError(RuntimeError):
    """Raise if a configuration file contains one or more invalid options """


class ConfigTypeError(RuntimeError):
    """Raise if a configuration file contains one or more values with an invalid type """


class ConfigValueError(RuntimeError):
    """Raise if a configuration file contains one or more values with an invalid value 
    (i.e., the value is not one of the allowed options)"""


def parse_config(config, min_input_count=2): 
    """
    Parse a configuration file using ConfigObj. The file is validated using the spec
    described here in CONFIG_SPECS

    Exceptions: 
        ConfigException: if a ValidateError is encountered

    Arguments:
       config (str): Configuration file path
       min_input_count (int): Minimum number of inputs required in the configuration

    Return: 
        dict: Parsed configuration 
    """
    # Validate that the config file exists 
    if not config.is_file():
        raise FileNotFoundError
    
    # Parse and validate the configuration file
    config = ConfigObj(str(config), configspec=io.StringIO(CONFIG_SPECS))
    validator = Validator()
    results = config.validate(validator, preserve_errors=True)

    # Validate that the configuration contains at least two inputs
    if len(list_particle_key(config)) < min_input_count:
        msg = "The configuration file does not contain two input sections."
        raise ConfigError(msg)

    # Validate that either a mask or radius is provided for each particle
    for particle in list_particle_key(config):
        if not config['Input'][particle]["Radius"] and not config['Input'][particle]["MaskFile"]: 
            msg = "No mask file or particle radius is provided in the configuration for the particle \"{}\".".format(particle)
            raise ConfigError(msg)

    # Analyse the validator results to return user readable error messages 
    # Only VdtTypeError and VdtValueError are caught as there are no validation that 
    # would return VdtValueTooSmallError, VdtValueTooBigError, VdtValueTooShortError or 
    # VdtValueTooLongError
    for entry in flatten_errors(config, results):
        section_list, key, error = entry
        if error == False:
            msg = "The required parameter \"{}\" is not in the config file.".format(section_key_string(section_list, key))
            raise ConfigError(msg)

        if key is not None:
            # Invalid key content
            key_string = config_item(config, section_list, key)

            # Raise an exception based on the type of error in the config
            if isinstance(error, VdtValueError):
                option_string = config_item(config.configspec, section_list, key)[7:-1]
                msg = "The parameter \"{}\" is set to \"{}\" which is not one of the allowed values. Please set the value to be one of the following options : {}".format((section_key_string(section_list, key), key_string, option_string))
                raise ConfigValueError(msg)

            if isinstance(error, VdtTypeError):
                type_string = config_item(config.configspec, section_list, key)
                msg = "The parameter \"{}\" is set to \"{}\" which is not one of the allowed types. Please set the value to be of type : {}".format((section_key_string(section_list, key), key_string, type_string))
                raise ConfigTypeError(msg)

    return config


def list_particle_key(config):
    """
    Returns a list of the input sub-sections keys (i.e., the particules labels)
    """
    return [i for i in config['Input'] if isinstance(config['Input'][i], dict)]


def section_key_string(section_list, key):
    """
    Returns a string with the complete section and key for a config item. Sections are 
    separated by backslash
    """
    return '/'.join([x for x in section_list + [key] if x is not None])


def config_item(config, section_list, key):
    """
    Extract an item from the config based on it's section list and key
    """
    d = config
    for s in section_list+[key]:
        try:
            d = d[s]
        except KeyError:
            d = d["__many__"]
    return d 