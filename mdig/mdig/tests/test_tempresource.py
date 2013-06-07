import unittest
from mock import *

import mdig
from mdig.tempresource import TempResourceManager

class TempResourceTest(unittest.TestCase):

    def setUp(self):
        self.trm = TempResourceManager()

    def tearDown(self):
        self.trm.cleanup()
    
    def test_temp_file(self):
        fn = self.trm.temp_filename('test')
        self.assertTrue('test' in fn)

    def test_release(self):
        fn = self.trm.temp_filename('test')
        self.assertTrue('test' in fn)

        self.trm.release(fn)

        self.assertEqual(len(self.trm.temp_files), 0)
