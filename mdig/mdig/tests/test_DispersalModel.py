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
from mdig.ModelRepository import ModelRepository,RepositoryException
from mdig.Actions import RunAction

class DispersalModelTest(unittest.TestCase):

    def test_empty_model(self):
        dm = DispersalModel()
        self.assertEqual(dm.model_file, None)
        # Check root xml node has been created
        self.assertEqual(dm.xml_model.tag, "model")

    def test_model_constructor(self):
        # test bailing on creating models with bad combos
        dm = DispersalModel(the_action = RunAction())
        dm = DispersalModel(the_action = RunAction(), setup=False)
    
    @patch('mdig.LifestageTransition.LifestageTransition.xml_to_param')
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

        fn = models['management_use_maps']
        m = DispersalModel(fn)
        res = m.get_resources()
        self.assertEqual(len(res),3)
        self.assertEqual(len([i[0] for i in res if i[0] =='map']),3)
        self.assertEqual(len([i[0] for i in res if i[2] =='PERMANENT']),1)
        self.assertEqual(len([i[0] for i in res if i[2] is None]),2)
        del models['management_use_maps']

        # check the others don't erroneously report resources
        for k in models:
            fn = models[k]
            m = DispersalModel(fn)
            res = m.get_resources()
            self.assertEqual(len(res),0)

