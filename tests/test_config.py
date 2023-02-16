import unittest
from unittest import mock
import os 
import tempfile
import re

# Add project directory to sys.path in order to make the project file easily visible
# as discussed in https://stackoverflow.com/q/4761041
# Must be before the project import statements 
import sys
import os
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "..")

from dctracker import config
from dctracker.config import ConfigError, ConfigTypeError, ConfigValueError

class TestConfig(unittest.TestCase):

    def setUp(self):
        # Generate the list that is used to build the invalid configs
        self.dummy_config = config.CONFIG_SPECS.replace("__many__", "Label").splitlines()
        self.min_input_count = 1 # Remove requirement of 2+ input to be able to use the config.CONFIG_SPECS directly


    def options_to_list(self, line):
        """Convert the options to a list"""
        # Transform the option string into a list
        options = line.split("option(")[1][:-1] # Extraction the option string
        options = options.replace('\'', '').replace('"', '').replace(' ', '') # Clean unnecessary caracters
        options = options.split(',') # Generate a list
        return options


    def generate_valid_line(self, line):
        """Generate a valid line for the configuration based on the config specs description"""
        # Remove defaults from the lines 
        # Remove default value first, then remove empty parenthesis to handle both cases with 
        # int/str defaults (empty parenthesis) and options defaults (no empty parenthesis)
        # the coma is also removed for option default
        line = re.sub('(, )?default=[^)]*', '', line)
        line = line.replace('()', '')

        # Handle the other descriptions
        if "option(" in line:
            line = line.split("option(")[0] + self.options_to_list(line)[0]
        elif '= float' in line:
            line = line.replace('= float', '= ' + str(0.0))
        elif '= integer' in line:
            line = line.replace('= integer', '= ' + str(0))
        elif '= string' in line:
            line = line.replace('= string', '= ' + 'text')
        return line

    ############################################################
    #                  TESTS STARTS HERE                       #
    ############################################################


    def test_parse_config_throws_exception_when_file_missing(self):
        file = "/dummy/file"
        self.assertRaises(FileNotFoundError, config.parse_config, file)


    def test_parse_config_throws_exception_when_missing_input(self):

        testing_config = ""
        for l in self.dummy_config:
            testing_config = testing_config + self.generate_valid_line(l) + '\n'
        
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(bytes(testing_config, encoding = 'utf-8'))
            tmp.seek(0)
            # Keep the default input count by keeping the default min_input_count value
            self.assertRaises(ConfigError, config.parse_config, tmp.name)


    def test_parse_config_throws_exception_when_missing(self):
        # Generate all possible configuration file with a missing element
        #    - Section are removed entierly 
        #    - Keyword that does not have a default are removed (keyword with default are 
        #      ignored as this are optional) 

        # Iterate over all line in the config spec
        # The line in p is the line that will be analysed (and removed for the test) 
        testing_config = []
        for p in range(0, len(self.dummy_config)):
            # Return depth (number of "[") for section string
            def depth(s):
                return len([c for c in s.strip() if c == "["])
            
            # Ignore blank line and lines with default as these are optional
            if self.dummy_config[p].strip() and not ("default=" in self.dummy_config[p] or "Label" in self.dummy_config[p]):
                config_str = ''
                i = 0 
                section = False
                level = -1

                # Iterate over the complete config once more to build the testing config
                for l in self.dummy_config:
                    # Keep line before the tested line
                    if i < p:
                        config_str = config_str + self.generate_valid_line(l) + '\n'
                    else:
                        # Remove the tested line 
                        # If the tested line is a section label, start a section segment
                        # to remove the section block
                        if i == p:
                            if l.strip().startswith("["):
                                section = True 
                                level = depth(l)
                        # After the testing line two cases can happen : 
                        #    - If the testing is a section, lines are removed until the end of the section (i.e., a new section starts)
                        #    - If the testing is a keyword, the remaining lines are added 
                        else: 
                            if l.strip().startswith("[") and level == depth(l):
                                section = False 
                                level = -1
                            
                            if not section:
                                config_str = config_str + self.generate_valid_line(l) + '\n'
                    i += 1 
                
                testing_config.append(config_str.replace('(default=None)', '')) # Most remove default=None otherwise will trigged a ConfigTypeError exception

        with self.subTest(config_str=config_str):
            for config_str in testing_config:
                with tempfile.NamedTemporaryFile() as tmp:
                    tmp.write(bytes(config_str, encoding = 'utf-8'))
                    tmp.seek(0)
                    self.assertRaises(ConfigError, config.parse_config, tmp.name, self.min_input_count)


    def test_parse_config_throws_exception_when_invalid_type(self):
        # Generate all possible configuration files with an invalid type
        testing_config = []
        for p in range(0, len(self.dummy_config)):
            config_str = ""
            i = 0

            # Generate an invalid config if the line that is analysis contains the keyword 'option'
            if '= float' in self.dummy_config[p] or '= integer' in self.dummy_config[p]:
                # Iterate over the complete config to build the testing config
                for l in self.dummy_config:
                    # Keep line before or after the tested line
                    if i < p or i > p:
                        config_str = config_str + self.generate_valid_line(l) + '\n'
                    else:
                        if '= float' in l:
                            invalid_line = re.sub('\(default=.+\)', '', l.replace('= float', '= text'))
                        elif '= integer' in l:
                            invalid_line = re.sub('\(default=.+\)', '', l.replace('= integer', '= text'))
                        config_str = config_str + invalid_line + '\n'
                    i += 1
                testing_config.append(config_str)

        for config_str in testing_config:
            with self.subTest(config_str=config_str):
                with tempfile.NamedTemporaryFile() as tmp:
                    tmp.write(bytes(config_str, encoding = 'utf-8'))
                    tmp.seek(0)
                    self.assertRaises(ConfigTypeError, config.parse_config, tmp.name, self.min_input_count)  


    def test_parse_config_throws_exception_when_invalid_option(self):
        # Generate all possible configuration files with an invalid type
        testing_config = []
        for p in range(0, len(self.dummy_config)):
            config_str = ""
            i = 0

            # Generate an invalid config if the line that is analysis contains the keyword 'option'
            if "option(" in self.dummy_config[p]:
                # Iterate over the complete config to build the testing config
                for l in self.dummy_config:
                    # Keep line before or after the tested line
                    if i < p or i > p:
                        config_str = config_str + self.generate_valid_line(l) + '\n'
                    else:
                        invalid_line = l.split("option(")[0] + "INVALID_VALUE"
                        config_str = config_str + invalid_line + '\n'
                    i += 1
                testing_config.append(config_str)    

        for config_str in testing_config:
            with self.subTest(config_str=config_str):
                with tempfile.NamedTemporaryFile() as tmp:
                    tmp.write(bytes(config_str, encoding = 'utf-8'))
                    tmp.seek(0)
                    self.assertRaises(ConfigValueError, config.parse_config, tmp.name, self.min_input_count)       
