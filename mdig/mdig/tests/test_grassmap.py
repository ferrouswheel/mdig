import unittest
from mock import *

import mdig
from mdig import grass 

from mdig.grassmap import GrassMap
from mdig.tests import string_as_xml_node


class GrassMapTest(unittest.TestCase):

    def setUp(self):
        self.gmap = None
        self.grass_i = mdig.grass.get_g()

    #def tearDown(self,get_g):
    # Save objects from trying to cleanup after themselves
        #if self.gmap: self.gmap.__del__ = lambda x: None

    @patch('mdig.grass.get_g')
    def test_create_sites_map(self,get_g):
        xml = """<sites>
          <s x="1" y="0" count="100"/>
          <s x="2" y="0"/>
          <s x="3" y="0"/>
          <s x="4" y="0"/>
          <s x="5" y="0"/>
          <s x="0" y="-5"/>
        </sites>"""
        map_node = string_as_xml_node(xml)
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(len(self.gmap.value), 6)

        get_g.return_value.init_map.return_value = ("test","a_map_type")
        get_g.return_value.get_mapset.return_value = "a_mapset"
        a = self.gmap.get_map_filename()
        b = self.gmap.get_map_filename()
        self.assertEqual(get_g.return_value.init_map.call_count,1)
        self.assertEqual(self.gmap.ready, True)
        self.assertEqual(self.gmap.mapset, "a_mapset")

    @patch('mdig.grass.get_g')
    def test_create_sites_map_w_comment(self,get_g):
        xml = """<sites>
          <!--<s x="1" y="0" count="100"/>-->
          <s x="2" y="0"/>
          <s x="3" y="0"/>
          <s x="4" y="0"/>
          <s x="5" y="0"/>
          <s x="0" y="-5"/>
        </sites>"""
        map_node = string_as_xml_node(xml)
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(len(self.gmap.value), 5)

    @patch('mdig.grass.get_g')
    def test_create_name_map(self, get_g):
        xml = "<map>nz_DEM</map>"
        map_node = string_as_xml_node(xml)
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(self.gmap.value, "nz_DEM")
        self.assertEqual(self.gmap.filename, "nz_DEM")
        self.assertEqual(self.gmap.xml_map_type, "name")
        self.assertEqual(self.gmap.get_map_filename(), "nz_DEM")

    @patch('mdig.grass.get_g')
    def test_create_value_map(self, get_g):
        xml = "<value>1</value>"
        map_node = string_as_xml_node(xml)
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(self.gmap.value, "1")
        self.assertEqual(self.gmap.xml_map_type, "value")

    @patch('mdig.grass.grass_i')
    def test_create_mapcalc_map(self, grass_i):
        xml = "<mapcalc>if(isnull(nz_DEM),x(),nz_DEM)</mapcalc>"
        map_node = string_as_xml_node(xml)
        self.gmap = GrassMap(xml_node = map_node)
        self.assertEqual(self.gmap.xml_map_type, "mapcalc")
        self.assertEqual(self.gmap.refresh, False)
        del self.gmap

        xml = "<mapcalc refresh=\"true\">if(isnull(nz_DEM),x(),nz_DEM)</mapcalc>"
        map_node = string_as_xml_node(xml)
        self.gmap = GrassMap(xml_node=map_node)
        self.assertEqual(self.gmap.xml_map_type, "mapcalc")
        self.assertEqual(self.gmap.refresh, True)

    @patch('mdig.grass.get_g')
    def test_mapcalc_cleanup(self, get_g):
        xml = "<mapcalc refresh=\"true\">if(isnull(nz_DEM),x(),nz_DEM)</mapcalc>"
        map_node = string_as_xml_node(xml)
        self.gmap = GrassMap(xml_node=map_node)

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

    def test_change_map_type(self):
        self.gmap = GrassMap(filename="suitability@PERMANENT")
        self.assertRaises(NotImplementedError, self.gmap.change_map_type, "raster", "1") 

    @patch('mdig.grass.grass_i.check_map')
    def test_use_existing_map(self, check_map):
        fn = "nz_DEM_jacques"
        self.gmap = GrassMap(filename=fn)
        self.assertEqual(check_map.called, True)
        self.assertEqual(check_map.call_args[0][0], fn)

        # test when we can't find the map
        check_map.return_value = None
        self.assertRaises(mdig.grass.MapNotFoundException, GrassMap, filename=fn)

    def test_init_map(self):
        xml = "<mapcalc refresh=\"true\">x()</mapcalc>"
        map_node = string_as_xml_node(xml)
        self.gmap = GrassMap(xml_node=map_node)

        grass.get_g().init_map(self.gmap)
