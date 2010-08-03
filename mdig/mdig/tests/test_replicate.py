import unittest
from mock import *
import logging

import mdig
from mdig import config
from mdig import grass 
from mdig.model import DispersalModel
from mdig.modelrepository import ModelRepository,RepositoryException
from mdig.replicate import Replicate

class ReplicateTest(unittest.TestCase):

    def setUp(self):
        mdig.repository = self.repo = ModelRepository()
        #logging.getLogger('mdig').setLevel(logging.CRITICAL)
        models = mdig.repository.get_models()
        fn = models['lifestage_test']
        self.m_lifestage = DispersalModel(fn)

        # Model initialise with variables
        fn = models['variables']
        self.m_variables = DispersalModel(fn)
        fn = models['variables_complete']
        self.m_variables_complete = DispersalModel(fn)

    def tearDown(self):
        self.m_variables.remove_log_handler()
        self.m_variables_complete.remove_log_handler()
        self.m_lifestage.remove_log_handler()
        
    def test_create_w_no_node(self):
        i = self.m_lifestage.get_instances()[0]
        r = Replicate(node=None,instance=i)
        # TODO check effects

    def test_create_w_no_instance(self):
        i = self.m_lifestage.get_instances()[0]
        self.assertRaises(ValueError,Replicate,node=None,instance=None)

    def test_check_complete_on_creation(self):
        config.get_config()['replicate']['check_complete']='true'
        i = self.m_variables.get_instances()[0]
        r = Replicate(node=None,instance=i)
        config.get_config()['replicate']['check_complete']='false'

    def test_check_complete(self):
        i = self.m_variables.get_instances()[0]
        r = Replicate(node=None,instance=i)
        self.assertFalse(r.check_complete())
        i = self.m_variables_complete.get_instances()[0]
        self.assertTrue(i.replicates[0].check_complete())

        r = i.replicates[0]
        r.get_saved_maps = mock_get_saved_maps
        self.assertFalse(i.replicates[0].check_complete())
        global get_save_count
        get_save_count = 0

    @patch('mdig.grass.get_g')
    def test_delete_maps(self,get_g):
        i = self.m_variables_complete.get_instances()[0]
        i.replicates[0].delete_maps()
        self.assertEqual(get_g.return_value.remove_map.call_count, 6)

        get_g.return_value.remove_map.call_count = 0
        i = self.m_lifestage.get_instances()[0]
        r = Replicate(node=None,instance=i)
        r.delete_maps()
        self.assertEqual(get_g.return_value.remove_map.call_count, 0)

        r.get_saved_maps = mock_get_saved_maps
        r.delete_maps()
        self.assertEqual(get_g.return_value.remove_map.call_count, 0)
        global get_save_count
        get_save_count = 0

    @patch('mdig.grass.get_g')
    def test_null_bitmask(self,get_g):
        i = self.m_variables_complete.get_instances()[0]
        r = i.replicates[0]
        r.null_bitmask()
        self.assertEqual(get_g.return_value.null_bitmask.call_count, 6)

    def test_map_name_base(self):
        i = self.m_variables_complete.get_instances()[0]
        name = i.replicates[0].get_map_name_base()
        self.assertEqual('variables_complete_region_a_i0_rep_0', name)
        name = i.replicates[1].get_map_name_base()
        self.assertEqual('variables_complete_region_a_i0_rep_1', name)
        i = self.m_variables_complete.get_instances()[1]
        name = i.replicates[0].get_map_name_base()
        self.assertEqual('variables_complete_region_a_i1_rep_0', name)

    def test_get_img_filenames(self):
        i = self.m_variables_complete.get_instances()[0]
        # return a dictionary of time:names
        img_fns = i.replicates[0].get_img_filenames()
        self.assertEqual(len(img_fns),6)
        # return a single filename
        img_fn = i.replicates[0].get_img_filenames(gif = True)
        self.assertEqual(len(img_fn),125)

    def test_previous_maps(self):
        i = self.m_variables_complete.get_instances()[0]
        r = i.replicates[0]
        maps = r.get_previous_maps('all')
        self.assertEqual(maps, [])
        maps.append('test1')
        maps.append('test2')
        maps = r.get_previous_maps('all')
        self.assertEqual(len(maps), 2)
        a_map = r.get_previous_map('all')
        self.assertEqual(a_map, 'test2')
        a_map = r.get_previous_map('all',2)
        self.assertEqual(a_map, 'test1')
        a_map = r.get_previous_map('all',3)
        self.assertEqual(a_map, None)
        r.push_previous_map('all','freaky')
        a_map = r.get_previous_map('all')
        self.assertEqual(a_map, 'freaky')


get_save_count = 0
def mock_get_saved_maps(ls_id):
    global get_save_count
    if get_save_count > 0:
        return {}
    else:
        get_save_count += 1
        raise mdig.grass.MapNotFoundException()







