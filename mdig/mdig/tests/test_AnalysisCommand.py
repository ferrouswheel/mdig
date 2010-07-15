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
from mdig.AnalysisCommand import AnalysisCommand, OutputFileNotSetException
from mdig import NotEnoughHistoryException

class AnalysisCommandTest(unittest.TestCase):

    def setUp(self):
        mdig.repository = self.repo = ModelRepository()

    def test_constructor(self):
        #TODO ensure that cmd_string is actually a string or streamable
        pass

    @patch('os.path.isfile')
    @patch('os.remove')
    def test_init_output_file(self,rm_mock,isfile_mock):
        isfile_mock.return_value = True
        mdig_config = MDiGConfig.get_config()
        mdig_config.overwrite_flag = False
        model_fn = self.repo.get_models()['lifestage_test']
        model = DispersalModel(model_fn,setup=False)
        i = model.get_instances()[0]
        ac = AnalysisCommand("test")
        self.assertRaises(mdig.OutputFileExistsException, ac.init_output_file, i)
        mdig_config.overwrite_flag = True
        output_file = ac.init_output_file(i)
        self.assertEqual(output_file.index("lifestage_test_region_a_i0"), 0)

        # test with rep
        isfile_mock.return_value = False
        output_file = ac.init_output_file(i, i.replicates[0])
        print output_file
        self.assertEqual(output_file.index("lifestage_test_region_a_i0_rep_0"), 0)

    def test_insert_output_into_cmd(self):
        model_fn = self.repo.get_models()['lifestage_test']
        model = DispersalModel(model_fn,setup=False)
        i = model.get_instances()[0]
        ac = AnalysisCommand("test")
        # test exception for when no output file initialised
        self.assertRaises(OutputFileNotSetException,ac.insert_output_into_cmd)
        # check normal function works
        output_file = ac.init_output_file(i)
        self.assertEqual(output_file.index("lifestage_test_region_a_"), 0)
        output_cmd = ac.insert_output_into_cmd()
        self.assertEqual(output_cmd, "test >> " + output_file)
        # check that file substitution works 
        ac.cmd_string = "test %f"
        output_cmd = ac.insert_output_into_cmd()
        self.assertEqual(output_cmd, "test " + output_file)
        # check that it doesn't replaced escaped %
        ac.cmd_string = "test %%f"
        output_cmd = ac.insert_output_into_cmd()
        self.assertEqual(output_cmd, "test %%f >> " + output_file)

    @patch.object(AnalysisCommand, 'run_command_once')
    def test_run_command(self, rc_mock):
        model_fn = self.repo.get_models()['lifestage_test']
        model = DispersalModel(model_fn,setup=False)
        i = model.get_instances()[0]
        ac = AnalysisCommand("test")
        # test when there are no times set for when to run command
        self.assertRaises(Exception, ac.run_command, maps=[])
        # test when the times are empty list
        ac.times=[]
        output_file = ac.init_output_file(i)
        ac.run_command([])
        self.assertEqual(rc_mock.called,False)
        # test when there are times
        ac.times=[1990]
        rc_mock.called = False
        ac.run_command([])
        self.assertEqual(rc_mock.called,True)

    @patch('os.popen')
    def test_run_command_once(self,po_mock):
        # expect return value from function of 0
        po_mock.return_value.close.return_value = 0
        model_fn = self.repo.get_models()['lifestage_test']
        model = DispersalModel(model_fn,setup=False)
        i = model.get_instances()[0]
        ac = AnalysisCommand("test")
        # test normal
        ac.times=[1990,1991,1992]
        t_strings = [str(x) for x in ac.times]
        maps = ['map1','map2','map3']
        maps = dict(zip(t_strings, maps))
        return_val = ac.run_command_once(1990,maps,"testcommand")
        self.assertEqual(return_val, 0)
        # test with map_name replacements, but too early
        self.assertRaises(IndexError,ac.run_command_once, 1991,maps,"testcommand %1 %2")
        # test with map_name replacements
        return_val = ac.run_command_once(1991,maps,"testcommand %1")
        self.assertEqual(po_mock.call_args[0][0], "testcommand map1")
        return_val = ac.run_command_once(1990,maps,"testcommand %0")
        self.assertEqual(po_mock.call_args[0][0], "testcommand map1")
        return_val = ac.run_command_once(1992,maps,"testcommand %0")
        self.assertEqual(po_mock.call_args[0][0], "testcommand map3")
        mdig_config = MDiGConfig.get_config()
        mdig_config.analysis_print_time = True
        self.__do_run_command_once(model,ac,maps)

    @patch('__builtin__.open')
    def __do_run_command_once(self,model,ac,maps,open_mock):
        # test printing analysis
        ac.output_fn = "output.txt"
        return_val = ac.run_command_once(1992,maps,"testcommand %0")
        self.assertEqual(open_mock.call_args[0][0],ac.output_fn)
    
    def test_set_times(self):
        model_fn = self.repo.get_models()['lifestage_test']
        model = DispersalModel(model_fn,setup=False)
        i = model.get_instances()[0]
        ac = AnalysisCommand("test")
        o_times=range(1990,2000)
        # Test running on all available times
        ac.set_times((1990,1999),o_times)
        self.assertEquals(ac.times,o_times)
        # Test with a single time in range
        ac.set_times((1990,1999),o_times,[1990])
        self.assertEquals(ac.times,[1990])
        # Test with a single time out of range
        self.assertRaises(ValueError,ac.set_times,(1990,1999),o_times,[11990])
        # Test with a single negative index
        ac.set_times((1990,1999),o_times,[-1])
        self.assertEquals(ac.times,[1999])
        # Test with time not in original times
        del o_times[2] # delete 1992
        self.assertRaises(ValueError,ac.set_times,(1990,1999),o_times,[1992])
        # Test earliest time and not enough past maps to fulfill command line
        ac = AnalysisCommand("test %19")
        self.assertRaises(NotEnoughHistoryException,ac.set_times,(1990,1999),o_times,[-1])

    def test_get_earliest_time(self):
        # Test that normal use works
        ac = AnalysisCommand("test %1")
        self.assertEquals(ac.get_earliest_time(), 1)
        # Test that no time in command works == 0
        ac = AnalysisCommand("test")
        self.assertEquals(ac.get_earliest_time(), 0)
        # Test that % can be escaped
        ac = AnalysisCommand("test %% %1")
        self.assertEquals(ac.get_earliest_time(), 1)
        # Test that earliest map is found
        ac = AnalysisCommand("test %1 %2 %19 %1")
        self.assertEquals(ac.get_earliest_time(), 19)
        # Test that future maps don't work
        ac = AnalysisCommand("test %-1")
        self.assertEquals(ac.get_earliest_time(), 0)

    def test_get_output_filename_base(self):
        ac = AnalysisCommand("test %1")
        mdig_config = MDiGConfig.get_config()
        spam = "woooo"
        old_base = mdig_config.analysis_filename_base
        mdig_config.analysis_filename_base = spam
        self.assertTrue(spam in ac.get_output_filename_base())
        mdig_config.analysis_filename_base = old_base

