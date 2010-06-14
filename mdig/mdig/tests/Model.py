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
        g.in_grass_shell = False

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

from mdig.AnalysisCommand import AnalysisCommand, OutputFileNotSetException
from mdig import NotEnoughHistoryException
class AnalysisCommandTest(unittest.TestCase):

    def setUp(self):
        self.repo = ModelRepository()

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


from mdig import WebService
from mdig.bottle import app, HTTPError, HTTPResponse, run
import mdig.bottle
class WebServiceTest(unittest.TestCase):

    def setUp(self):
        mdig.repository = self.repo = ModelRepository()
        self.bottle = app()
        self.catchall=False

    def call_url(self, url, method='GET'):
        # Wrap the bottle handle method and turn result into a string instead of
        # weird array of unicode characters
        result=self.bottle.handle(url,method=method)
        if isinstance(result,Exception):
            raise result
        return str("".join(result))

    def test_404(self):
        self.assertRaises(HTTPError, self.call_url, 'flergul')

    def test_handle_index(self):
        r = self.call_url('/')

    def test_handle_models(self):
        try:
            self.call_url('/models/')
            self.assertTrue(False)
        except HTTPResponse, e:
            self.assertEqual(e.status,303)

    def test_handle_model_w_lifestages(self):
        r = self.call_url('/models/lifestage_test')

    def test_handle_bad_model(self):
        self.assertRaises(HTTPError, self.call_url, '/models/flergul')

    def test_handle_model_instance(self):
        r = self.call_url('/models/lifestage_test/instances/0')

    def test_handle_model_bad_instance(self):
        self.assertRaises(HTTPError, self.call_url, '/models/lifestage_test/instances/asdas')
        self.assertRaises(HTTPError, self.call_url, '/models/lifestage_test/instances/111')
        self.assertRaises(HTTPError, self.call_url, '/models/lifestage_test/instances/-11')

    def test_handle_model_replicate(self):
        r = self.call_url('/models/lifestage_test/instances/0/replicates/0')

    def test_handle_model_bad_replicate(self):
        self.assertRaises(HTTPError, self.call_url,
                '/models/lifestage_test/instances/0/replicates/asdasd')
        self.assertRaises(HTTPError, self.call_url,
                '/models/lifestage_test/instances/0/replicates/10101')
        self.assertRaises(HTTPError, self.call_url,
                '/models/lifestage_test/instances/0/replicates/-111')

    def test_process_tasks(self):
        import datetime
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

    def test_shutdown_webapp(self):
        WebService.shutdown_webapp()
        WebService.app = self.bottle
        WebService.shutdown_webapp()

    @patch('mdig.bottle.run')
    def test_start_webapp(self,m_run):
        WebService.start_web_service()
        WebService.shutdown_webapp()

    def test_change_to_mapset(self):
        WebService.change_to_web_mapset()

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

    def test_change_map_type(self):
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

        


