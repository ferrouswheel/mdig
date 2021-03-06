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

class ModelRepositoryTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mdig_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def normal_repository_test(self):
        m = ModelRepository()
        models = m.get_models()
        self.assertEqual(len(models),13)
        self.assertTrue("lifestage_test" in models)
        self.assertTrue("variables" in models)
        self.assertTrue("management_area_combine" in models)
        self.assertTrue("management_delay" in models)
        self.assertTrue("management_event" in models)
        self.assertTrue("management_alter_variable" in models)
        # ... also others that are not explicitly checked

    def make_grass_mock(self,g):
        g.grass_vars = {}
        g.in_grass_shell = False
        g.check_mapset.return_value = False
        g.change_mapset.return_value = True
        g.create_mdig_subdir.return_value = os.path.join( \
                self.temp_dir,'grass_location/variables/mdig')
        c = config.get_config()
        gisdb = c['GRASS']['GISDBASE']
        g.grass_vars = {"GISDBASE": gisdb}

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

    @patch('mdig.grass.get_g')
    def remove_model_test(self,get_g):
        self.make_grass_mock(get_g.return_value)
        # Assume no appropriate files in tmp
        c = config.get_config()
        m = ModelRepository(self.temp_dir)
        self.assertEqual(len(m.get_models()), 0)

        # Try to add a model from one repository to the empty one
        try:
            self.remove_mock_location(self.temp_dir)
        except OSError, e:
            stre = str(e)
            if 'No such file' not in stre and \
                'system cannot find the path specified' not in stre:
                raise e
        m2 = ModelRepository()
        a_file = m2.get_models()['variables']
        self.create_mock_location(self.temp_dir)

        # Add location to model
        dm = DispersalModel(a_file)
        dm.set_location('grass_location')
        temp_model_fn = "with_location_model.xml"
        dm.save_model(filename=temp_model_fn)

        m.add_model(temp_model_fn)
        self.assertEqual(len(m.get_models()), 1)
        m.remove_model('variables',force=True)
        self.assertEqual(get_g.return_value.remove_mapset.call_args[0][0], 'variables')
        os.remove(temp_model_fn)

        self.assertRaises(mdig.modelrepository.RepositoryException,m.remove_model,'non_existant')
        self.remove_mock_location(self.temp_dir)

    @patch('mdig.grass.get_g')
    @patch('__builtin__.raw_input')
    def remove_other_test(self,m_in,get_g):
        self.make_grass_mock(get_g.return_value)
        # Assume no appropriate files in tmp
        c = config.get_config()
        m = ModelRepository(self.temp_dir)

        # Try to add a model from one repository to the empty one
        try: self.remove_mock_location(self.temp_dir)
        except OSError, e:
            stre = str(e)
            if 'No such file' not in stre and \
                'system cannot find the path specified' not in stre:
                raise e
        m2 = ModelRepository()
        a_file = m2.get_models()['variables']
        self.create_mock_location(self.temp_dir)

        # Add location to model
        dm = DispersalModel(a_file)
        dm.set_location('grass_location')
        temp_model_fn = "with_location_model.xml"
        dm.save_model(filename=temp_model_fn)

        m.add_model(temp_model_fn)
        m.remove_model('variables')

        self.assertRaises(RepositoryException,m.add_model,temp_model_fn)
        m_in.return_value.upper.return_value = 'Y'
        m.remove_model('variables')

        os.remove(temp_model_fn)
        self.remove_mock_location(self.temp_dir)

    @patch('mdig.grass.get_g')
    def empty_repository_test(self,get_g):
        self.make_grass_mock(get_g.return_value)
        # Assume no appropriate files in tmp
        c = config.get_config()
        
        m = ModelRepository(self.temp_dir)
        self.assertEqual(len(m.get_models()), 0)

        # Test that Repository gets db from shell when it exists
        g = get_g.return_value
        g.grass_vars["GISDBASE"] = self.temp_dir
        g.in_grass_shell = True
        m_in_grass = ModelRepository(self.temp_dir)
        self.assertEqual(m_in_grass.db, self.temp_dir)
        # Test with no specified dir
        m_in_grass = ModelRepository()
        self.assertEqual(m_in_grass.db, self.temp_dir)
        g.in_grass_shell = False
        # Test with dir missing
        self.assertRaises(OSError,ModelRepository,'invalid/dir')

        # Try to add a model from one repository to the empty one
        try: self.remove_mock_location(self.temp_dir)
        except OSError, e:
            stre = str(e)
            if 'No such file' not in stre and \
                'system cannot find the path specified' not in stre:
                raise e
        m2 = ModelRepository()
        a_file = m2.get_models()['variables']
        self.assertRaises(RepositoryException,m.add_model,a_file)
        self.assertEqual(len(m.get_models()), 0)

        # test trying to model with missing location
        self.create_mock_location(self.temp_dir)
        self.assertRaises(RepositoryException,m.add_model,a_file)
        self.assertEqual(len(m.get_models()), 0)
        # try invalid file
        self.assertRaises(RepositoryException,m.add_model,"invalid_file.xml")
        self.assertEqual(len(m.get_models()), 0)

        # add location to model, save as new
        dm = DispersalModel(a_file)
        dm.set_location('grass_location')
        temp_model_fn = "with_location_model.xml"
        dm.save_model(filename=temp_model_fn)

        # and then try to add
        m.add_model(temp_model_fn) 
        self.assertEqual(len(m.get_models()), 1)
        self.remove_mock_location(self.temp_dir)

        # test when mapset already exists with the name of model
        get_g.return_value.check_mapset.return_value = True
        m.get_models = Mock()
        m.get_models.return_value = {'variables':'blreerger'}
        self.assertRaises(mdig.modelrepository.RepositoryException,m.add_model,temp_model_fn)
        get_g.return_value.check_mapset.return_value = False
        m = ModelRepository(self.temp_dir)

        # test what happens if we can't create new mapset
        get_g.return_value.change_mapset.return_value = False
        self.create_mock_location(self.temp_dir)
        try:
            m.add_model(temp_model_fn)
            os.remove(temp_model_fn)
            self.fail("RepositoryException not generated")
        except RepositoryException, e:
            self.assertTrue("Couldn't create mapset" in str(e))
        self.remove_mock_location(self.temp_dir)
        get_g.return_value.change_mapset.return_value = True
        
        # test response when failure to create mdig dir 
        get_g.return_value.create_mdig_subdir.side_effect = OSError('test')
        self.create_mock_location(self.temp_dir)
        self.assertRaises(RepositoryException,m.add_model,temp_model_fn) 
        self.assertEqual(len(m.get_models()), 0)
        self.remove_mock_location(self.temp_dir)

        os.remove(temp_model_fn)

        # add invalid location to model, and test add
        dm = DispersalModel(a_file)
        dm.set_location('grass_location')
        temp_model_fn = "with_bad_location_model.xml"
        dm.save_model(filename=temp_model_fn)
        try:
            m.add_model(temp_model_fn)
            os.remove(temp_model_fn)
            self.fail("RepositoryException not generated")
        except RepositoryException, e: pass
        self.assertTrue("doesn't exist in" in str(e))
        os.remove(temp_model_fn)

    @patch('mdig.lifestagetransition.LifestageTransition.xml_to_param')
    @patch('mdig.grass.get_g')
    def test_add_lifestage_model(self,get_g,m_ls):
        self.make_grass_mock(get_g.return_value)
        # Assume no appropriate files in tmp
        c = config.get_config()
        m = ModelRepository(self.temp_dir)
        m2 = ModelRepository()
        a_file = m2.get_models()['lifestage_test']

        self.create_mock_location(self.temp_dir)
        self.assertEqual(len(m.get_models()), 0)
        # add location to model, save as new
        dm = DispersalModel(a_file)
        dm.set_location('grass_location')
        temp_model_fn = os.path.join(os.path.dirname(a_file),"with_location_model.xml")
        dm.save_model(filename=temp_model_fn)

        get_g.return_value.get_range.return_value = [ 'xxxxxx10' ] * 10
        get_g.return_value.raster_value_freq.return_value = [ [1],[2],[3] ]
        m_ls.return_value = {}

        # and then try to add
        m.add_model(temp_model_fn) 
        self.assertEqual(len(m.get_models()), 1)
        # more tests about lifestage resources?
        self.remove_mock_location(self.temp_dir)

    @patch('mdig.grass.get_g')
    def test_lifestage_model_missing_files(self,get_g):
        self.make_grass_mock(get_g.return_value)
        # Assume no appropriate files in tmp
        c = config.get_config()
        m = ModelRepository(self.temp_dir)
        m2 = ModelRepository()
        a_file = m2.get_models()['lifestage_test']

        self.create_mock_location(self.temp_dir)
        self.assertEqual(len(m.get_models()), 0)
        # add location to model, save as new
        dm = DispersalModel(a_file)
        dm.set_location('grass_location')
        temp_model_fn = os.path.join(self.temp_dir,"with_location_model.xml")
        dm.save_model(filename=temp_model_fn)

        # and then try to add
        self.assertRaises(mdig.modelrepository.RepositoryException,m.add_model,temp_model_fn) 
        self.assertEqual(len(m.get_models()), 0)
        # more tests about lifestage resources?
        self.remove_mock_location(self.temp_dir)

