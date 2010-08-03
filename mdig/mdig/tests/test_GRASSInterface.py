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

class MapNotFoundExceptionTest(unittest.TestCase):

    def test_construct(self):
        e = GRASSInterface.MapNotFoundException()
        self.assertTrue('MapNotFoundException' in str(e))
        e = GRASSInterface.MapNotFoundException('blag')
        self.assertTrue('blag' in str(e))


class GRASSCommandExceptionTest(unittest.TestCase):
    
    def test_no_args(self):
        e = GRASSInterface.GRASSCommandException()
        self.assertTrue('Command' in str(e))

    def test_construct(self):
        e = GRASSInterface.GRASSCommandException('g.region','my face',10)
        self.assertTrue('g.region' in str(e))
        self.assertTrue('10' in str(e))

class GRASSInterfaceTest(unittest.TestCase):

    def setUp(self):
        self.g = GRASSInterface.GRASSInterface()

    def tearDown(self):
        self.g.clean_up()
        del self.g

    def test_backup_region(self):
        g = self.g
        m_run = g.run_command = Mock()
        g.backup_region()

        m_run.side_effect = GRASSInterface.GRASSCommandException()
        self.assertRaises(GRASSInterface.GRASSCommandException,g.backup_region)

        m_run.side_effect = GRASSInterface.GRASSCommandException('g.region','',1)
        self.assertRaises(GRASSInterface.EnvironmentException,g.backup_region)

    def test_check_environment(self):
        g = self.g
        m_run = g.run_command = Mock()
        m_get_env = g.get_gis_env = Mock()
        import os
        # backup vars to allow succesful cleanup
        old_python = g.grass_vars['GRASS_PYTHON']
        old_rc_file = g.grass_vars['GISRC']
        # remove var otherwise it doesn't get reloaded
        del g.grass_vars['GRASS_PYTHON']
        # add test values to environ
        os.environ['GISRC'] = 'robocop'
        os.environ['GRASS_PYTHON'] = 'robocop2'

        g.check_environment()
        self.assertEqual(g.grass_vars['GISRC'],'robocop')
        self.assertEqual(g.grass_vars['GRASS_PYTHON'],'robocop2')
        self.assertEqual(m_get_env.call_count, 1)

        #remove test files from environ
        os.environ['GISRC'] = old_rc_file
        g.grass_vars['GISRC'] = old_rc_file
        os.environ['GRASS_PYTHON'] = old_python
        g.grass_vars['GRASS_PYTHON'] = old_python

    def test_check_paths(self):
        g = self.g
        self.assertTrue(g.check_paths())

        old_path = g.grass_vars['GISDBASE']
        g.grass_vars['GISDBASE'] = 'firbble'
        self.assertFalse(g.check_paths())
        g.grass_vars['GISDBASE'] = old_path

        old_path = g.grass_vars['LOCATION_NAME']
        g.grass_vars['LOCATION_NAME'] = 'firbble'
        self.assertFalse(g.check_paths())
        g.grass_vars['LOCATION_NAME'] = old_path

        old_path = g.grass_vars['MAPSET']
        g.grass_vars['MAPSET'] = 'firbble'
        self.assertFalse(g.check_paths())
        g.grass_vars['MAPSET'] = old_path

        old_path = g.grass_vars['GISBASE']
        g.grass_vars['GISBASE'] = 'firbble'
        self.assertFalse(g.check_paths())
        g.grass_vars['GISBASE'] = old_path

    def test_clear_monitor(self):
        g = self.g
        os.environ['GRASS_PNG_READ']="TRUE"
        g.clear_monitor()
        self.assertEqual(os.environ['GRASS_PNG_READ'],"FALSE")
        
    @patch('subprocess.Popen')
    def test_paint_map(self,m_popen):
        g = self.g
        m_popen.return_value.communicate.return_value = ['','']
        m_popen.return_value.returncode = 0
        m_run = g.run_command = Mock()
        # no layer info...
        g.paint_map('a_map')
        self.assertEqual(os.environ['GRASS_PNG_READ'],"TRUE")
        self.assertEqual(m_popen.call_count,0)
        self.assertEqual(m_run.call_count,1)
        # specify layer for color setting...
        g.paint_map('a_map',layer=1)
        self.assertEqual(m_popen.call_count,1)
        self.assertEqual(m_run.call_count,2)
        # invalid layer...
        self.assertRaises(ValueError,
                g.paint_map,'a_map',layer='blerg')
        self.assertEqual(m_popen.call_count,1)
        self.assertEqual(m_run.call_count,2)
        # r.color fail
        m_popen.return_value.returncode = 1
        self.assertRaises(GRASSInterface.GRASSCommandException,
                g.paint_map,'a_map',layer=1)
        self.assertEqual(m_popen.call_count,2)

    @patch('subprocess.Popen')
    def test_normalise_map_colors(self,m_popen):
        pass






    


