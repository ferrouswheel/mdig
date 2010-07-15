import unittest
from mock import *

import os
import pdb
import tempfile
import shutil
import datetime

import mdig
from mdig import MDiGConfig
from mdig import GRASSInterface 
from mdig.DispersalModel import DispersalModel
from mdig.Actions import RunAction
from mdig.ModelRepository import ModelRepository,RepositoryException
from mdig.DispersalInstance import InvalidLifestageException, \
        InstanceIncompleteException, InvalidReplicateException, NoOccupancyEnvelopesException

from mdig.GrassMap import GrassMap
from StringIO import StringIO
class GrassMapTest(unittest.TestCase):

    def setUp(self):
	self.gmap = None
    
    #def tearDown(self,get_g):
	# Save objects from trying to cleanup after themselves
        #if self.gmap: self.gmap.__del__ = lambda x: None

    @patch('mdig.GRASSInterface.get_g')
    def test_create_sites_map(self,get_g):
        from lxml import etree
        xml = """<sites>
          <s x="1" y="0" count="100"/>
          <s x="2" y="0"/>
          <s x="3" y="0"/>
          <s x="4" y="0"/>
          <s x="5" y="0"/>
          <s x="0" y="-5"/>
        </sites>"""
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(len(self.gmap.value), 6)

        get_g.return_value.init_map.return_value = ("test","a_map_type")
        get_g.return_value.get_mapset.return_value = "a_mapset"
        a = self.gmap.get_map_filename()
        b = self.gmap.get_map_filename()
        self.assertEqual(get_g.return_value.init_map.call_count,1)
        self.assertEqual(self.gmap.ready, True)
        self.assertEqual(self.gmap.mapset, "a_mapset")

    @patch('mdig.GRASSInterface.get_g')
    def test_create_name_map(self,get_g):
        from lxml import etree
        xml = "<map>nz_DEM</map>"
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(self.gmap.value, "nz_DEM")
        self.assertEqual(self.gmap.filename, "nz_DEM")
        self.assertEqual(self.gmap.xml_map_type, "name")
        self.assertEqual(self.gmap.get_map_filename(), "nz_DEM")

    @patch('mdig.GRASSInterface.get_g')
    def test_create_value_map(self,get_g):
        from lxml import etree
        xml = "<value>1</value>"
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(self.gmap.value, "1")
        self.assertEqual(self.gmap.xml_map_type, "value")

    @patch('mdig.GRASSInterface.get_g')
    def test_create_mapcalc_map(self,get_g):
        from lxml import etree
        xml = "<mapcalc>if(isnull(nz_DEM),x(),nz_DEM)</mapcalc>"
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(self.gmap.xml_map_type, "mapcalc")
        self.assertEqual(self.gmap.refresh, False)
	del self.gmap

        xml = "<mapcalc refresh=\"true\">if(isnull(nz_DEM),x(),nz_DEM)</mapcalc>"
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(self.gmap.xml_map_type, "mapcalc")
        self.assertEqual(self.gmap.refresh, True)

        get_g.return_value.init_map.return_value = ("test","a_map_type")
        get_g.return_value.get_mapset.return_value = "a_mapset"
        a = self.gmap.get_map_filename()
        b = self.gmap.get_map_filename()
        self.assertEqual(get_g.return_value.init_map.call_count,2)
        self.assertEqual(get_g.return_value.destruct_map.call_count,1)
        self.assertEqual(self.gmap.ready, True)
        self.assertEqual(self.gmap.mapset, "a_mapset")
        self.gmap.clean_up()
        self.assertEqual(get_g.return_value.destruct_map.call_count,2)

    @patch('mdig.GRASSInterface.get_g')
    def test_change_map_type(self,get_g):
        self.gmap = GrassMap(filename="test")
        self.assertRaises(NotImplementedError, self.gmap.change_map_type, "raster", "1") 

    @patch('mdig.GRASSInterface.get_g')
    def test_use_existing_map(self,get_g):
        fn = "nz_DEM_jacques"
        self.gmap = GrassMap(filename=fn)
        self.assertEqual(get_g.return_value.check_map.called, True)
        self.assertEqual(get_g.return_value.check_map.call_args[0][0], fn)

        # test when we can't find the map
        get_g.return_value.check_map.return_value = None
        self.assertRaises(mdig.GRASSInterface.MapNotFoundException,GrassMap,filename=fn)

