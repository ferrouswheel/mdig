import unittest
from mock import *
import logging

import mdig
from mdig import MDiGConfig
from mdig import GRASSInterface 
from mdig.DispersalModel import DispersalModel
from mdig.ModelRepository import ModelRepository,RepositoryException
from mdig.DispersalInstance import InvalidLifestageException, \
        InstanceIncompleteException, InvalidReplicateException, NoOccupancyEnvelopesException

class DispersalInstanceTest(unittest.TestCase):

    def setUp(self):
        mdig.repository = self.repo = ModelRepository()
        #logging.getLogger('mdig').setLevel(logging.CRITICAL)
        fn = mdig.repository.get_models()['lifestage_test']
        self.m_lifestage = DispersalModel(fn)

        # Model initialise with management strategy
        fn = mdig.repository.get_models()['management_alter_variable']
        self.m_strategy = DispersalModel(fn)
        
        # Model initialise with variables
        fn = mdig.repository.get_models()['variables']
        self.m_variables = DispersalModel(fn)
        #logging.getLogger('mdig').setLevel(logging.WARNING)

        c = MDiGConfig.get_config()
        self.gisdb = c['GRASS']['GISDBASE']

    def testDown(self):
        pass

    @patch('mdig.GRASSInterface.get_g')
    def test_load_replicates(self,m_g):
        m_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        # replicates loaded on init
        self.m_lifestage.get_instances()
        self.m_strategy.get_instances()
        self.m_variables.get_instances()

    @patch('mdig.GRASSInterface.get_g')
    def test_get_mapset(self,m_g):
        m_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        i = self.m_lifestage.get_instances()[0]
        self.assertEqual(i.get_mapset().find('lifestage_test_i'), 0)
        del i.node.attrib['mapset']
        self.assertRaises(mdig.DispersalInstance.DispersalInstanceException,i.get_mapset)

    @patch('mdig.GRASSInterface.get_g')
    def test_set_mapset(self,m_g):
        m_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        i = self.m_lifestage.get_instances()[0]
        i.set_mapset('blah')
        self.assertEqual(i.node.attrib['mapset'], 'blah')

    @patch('mdig.GRASSInterface.get_g')
    def test_add_envelope(self,m_g):
        m_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        i = self.m_variables.get_instances()[0]
        i._add_envelope('test_envelope','all',1)
        e = i.node.find('envelopes')
        self.assertEqual(len(e),1)
        # second add doesn't have to init xml structure
        i._add_envelope('test_envelope','all',1)
        self.assertEqual(len(e),1)

    @patch('mdig.GRASSInterface.get_g')
    def test_update_xml(self,m_g):
        m_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        i = self.m_variables.get_instances()[0]
        i.enabled = False
        i.update_xml()
        self.assertEqual(i.node.attrib['enabled'],'false')
        i.enabled = True
        i.update_xml()
        self.assertEqual(i.node.attrib['enabled'],'true')

    @patch('mdig.GRASSInterface.get_g')
    def test_update_occupancy_envelope(self,m_get_g):
        m_get_g.return_value.occupancy_envelope.return_value = "test_env"
        m_get_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        i = self.m_variables.get_instances()[0]
        self.assertRaises(InstanceIncompleteException,i.update_occupancy_envelope)
        #i.is_complete = True
        # TODO need a instance that actually has some replicates
        #i.update_occupancy_envelope()

        # test without rep maps
        #i.saved_maps = {}
        #m_get_g.return_value.occupancy_envelope.return_value = "test_env"
        #i = self.m_variables.get_instances()[0]
        #i.update_occupancy_envelope(force=True)

