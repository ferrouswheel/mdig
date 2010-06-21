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
from mdig.Actions import RunAction
from mdig.ModelRepository import ModelRepository,RepositoryException
from mdig.DispersalInstance import InvalidLifestageException, \
        InstanceIncompleteException, InvalidReplicateException, NoOccupancyEnvelopesException

class RepositoryTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mdig_test_")

    def tearDown(self):
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
        g.in_grass_shell = False
        g.check_mapset.return_value = False
        g.change_mapset.return_value = True
        g.create_mdig_subdir.return_value = os.path.join( \
                self.temp_dir,'grass_location/variables/mdig')
        g.grass_vars = {"GISDBASE": None}

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

    @patch('mdig.GRASSInterface.get_g')
    def remove_model_test(self,get_g):
        self.make_grass_mock(get_g.return_value)
        # Assume no appropriate files in tmp
        c = MDiGConfig.get_config()
        m = ModelRepository(self.temp_dir)
        self.assertEqual(len(m.get_models()), 0)

        # Try to add a model from one repository to the empty one
        try: self.remove_mock_location(self.temp_dir)
        except OSError, e:
            if 'No such file' not in str(e): raise e
        m2 = ModelRepository()
        a_file = m2.get_models()['variables']
        self.create_mock_location(self.temp_dir)
        m.add_model(a_file)
        self.assertEqual(len(m.get_models()), 1)
        m.remove_model('variables',force=True)
        self.assertEqual(get_g.return_value.remove_mapset.call_args[0][0], 'variables')
        self.remove_mock_location(self.temp_dir)

    @patch('mdig.GRASSInterface.get_g')
    def empty_repository_test(self,get_g):
        self.make_grass_mock(get_g.return_value)
        # Assume no appropriate files in tmp
        c = MDiGConfig.get_config()
        
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
            if 'No such file' not in str(e): raise e
        m2 = ModelRepository()
        a_file = m2.get_models()['variables']
        self.assertRaises(RepositoryException,m.add_model,a_file)
        self.assertEqual(len(m.get_models()), 0)

        self.create_mock_location(self.temp_dir)
        m.add_model(a_file)
        self.assertEqual(len(m.get_models()), 1)
        self.assertRaises(RepositoryException,m.add_model,"invalid_file.xml")
        self.remove_mock_location(self.temp_dir)

        # test trying to model with missing location
        dm = DispersalModel(a_file)
        nodes = dm.xml_model.xpath('/model/GISLocation')
        nodes[0].getparent().remove(nodes[0])
        temp_model_fn = "no_location_model.xml"
        dm.save_model(filename=temp_model_fn)
        self.assertRaises(RepositoryException,m.add_model,temp_model_fn) 
        os.remove(temp_model_fn)

        # test when mapset already exists with the name of model
        get_g.return_value.check_mapset.return_value = True
        self.create_mock_location(self.temp_dir)
        e = ""
        try:
            m.add_model(a_file)
        except RepositoryException, e:
            pass
        self.assertTrue("it already exists" in str(e))
        self.remove_mock_location(self.temp_dir)
        get_g.return_value.check_mapset.return_value = False

        # test what happens if we can't create new mapset
        get_g.return_value.change_mapset.return_value = False
        self.create_mock_location(self.temp_dir)
        e = ""
        try:
            m.add_model(a_file)
        except RepositoryException, e:
            pass
        self.assertTrue("Couldn't create mapset" in str(e))
        self.remove_mock_location(self.temp_dir)
        get_g.return_value.change_mapset.return_value = True


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

        # check the others don't erroneously report resources
        for k in models:
            fn = models[k]
            m = DispersalModel(fn)
            res = m.get_resources()
            self.assertEqual(len(res),0)

