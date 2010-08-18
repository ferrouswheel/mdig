import unittest
from mock import *
from StringIO import StringIO

import mdig
from mdig import grass 

from mdig.region import Region
class RegionTest(unittest.TestCase):
    
    @patch('mdig.grass.get_g')
    def test_create_region(self,get_g):
        from lxml import etree
        xml = """ <region id='a' name='test_region'/> """
        tree = etree.parse(StringIO(xml))
        r_node = tree.getroot()
        r = Region(r_node)
        self.assertEqual(r.get_name(), 'test_region')
        self.assertEqual(r.get_resolution(), None)
        r.set_resolution(1)
        self.assertEqual(r.get_resolution(), 1)

        xml = """ <region id='a' name='test_region@test_mapset'/> """
        tree = etree.parse(StringIO(xml))
        r_node = tree.getroot()
        r = Region(r_node)
        self.assertEqual(r.get_name(), 'test_region')
        self.assertEqual(r.get_mapset(), 'test_mapset')

        xml = """ <region id='a'></region> """
        tree = etree.parse(StringIO(xml))
        r_node = tree.getroot()
        r = Region(r_node)
        self.assertEqual(r.get_resolution(), 1)
        self.assertEqual(r.get_name(), None)
        xml = """ <region id='a'><resolution>1</resolution></region> """
        tree = etree.parse(StringIO(xml))
        r_node = tree.getroot()
        r = Region(r_node)
        self.assertEqual(r.get_resolution(), 1)
        self.assertEqual(r.get_name(), None)
        xml = """ <region id='a'><resolution>201</resolution></region> """
        tree = etree.parse(StringIO(xml))
        r_node = tree.getroot()
        r = Region(r_node)
        self.assertEqual(r.get_resolution(), 201)
        self.assertEqual(r.get_name(), None)
        xml = """ <region id='a'><resolution>flibble</resolution></region> """
        tree = etree.parse(StringIO(xml))
        r_node = tree.getroot()
        r = Region(r_node)
        self.assertRaises(ValueError,r.get_resolution)
        self.assertEqual(r.get_name(), None)

        r.set_name('test_region')
        self.assertEqual(r.get_name(), 'test_region')

        r.set_resolution(1)
        self.assertEqual(r.get_resolution(), 1)
        self.assertRaises(ValueError,r.set_resolution,'fox')

    @patch('mdig.grass.get_g')
    def test_extents(self,get_g):
        from lxml import etree
        xml = """ <region id='a'><extents n='10' s='-10' e='10' w='-10'/></region> """
        tree = etree.parse(StringIO(xml))
        r_node = tree.getroot()
        r = Region(r_node)
        e = r.get_extents()
        self.assertEqual(e['n'], 10)
        e = {'n':1,'s':0,'e':2,'w':1}
        r.set_extents(e)
        self.assertEqual(r.get_extents(),e)

        xml = """ <region id='a'></region> """
        tree = etree.parse(StringIO(xml))
        r_node = tree.getroot()
        r = Region(r_node)
        e = r.get_extents()
        self.assertEqual(e, None)

        e = {'n':1,'s':0,'e':2,'w':1}
        r.set_extents(e)
        self.assertEqual(r.get_extents(),e)

        bade = {'k':1,'s':0,'e':2,'w':1}
        self.assertRaises(KeyError,r.set_extents,bade)
        self.assertEqual(r.get_extents(),e)
        bade = {'n':1,'s':0,'roar':2,'w':1}
        self.assertRaises(KeyError,r.set_extents,bade)
        self.assertEqual(r.get_extents(),e)

        r.update_xml() # does nothing



        


        



        


