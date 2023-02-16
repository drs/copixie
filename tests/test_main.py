import unittest

# Add project directory to sys.path in order to make the project file easily visible
# as discussed in https://stackoverflow.com/q/4761041
# Must be before the project import statements 
import sys
import os
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "..")

from dctracker import main 

class TestConfig(unittest.TestCase):
    pass 