class DispersalInstanceTest(unittest.TestCase):

    def setUp(self):
        mdig.repository = self.repo = ModelRepository()
        fn = mdig.repository.get_models()['lifestage_test']
        self.m_lifestage = DispersalModel(fn)

        # Model initialise with management strategy
        fn = mdig.repository.get_models()['management_alter_variable']
        self.m_strategy = DispersalModel(fn)
        
        # Model initialise with variables
        fn = mdig.repository.get_models()['variables']
        self.m_variables = DispersalModel(fn)

    def testDown(self):
        pass

    def test_load_replicates(self):
        # replicates loaded on init
        self.m_lifestage.get_instances()
        self.m_strategy.get_instances()
        self.m_variables.get_instances()

    def test_get_mapset(self):
        i = self.m_lifestage.get_instances()[0]
        self.assertEqual(i.get_mapset().find('lifestage_test_i'), 0)
        del i.node.attrib['mapset']
        self.assertEqual(i.get_mapset(),'lifestage_test')

    def test_set_mapset(self):
        i = self.m_lifestage.get_instances()[0]
        i.set_mapset('blah')
        self.assertEqual(i.node.attrib['mapset'], 'blah')

    def test_add_envelope(self):
        i = self.m_variables.get_instances()[0]
        i._add_envelope('test_envelope','all',1)
        e = i.node.find('envelopes')
        self.assertEqual(len(e),1)
        # second add doesn't have to init xml structure
        i._add_envelope('test_envelope','all',1)
        self.assertEqual(len(e),1)

    def test_update_xml(self):
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
        i = self.m_variables.get_instances()[0]
        self.assertRaises(InstanceIncompleteException,i.update_occupancy_envelope)
        #i.is_complete = True
        # TODO need a instance that actually has some replicates
        #i.update_occupancy_envelope()

        # test without rep maps
        #i.saved_maps = {}
        #m_get_g.return_value.occupancy_envelope.return_value = "test_env"
        #i = self.m_variables.get_instances()[0]
        #i.update_occupancy_envelope(force=True)

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
        self.assertEqual(output_file.index("lifestage_test_region_a_"), 0)

        # test with rep
        isfile_mock.return_value = False
        output_file = ac.init_output_file(i, i.replicates[0])
        self.assertEqual(output_file.index("lifestage_test_region_a_0_"), 0)

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

    @patch_object(AnalysisCommand, 'run_command_once')
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

from mdig import Actions

class ExportActionTest(unittest.TestCase):

    def setUp(self):
        mdig.repository = self.repo = ModelRepository()

    def test_create(self):
        ea = Actions.ExportAction()

    def test_act_on_options(self):
        ea = Actions.ExportAction()
        ea.parse_options([])
    
    def test_do_me(self):
        ea = Actions.ExportAction()
        fn = mdig.repository.get_models()['variables']
        m = DispersalModel(fn)
        ea.parse_options([])
        self.assertRaises(SystemExit,ea.do_me,m)

        ea.options.output_map_pack = True
        ea.do_instance_map_pack = Mock()
        ea.do_me(m)
        self.assertEqual(ea.do_instance_map_pack.call_count, 6)

        ea.do_instance_map_pack.call_count = 0
        ea.options.instances = [0]
        ea.do_me(m)
        self.assertEqual(ea.do_instance_map_pack.call_count, 1)

        ea.do_instance_map_pack.call_count = 0
        ea.options.instances = [1231]
        self.assertRaises(SystemExit,ea.do_me,m)

        ea.do_instance_map_pack.call_count = 0
        ea.options.instances = ['monkey']
        self.assertRaises(SystemExit,ea.do_me,m)

        ea.options.output_image = True
        ea.do_instance_images = Mock()
        ea.options.instances = None
        ea.do_me(m)
        self.assertEqual(ea.do_instance_map_pack.call_count, 6)

    @patch('mdig.GRASSInterface.get_g')
    @patch('os.remove')
    def test_do_instance_map_pack(self,m_rm,m_g):
        m_g.return_value.grass_vars = {}
        ea = Actions.ExportAction()
        fn = mdig.repository.get_models()['variables']
        m = DispersalModel(fn)
        ea.parse_options([])
        ea.export_map = Mock()
        ea.zip_maps = Mock()
        # TODO create replicates so this all works
        #instances = m.get_instances()
        ea.options.reps=[0]
        # No replicates in a fresh model
        #self.assertRaises(InvalidReplicateException,ea.do_instance_map_pack,instances[0])

        #ea.do_instance_map_pack(instances[0])

    @patch('mdig.GRASSInterface.get_g')
    @patch('os.remove')
    def test_do_instance_images(self,m_rm,m_g):
        m_g.return_value.grass_vars = {}
        ea = Actions.ExportAction()
        fn = mdig.repository.get_models()['variables']
        m = DispersalModel(fn)
        ea.parse_options([])
        ea.create_frame = Mock()
        ea.create_gif = Mock()
        # TODO create replicates so this all works
        # instances = m.get_instances()
        ea.options.reps=[0]
        # No replicates in a fresh model
        # self.assertRaises(InvalidReplicateException,ea.do_instance_images,instances[0])
        # create mock replicate
        #instances[0].replicates = [Mock()]
        #instances[0].replicates[0].get_saved_maps.return_value = {'1':'xx','2':'yy'}
        #instances[0].replicates[0].get_img_filenames.return_value = {'1':'xx','2':'yy'}
        # ea.do_instance_images(instances[0])

