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
        models = mdig.repository.get_models()
        fn = models['lifestage_test']
        self.m_lifestage = DispersalModel(fn)

        # Model initialise with management strategy
        fn = models['management_area_combine']
        self.m_strategy = DispersalModel(fn)
        
        # Model initialise with variables
        fn = models['variables']
        self.m_variables = DispersalModel(fn)
        #logging.getLogger('mdig').setLevel(logging.WARNING)

        fn = models['variables_complete']
        self.m_variables_complete = DispersalModel(fn)

        c = MDiGConfig.get_config()
        self.gisdb = c['GRASS']['GISDBASE']

    def tearDown(self):
        self.m_variables.remove_log_handler()
        self.m_variables_complete.remove_log_handler()
        self.m_lifestage.remove_log_handler()
        self.m_strategy.remove_log_handler()

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
        mapset = i.node.attrib['mapset']
        del i.node.attrib['mapset']
        self.assertRaises(mdig.DispersalInstance.DispersalInstanceException,i.get_mapset)
        i.node.attrib['mapset'] = mapset

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

        i = self.m_variables_complete.get_instances()[0]
        i.update_occupancy_envelope()
        call_args = m_get_g.return_value.occupancy_envelope.call_args
        self.assertEqual(len(call_args[0][0]), 2)
        self.assertEqual(call_args[0][1], 'variables_complete_region_a_i0_ls_all_t_5_prob')

        #check existing aborts
        m_get_g.return_value.occupancy_envelope.call_args = []
        i.update_occupancy_envelope()
        call_args = m_get_g.return_value.occupancy_envelope.call_args
        self.assertEqual(len(call_args), 0)

        #check overwrite maps works
        m_get_g.return_value.occupancy_envelope.call_args = []
        i.update_occupancy_envelope(force=True)
        call_args = m_get_g.return_value.occupancy_envelope.call_args
        self.assertEqual(len(call_args[0][0]), 2)
        self.assertEqual(call_args[0][1], 'variables_complete_region_a_i0_ls_all_t_5_prob')

    @patch('mdig.GRASSInterface.get_g')
    def test_listeners(self,m_get_g):
        m_get_g.return_value.occupancy_envelope.return_value = "test_env"
        m_get_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        i = self.m_variables_complete.get_instances()[0]
        class l:
            count = 0
            def occupancy_envelope_complete(self,i,l,t): self.count+=1
        i.listeners = [ l() ]
        i.update_occupancy_envelope()
        self.assertEqual(i.listeners[0].count, 6)
        call_args = m_get_g.return_value.occupancy_envelope.call_args
        self.assertEqual(len(call_args[0][0]), 2)
        self.assertEqual(call_args[0][1], 'variables_complete_region_a_i0_ls_all_t_5_prob')

    @patch('mdig.GRASSInterface.get_g')
    def test_update_occupancy_env_strategy(self,m_get_g):
        # test with strategy
        m_get_g.return_value.occupancy_envelope.return_value = "test_env"
        m_get_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        m_get_g.return_value.occupancy_envelope.call_args = []
        # check with strategy
        i = self.m_strategy.get_instances()[1]
        self.assertTrue(i.strategy is not None)
        i.update_occupancy_envelope(force=True)
        call_args = m_get_g.return_value.occupancy_envelope.call_args
        self.assertEqual(len(call_args[0][0]), 2)
        self.assertEqual(call_args[0][1], 'management_area_combine_region_a_i1_ls_all_t_5_prob')

    @patch('mdig.GRASSInterface.get_g')
    @patch('mdig.Replicate.Replicate.get_saved_maps')
    def test_update_occupancy_env_missing_maps(self,m_get_maps,m_get_g):
        # test without rep maps
        m_get_g.return_value.occupancy_envelope.return_value = "test_env"
        m_get_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        m_get_g.return_value.occupancy_envelope.call_args = []
        m_get_maps.return_value = {}

        i = self.m_variables_complete.get_instances()[0]
        self.assertRaises(mdig.DispersalInstance.DispersalInstanceException,
                i.update_occupancy_envelope,force=True)
        call_args = m_get_g.return_value.occupancy_envelope.call_args
        self.assertEqual(len(call_args), 0)

        #import pdb;pdb.set_trace()
        m_get_maps.return_value = {1:'test1',222:'test2'}
        self.assertRaises(mdig.DispersalInstance.DispersalInstanceException,
                i.update_occupancy_envelope,force=True)

    @patch('mdig.GRASSInterface.get_g')
    def test_str(self,m_get_g):
        # test with strategy
        m_get_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        # check with no strategy
        i = self.m_strategy.get_instances()[0]
        self.assertTrue(len(str(i)) > 0)
        self.assertTrue(len(i.long_str()) > 0)
        i.enabled = False
        self.assertTrue(len(str(i)) > 0)
        self.assertTrue(len(i.long_str()) > 0)
        i.enabled = True
        i.activeReps = [1]
        self.assertTrue(len(str(i)) > 0)
        self.assertTrue(len(i.long_str()) > 0)
        i.activeReps = []
        # check with strategy
        i = self.m_strategy.get_instances()[1]
        self.assertTrue(len(str(i)) > 0)
        self.assertTrue(len(i.long_str()) > 0)

    @patch('mdig.GRASSInterface.get_g')
    @patch('os.path')
    @patch('os.remove')
    @patch('shutil.move')
    def test_add_analysis_result(self,m_shutil,m_remove,m_path,m_get_g):
        m_path.basename.return_value = 'test'
        m_get_g.return_value.grass_vars = {'GISDBASE':self.gisdb}
        # check with no strategy
        i = self.m_strategy.get_instances()[0]
        analysis_cmd = Mock()
        analysis_cmd.cmd_string = 'wibble'
        analysis_cmd.output_fn = 'wibble'
        # Test with file existing
        i.add_analysis_result('all',analysis_cmd)
        # Test with overwrite
        MDiGConfig.get_config().overwrite_flag = True
        i.add_analysis_result('all',analysis_cmd)
        # run again to check parsing existing lifestage analysis results
        i.add_analysis_result('all',analysis_cmd)
        MDiGConfig.get_config().overwrite_flag = False






