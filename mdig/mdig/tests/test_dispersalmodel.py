import unittest
from mock import *

import os
import pdb
import tempfile
import shutil
import datetime

import mdig
from mdig import config
from mdig import grass 
from mdig.model import DispersalModel
from mdig.modelrepository import ModelRepository,RepositoryException
from mdig.actions import RunAction

class CompareVersionTest(unittest.TestCase):

    def test_compare_version(self):
        from mdig import compare_version
        self.assertTrue(compare_version('1.2.3','1.3.5') < 0)
        self.assertTrue(compare_version('1.3.5','1.2.44') > 0)
        self.assertTrue(compare_version('1.3.5','1.3.5.1') < 0)


class DispersalModelTest(unittest.TestCase):

    def test_empty_model(self):
        dm = DispersalModel()
        self.assertEqual(dm.model_file, None)
        # Check root xml node has been created
        self.assertEqual(dm.xml_model.tag, "model")

    def test_model_constructor(self):
        dm = DispersalModel(the_action = RunAction())
        dm = DispersalModel(the_action = RunAction(), setup=False)

    def test_get_weird_resources(self):
        mdig.repository = self.repo = ModelRepository()
        models = mdig.repository.get_models()
        # this model has a comment that messed up initial map creation
        fn = models['test_weird_map_resource']
        m = DispersalModel(fn)
        res = m.get_resources()
        self.assertEqual(len(res),0)
        m.remove_log_handler()
    
    @patch('mdig.lifestagetransition.LifestageTransition.xml_to_param')
    def test_get_resources(self,m_xml):
        m_xml.return_value={}
        mdig.repository = self.repo = ModelRepository()
        models = mdig.repository.get_models()
        # in other test
        del models['test_weird_map_resource']
        ###
        fn = models['lifestage_test']
        m = DispersalModel(fn)
        res = m.get_resources()
        self.assertEqual(len(res),7)
        self.assertEqual(len([i[0] for i in res if i[0] =='popmod']),1)
        self.assertEqual(len([i[0] for i in res if i[0] =='coda']),6)
        del models['lifestage_test']
        m.remove_log_handler()

        fn = models['test_named_region']
        m = DispersalModel(fn)
        res = m.get_resources()
        self.assertEqual(len(res),5)
        self.assertEqual(len([i[0] for i in res if i[0] =='region']),1)
        self.assertEqual(len([i[0] for i in res if i[0] =='map']),4)
        self.assertEqual(len([i[0] for i in res if i[2] =='PERMANENT']),2)
        self.assertEqual(len([i[0] for i in res if i[2] =='test_named_region']),2)
        self.assertEqual(len([i[0] for i in res if i[2] is None]),1)
        del models['test_named_region']
        m.remove_log_handler()

        fn = models['management_use_maps']
        m = DispersalModel(fn)
        res = m.get_resources()
        self.assertEqual(len(res),3)
        self.assertEqual(len([i[0] for i in res if i[0] =='map']),3)
        self.assertEqual(len([i[0] for i in res if i[2] =='PERMANENT']),1)
        self.assertEqual(len([i[0] for i in res if i[2] is None]),2)
        del models['management_use_maps']
        m.remove_log_handler()

        # check the others don't erroneously report resources
        for k in models:
            fn = models[k]
            m = DispersalModel(fn)
            res = m.get_resources()
            self.assertEqual(len(res),0)
            m.remove_log_handler()

    def test_get_instances(self):
        # this functionally generally well tested, but
        # test removing deprecated baseDir attrib...
        mdig.repository = ModelRepository()
        models = mdig.repository.get_models()
        fn = models['lifestage_test']
        m = DispersalModel(fn)
        completed_node = m.xml_model.xpath("/model/instances")
        self.assertTrue(len(completed_node) > 0)
        completed_node[0].attrib['baseDir'] = 'flibble'
        instances = m.get_instances()

    def test_null_bitmask(self):
        mdig.repository = ModelRepository()
        models = mdig.repository.get_models()
        fn = models['lifestage_test']
        m = DispersalModel(fn)
        for i in m.get_instances():
            i.null_bitmask = Mock()
        m.null_bitmask()
        for i in m.get_instances():
            self.assertEqual(i.null_bitmask.call_count,1)
            self.assertEqual(i.null_bitmask.call_args[0][0], True)
        # check parameter is passed
        m.null_bitmask(generate=False)
        for i in m.get_instances():
            self.assertEqual(i.null_bitmask.call_count,2)
            self.assertEqual(i.null_bitmask.call_args[0][0], False)
        # check disabled instances are not touched
        for i in m.get_instances():
            i.enabled=False
        m.null_bitmask()
        for i in m.get_instances():
            self.assertEqual(i.null_bitmask.call_count,2)

        
    def test_run(self):
        mdig.repository = ModelRepository()
        models = mdig.repository.get_models()
        fn = models['lifestage_test']
        m = DispersalModel(fn)
        m._get_instance_w_smallest_reps_remaining = Mock()
        m._get_instance_w_smallest_reps_remaining.return_value = None
        m.pre_run()
        m.run()
        self.assertEqual(m.active, False)
        self.assertTrue(m.start_time < datetime.datetime.now())
        self.assertTrue(m.start_time < m.end_time)
        self.assertTrue(m.end_time < datetime.datetime.now())

    def test_log_instance_times(self):
        mdig.repository = ModelRepository()
        models = mdig.repository.get_models()
        fn = models['lifestage_test']
        m = DispersalModel(fn)
        m.log_instance_times()

    def test_is_complete(self):
        mdig.repository = ModelRepository()
        models = mdig.repository.get_models()
        fn = models['variables']
        m = DispersalModel(fn)
        self.assertFalse(m.is_complete())
        fn = models['variables_complete']
        m = DispersalModel(fn)
        self.assertTrue(m.is_complete())

    @patch('shutil.rmtree')
    def test_hard_reset(self,m_rm):
        mdig.repository = ModelRepository()
        models = mdig.repository.get_models()
        fn = models['lifestage_test']
        m = DispersalModel(fn)
        # init the mapsets so we have something to remove
        for i in m.get_instances():
            i.init_mapset()
        m.hard_reset()
        self.assertEqual(m_rm.call_count,1)
        self.assertEqual(len(m.xml_model.xpath('/model/instances/completed')),0)
        m.remove_log_handler()