from mdig import WebService

class ResultsMonitorTest(unittest.TestCase):

    def run_counter(self,timeout=None):
        self.rm.running = False
        return self.result

    def test_run(self):
        self.rm=WebService.ResultMonitor(Mock())
        self.rm.running = True
        self.result = {'action':'sss'}
        self.rm.result_q.get.side_effect = self.run_counter
        self.rm.run()

class MDiGWorkTest(unittest.TestCase):

    @patch('mdig.WebService.MDiGWorker')
    @patch('mdig.GRASSInterface.get_g')
    def test_worker_start(self,m_g,m_worker):
        m_g.return_value.grass_vars = {}
        WebService.mdig_worker_start('a','b')
        self.assertEqual(m_g.return_value.grass_vars['MAPSET'],"PERMANENT")
        self.assertEqual(m_worker.call_args[0],('a','b'))

from mdig.bottle import app, HTTPError, HTTPResponse, run
import mdig.bottle
import mdig.tests.tools as tools
class WebServiceTest(tools.ServerTestBase):

    def setUp(self):
        self.port = 8080
        self.host = 'localhost'
        self.app = mdig.bottle.app()
        import wsgiref.validate
        self.wsgiapp = wsgiref.validate.validator(self.app)
        mdig.repository = self.repo = ModelRepository()

    def tearDown(self):
        pass

    def test_404(self):
        self.assertStatus(404,'/felgrul')

    def test_models_redirect(self):
        self.assertStatus(303,'/models')
        self.assertStatus(303,'/models/')

    def test_handle_index(self):
        r = self.urlopen('/')

    def test_handle_model_w_lifestages(self):
        r = self.urlopen('/models/lifestage_test')

    def test_handle_bad_model(self):
        self.assertStatus(404,'/models/flergul')

    def test_handle_model_instance(self):
        r = self.urlopen('/models/lifestage_test/instances/0')

    def test_handle_model_bad_instance(self):
        self.assertStatus(403,'/models/lifestage_test/instances/asdas')
        self.assertStatus(404,'/models/lifestage_test/instances/111')
        self.assertStatus(404,'/models/lifestage_test/instances/-11')

    def test_handle_model_replicate(self):
        r = self.urlopen('/models/lifestage_test/instances/0/replicates/0')

    def test_handle_model_bad_replicate(self):
        self.assertStatus(403,'/models/lifestage_test/instances/0/replicates/asdasd')
        self.assertStatus(404,'/models/lifestage_test/instances/0/replicates/10101')
        self.assertStatus(404,'/models/lifestage_test/instances/0/replicates/-111')

    def test_process_tasks(self):
        now = datetime.datetime.now() 
        WebService.models_in_queue = {
            "lifestage_test": {
                "RUN" : { 
                    'last_update': now - datetime.timedelta(seconds=100)
                    },
                "OCCUPANCY_GIF": {
                    'last_update': now - datetime.timedelta(seconds=500)
                    }
                }
            }
        before_complete = WebService.last_notice
        updates=WebService.process_tasks()
        self.assertEqual(WebService.last_notice, before_complete)
        before_complete = WebService.last_notice
        WebService.models_in_queue['lifestage_test']['RUN']['complete']= \
                datetime.datetime.now()
        updates=WebService.process_tasks()
        self.assertTrue(WebService.last_notice > before_complete)

        # test to ensure old completed actions are removed:
        WebService.models_in_queue['lifestage_test']['RUN']['last_update']= \
                datetime.datetime.now() - datetime.timedelta(days=8)
        updates=WebService.process_tasks()
        self.assertTrue('RUN' not in \
                WebService.models_in_queue['lifestage_test']) 

    def test_process_tasks_errors(self):
        # test errors
        now = datetime.datetime.now() 
        WebService.models_in_queue = {
            "lifestage_test": {
                "RUN" : { 
                    'last_update': now,
                    'error': "test error"
                    },
                "OCCUPANCY_GIF": {
                    'last_update': now - datetime.timedelta(seconds=1)
                    }
                }
            }
        before_complete = WebService.last_notice
        updates=WebService.process_tasks()
        self.assertEqual(updates[0][0][0], 'lifestage_test')
        self.assertEqual(updates[0][0][1], 'OCCUPANCY_GIF')
        self.assertEqual(updates[0][1][1], 'RUN')
        before_complete = WebService.last_notice

        # ensure error message disappears
        updates=WebService.process_tasks()
        self.assertEqual(WebService.last_notice, before_complete)
        self.assertEqual(len(updates[0]), 1)

    def test_shutdown_webapp(self):
        WebService.shutdown_webapp()
        WebService.app = self.app
        WebService.shutdown_webapp()

    @patch('mdig.bottle.run')
    def test_start_webapp(self,m_run):
        WebService.start_web_service()
        WebService.shutdown_webapp()

    def test_change_to_mapset(self):
        WebService.change_to_web_mapset()

    @patch('os.remove')
    @patch('mdig.WebService.get_map_pack_usage')
    def test_purge_oldest_map_packs(self,m_usage,m_rm):
        m_usage.return_value = 0.0
        # check that empty lfu does nothing
        WebService.map_pack_lfu = []
        WebService.purge_oldest_map_packs()
        self.assertEqual(len(WebService.map_pack_lfu),0)
        self.assertEqual(m_rm.call_count,0)

        m_usage.return_value = 2000.0
        WebService.map_pack_lfu = [('test1',None),
                ('test2',datetime.datetime.now())]
        WebService.purge_oldest_map_packs()
        self.assertEqual(m_rm.call_count,1)
        self.assertEqual(len(WebService.map_pack_lfu),1)

        # Test when removal throws a no such file error with date
        WebService.map_pack_lfu = [('test2',datetime.datetime.now()),('test1',None)]
        m_rm.side_effect = OSError("No such file")
        WebService.purge_oldest_map_packs()
        self.assertEqual(len(WebService.map_pack_lfu),1)

        # Test when removal throws a no such file error on a None date
        WebService.map_pack_lfu = [('test1',None),
                ('test2',datetime.datetime.now())]
        m_rm.side_effect = OSError("No such file")
        WebService.purge_oldest_map_packs()
        self.assertEqual(len(WebService.map_pack_lfu),1)

        # Test what happens when the OSError isn't to do with a invalid file
        WebService.map_pack_lfu = [('test2',datetime.datetime.now()),('test1',None)]
        m_rm.side_effect = OSError("Another OS error")
        self.assertRaises(OSError,WebService.purge_oldest_map_packs)

    @patch('os.path.getsize')
    def test_get_map_pack_usage(self,m_sz):
        five_megs = 1024*1024*5
        m_sz.return_value = five_megs
        WebService.map_pack_lfu = [('test1',None),
                ('test2',datetime.datetime.now())]
        usage = WebService.get_map_pack_usage()
        self.assertEqual(usage, five_megs * 2 / (1024*1024))

        m_sz.side_effect = OSError()
        WebService.map_pack_lfu = [('test1',None),
                ('test2',datetime.datetime.now())]
        usage = WebService.get_map_pack_usage()
        self.assertEqual(usage, 0.0)
        self.assertEqual(len(WebService.map_pack_lfu),1)

    def test_add_to_map_pack(self):
        WebService.map_pack_lfu = []
        # test empty
        WebService.add_to_map_pack_lfu('test1')
        self.assertEqual(WebService.map_pack_lfu[0][0],'test1')

        # test not in lfu
        WebService.add_to_map_pack_lfu('test2',nodate=True)
        self.assertEqual(WebService.map_pack_lfu[1][0],'test2')
        self.assertEqual(WebService.map_pack_lfu[1][1],None)

        # test replace none with date
        WebService.add_to_map_pack_lfu('test2')
        self.assertNotEqual(WebService.map_pack_lfu[1][1],None)
        print WebService.map_pack_lfu

        # test replace with none 
        WebService.add_to_map_pack_lfu('test1',nodate=True)
        print WebService.map_pack_lfu
        self.assertEqual(WebService.map_pack_lfu[1][1],None)

        # test update date
        old_date = WebService.map_pack_lfu[0][1]
        WebService.add_to_map_pack_lfu('test2')
        self.assertTrue(WebService.map_pack_lfu[1][1]>old_date)

    def test_run_model(self):
        WebService.mdig_worker_process = Mock()
        #import pdb; pdb.set_trace()

        WebService.models_in_queue = {}
        r = self.urlopen('/models/lifestage_test/run',method='POST',post='rerun=true')
        self.assertTrue('RUN' in WebService.models_in_queue['lifestage_test']) 

        WebService.models_in_queue = {'lifestage_test':
                {'OCCUPANCY_GIF': {
                    'last_update': datetime.datetime(2010, 6, 15, 16, 24, 36, 171171)
                    }
                }
            }
        r = self.urlopen('/models/lifestage_test/run',method='POST',post='rerun=true')
        self.assertTrue('RUN' in WebService.models_in_queue['lifestage_test']) 
        r = self.urlopen('/models/lifestage_test/run',method='POST',post='rerun=true')
        self.assertTrue('RUN' in WebService.models_in_queue['lifestage_test']) 


