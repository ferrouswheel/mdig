import unittest
from mock import *

import mdig
from mdig.model import DispersalModel
from mdig.modelrepository import ModelRepository,RepositoryException
from mdig.migrate import *

class Migrate0Test(unittest.TestCase):

    def setUp(self):
        c = config.get_config()
        self.r_dir = os.path.join(c['GRASS']['GISDBASE'],'migrate_tests/version-0')
        self.old_r_dir = os.path.join(c['GRASS']['GISDBASE'],'migrate_tests/version-0/repository')
        self.old_dbase = c['GRASS']['GISDBASE']
        c['GRASS']['GISDBASE'] = self.r_dir

    def tearDown(self):
        c = config.get_config()
        c['GRASS']['GISDBASE'] = self.old_dbase 

    @patch('__builtin__.raw_input')
    def test_migrate_old_repository(self,m_in):
        m_in.return_value = 'n'
        migrate_old_repository(self.old_r_dir,self.r_dir)
        m_in.return_value = 'y'
        migrate_old_repository(self.old_r_dir,self.r_dir)




class Migrate029Test(unittest.TestCase):

    def setUp(self):
        c = config.get_config()
        self.old_dbase = c['GRASS']['GISDBASE']
        self.m_dir = os.path.join(c['GRASS']['GISDBASE'],'migrate_tests/version-0.2.9')
        c['GRASS']['GISDBASE'] = self.m_dir

        print self.m_dir
        mdig.repository = ModelRepository(self.m_dir)
        self.models = mdig.repository.get_models()
        print self.models

    def tearDown(self):
        c = config.get_config()
        c['GRASS']['GISDBASE'] = self.old_dbase 

    @patch('mdig.grass.GRASSInterface.copy_map')
    @patch('mdig.grass.GRASSInterface.remove_map')
    def test_no_split_instances(self, m_remove_map, m_copy_map):
        m_fn = self.models['variables']
        dm = DispersalModel(m_fn)
        g = grass.get_g()
        split_instances_into_own_mapsets(dm)
        self.assertEqual(m_remove_map.call_count, 0)
        self.assertEqual(m_copy_map.call_count, 0)

    @patch('mdig.grass.GRASSInterface.copy_map')
    @patch('mdig.grass.GRASSInterface.remove_map')
    def test_split_instances(self, m_remove_map, m_copy_map):
        m_fn = self.models['variables_split']
        dm = DispersalModel(m_fn)
        g = grass.get_g()
        split_instances_into_own_mapsets(dm)
        self.assertEqual(m_remove_map.call_count, m_copy_map.call_count)

    #@patch('mdig.grass.grass.remove_map')
    def test_check_info(self): #, m_remove_map, m_copy_map):
        m_fn = self.models['variables']
        dm = DispersalModel(m_fn)
        g = grass.get_g()
        check_instances_have_info_file(dm.get_instances())
        #self.assertEqual(m_remove_map.call_count, m_copy_map.call_count)

    #@patch('mdig.grass.get_g')
    @patch('mdig.migrate.check_instances_have_info_file')
    @patch('mdig.migrate.split_instances_into_own_mapsets')
    def test_migrate_repository(self,m_split,m_check_info):# ,m_g):
        #m_g.return_value.grass_vars = {'LOCATION_NAME': 'grass_location'}
        #m_g.return_value.check_mapset.return_value = False
        migrate_repository(self.m_dir)
        self.assertEqual(m_split.call_count, 1)
        self.assertEqual(m_check_info.call_count, 1)
    
