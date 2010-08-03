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

class DispersalModelTest(unittest.TestCase):

    def test_empty_model(self):
        dm = DispersalModel()
        self.assertEqual(dm.model_file, None)
        # Check root xml node has been created
        self.assertEqual(dm.xml_model.tag, "model")

    def test_model_constructor(self):
        dm = DispersalModel(the_action = RunAction())
        dm = DispersalModel(the_action = RunAction(), setup=False)
    
    @patch('mdig.lifestagetransition.LifestageTransition.xml_to_param')
    def test_get_resources(self,m_xml):
        m_xml.return_value={}
        mdig.repository = self.repo = ModelRepository()
        models = mdig.repository.get_models()
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