from mdig.GrassMap import GrassMap
from StringIO import StringIO
class GrassMapTest(unittest.TestCase):
    
    @patch('mdig.GRASSInterface.get_g')
    def test_create_sites_map(self,get_g):
        from lxml import etree
        xml = """<sites>
          <s x="1" y="0" count="100"/>
          <s x="2" y="0"/>
          <s x="3" y="0"/>
          <s x="4" y="0"/>
          <s x="5" y="0"/>
          <s x="0" y="-5"/>
        </sites>"""
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        gmap = GrassMap(xml_node = map_node)
        self.assertEqual(len(gmap.value), 6)

        get_g.return_value.init_map.return_value = ("test","a_map_type")
        get_g.return_value.get_mapset.return_value = "a_mapset"
        a = gmap.getMapFilename()
        b = gmap.getMapFilename()
        self.assertEqual(get_g.return_value.init_map.call_count,1)
        self.assertEqual(gmap.ready, True)
        self.assertEqual(gmap.mapset, "a_mapset")

    @patch('mdig.GRASSInterface.get_g')
    def test_create_name_map(self,get_g):
        from lxml import etree
        xml = "<map>nz_DEM</map>"
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        gmap = GrassMap(xml_node = map_node)
        self.assertEqual(gmap.value, "nz_DEM")
        self.assertEqual(gmap.filename, "nz_DEM")
        self.assertEqual(gmap.xml_map_type, "name")

    @patch('mdig.GRASSInterface.get_g')
    def test_create_value_map(self,get_g):
        from lxml import etree
        xml = "<value>1</value>"
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        gmap = GrassMap(xml_node = map_node)
        self.assertEqual(gmap.value, "1")
        self.assertEqual(gmap.xml_map_type, "value")

    @patch('mdig.GRASSInterface.get_g')
    def test_create_mapcalc_map(self,get_g):
        from lxml import etree
        xml = "<mapcalc>if(isnull(nz_DEM),x(),nz_DEM)</mapcalc>"
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        gmap = GrassMap(xml_node = map_node)
        self.assertEqual(gmap.xml_map_type, "mapcalc")
        self.assertEqual(gmap.refresh, False)

        xml = "<mapcalc refresh=\"true\">if(isnull(nz_DEM),x(),nz_DEM)</mapcalc>"
        tree = etree.parse(StringIO(xml))
        map_node = tree.getroot()
        gmap = GrassMap(xml_node = map_node)
        self.assertEqual(gmap.xml_map_type, "mapcalc")
        self.assertEqual(gmap.refresh, True)

        get_g.return_value.init_map.return_value = ("test","a_map_type")
        get_g.return_value.get_mapset.return_value = "a_mapset"
        a = gmap.getMapFilename()
        b = gmap.getMapFilename()
        self.assertEqual(get_g.return_value.init_map.call_count,2)
        self.assertEqual(get_g.return_value.destruct_map.call_count,1)
        self.assertEqual(gmap.ready, True)
        self.assertEqual(gmap.mapset, "a_mapset")
        gmap.clean_up()
        self.assertEqual(get_g.return_value.destruct_map.call_count,2)

    @patch('mdig.GRASSInterface.get_g')
    def test_change_map_type(self,get_g):
        gmap = GrassMap(filename="test")
        self.assertRaises(NotImplementedError, gmap.change_map_type, "raster", "1") 

    @patch('mdig.GRASSInterface.get_g')
    def test_use_existing_map(self,get_g):
        fn = "nz_DEM_jacques"
        gmap = GrassMap(filename=fn)
        self.assertEqual(get_g.return_value.check_map.called, True)
        self.assertEqual(get_g.return_value.check_map.call_args[0][0], fn)

        # test when we can't find the map
        get_g.return_value.check_map.return_value = None
        self.assertRaises(GRASSInterface.MapNotFoundException,GrassMap,filename=fn)

        


