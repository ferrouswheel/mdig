import unittest
from mock import *

import os
import tempfile

import mdig
from mdig import MDiGConfig
from mdig import GRASSInterface 
from mdig.DispersalModel import DispersalModel
from mdig.Actions import RunAction
from mdig.ModelRepository import ModelRepository,RepositoryException

class RepositoryTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp("mdig_test_")

    def teardown(self):
        shutil.rmtree(self.temp_dir)

    def normal_repository_test(self):
        m = ModelRepository()
        models = m.get_models()
        self.assertEqual(len(models),6)
        self.assertTrue("lifestage_test" in models)
        self.assertTrue("variables" in models)
        self.assertTrue("management_area_combine" in models)
        self.assertTrue("management_delay" in models)
        self.assertTrue("management_event" in models)
        self.assertTrue("management_alter_variable" in models)

    def make_grass_mock(self,g):
        g.grass_vars = {}
        g.check_mapset.return_value = False
        g.change_mapset.return_value = True
        g.create_mdig_subdir.return_value = os.path.join( \
                self.temp_dir,'grass_location/variables/mdig')

    def create_mock_location(self,db_path):
        try: os.mkdir(os.path.join(db_path,'grass_location'))
        except OSError, e:
            # It's okay if the file exists
            if 'File exists' not in e: raise e
        # Have to create all of these as the GRASS interface is mocked
        try: os.mkdir(os.path.join(db_path,'grass_location','PERMANENT'))
        except OSError, e:
            if 'File exists' not in str(e): raise e
        try: os.mkdir(os.path.join(db_path,'grass_location','variables'))
        except OSError, e:
            if 'File exists' not in str(e): raise e
        try: os.mkdir(os.path.join(db_path,'grass_location','variables','mdig'))
        except OSError, e:
            if 'File exists' not in str(e): raise e

    def remove_mock_location(self,db_path):
        import shutil
        shutil.rmtree(os.path.join(db_path,'grass_location'))

    @patch('mdig.GRASSInterface.get_g') # prevent beanstalk queue connection
    def empty_repository_test(self,get_g):
        self.make_grass_mock(get_g.return_value)
        # Assume no appropriate files in tmp
        m = ModelRepository(self.temp_dir)
        self.assertEqual(len(m.get_models()), 0)

        # Try to add a model from one repository to the empty one
        try: self.remove_mock_location(self.temp_dir)
        except OSError, e:
            if 'No such file' not in str(e): raise e
            # okay if file exists
        m2 = ModelRepository()
        a_file = m2.get_models()['variables']
        self.assertRaises(RepositoryException,m.add_model,a_file)
        self.assertEqual(len(m.get_models()), 0)

        self.create_mock_location(self.temp_dir)
        m.add_model(a_file)
        self.assertEqual(len(m.get_models()), 1)
        self.remove_mock_location(self.temp_dir)

class DispersalModelTest(unittest.TestCase):

    def empty_model_test(self):
        dm = DispersalModel()
        self.assertEqual(dm.model_file, None)
        # Check root xml node has been created
        self.assertEqual(dm.xml_model.tag, "model")

    def model_constructor_test(self):
        # test bailing on creating models with bad combos
        dm = DispersalModel(the_action = RunAction())
        dm = DispersalModel(the_action = RunAction(), setup=False)

