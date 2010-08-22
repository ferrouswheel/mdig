import unittest
from mock import *

import os
import datetime

import mdig
from mdig import config
from mdig import grass 
from mdig.model import DispersalModel
from mdig.modelrepository import ModelRepository,RepositoryException

from StringIO import StringIO
from mdig import webui

class ResultsMonitorTest(unittest.TestCase):

    def run_counter(self,timeout=None):
        self.rm.running = False
        return self.result

    def test_run(self):
        self.rm=webui.ResultMonitor(Mock())
        self.rm.running = True
        self.result = {'action':'sss'}
        self.rm.result_q.get.side_effect = self.run_counter
        self.rm.run()

class MDiGWorkTest(unittest.TestCase):

    @patch('mdig.webui.MDiGWorker')
    @patch('mdig.grass.get_g')
    def test_worker_start(self,m_g,m_worker):
        m_g.return_value.grass_vars = {}
        webui.mdig_worker_start('a','b')
        self.assertEqual(m_g.return_value.grass_vars['MAPSET'],"PERMANENT")
        self.assertEqual(m_worker.call_args[0],('a','b'))

from mdig.bottle import app, HTTPError, HTTPResponse, run
import mdig.bottle
import tools
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

    def test_handle_alternate_location(self):
        r = self.urlopen('/models/other_loc_model')
        r = self.urlopen('/models/other_loc_model/instances/0')

    def test_process_tasks(self):
        now = datetime.datetime.now() 
        webui.models_in_queue = {
            "lifestage_test": {
                "RUN" : { 
                    'last_update': now - datetime.timedelta(seconds=100)
                    },
                "OCCUPANCY_GIF": {
                    'last_update': now - datetime.timedelta(seconds=500)
                    }
                }
            }
        before_complete = webui.last_notice
        updates=webui.process_tasks()
        self.assertEqual(webui.last_notice, before_complete)
        before_complete = webui.last_notice
        webui.models_in_queue['lifestage_test']['RUN']['complete']= \
                datetime.datetime.now()
        updates=webui.process_tasks()
        self.assertTrue(webui.last_notice > before_complete)

        # test to ensure old completed actions are removed:
        webui.models_in_queue['lifestage_test']['RUN']['last_update']= \
                datetime.datetime.now() - datetime.timedelta(days=8)
        updates=webui.process_tasks()
        self.assertTrue('RUN' not in \
                webui.models_in_queue['lifestage_test']) 

    def test_process_tasks_errors(self):
        # test errors
        now = datetime.datetime.now() 
        webui.models_in_queue = {
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
        before_complete = webui.last_notice
        updates=webui.process_tasks()
        self.assertEqual(updates[0][0][0], 'lifestage_test')
        self.assertEqual(updates[0][0][1], 'OCCUPANCY_GIF')
        self.assertEqual(updates[0][1][1], 'RUN')
        before_complete = webui.last_notice

        # ensure error message disappears
        updates=webui.process_tasks()
        self.assertEqual(webui.last_notice, before_complete)
        self.assertEqual(len(updates[0]), 1)

    def test_shutdown_webapp(self):
        webui.shutdown_webapp()
        webui.app = self.app
        webui.shutdown_webapp()

    @patch('mdig.grass.get_g')
    @patch('mdig.bottle.run')
    def test_start_webapp(self,m_run,m_g):
        webui.start_web_service()
        webui.shutdown_webapp()

    def test_change_to_mapset(self):
        webui.change_to_web_mapset()

    @patch('os.remove')
    @patch('mdig.webui.get_map_pack_usage')
    def test_purge_oldest_map_packs(self,m_usage,m_rm):
        m_usage.return_value = 0.0
        # check that empty lfu does nothing
        webui.map_pack_lfu = []
        webui.purge_oldest_map_packs()
        self.assertEqual(len(webui.map_pack_lfu),0)
        self.assertEqual(m_rm.call_count,0)

        m_usage.return_value = 2000.0
        webui.map_pack_lfu = [('test1',None),
                ('test2',datetime.datetime.now())]
        webui.purge_oldest_map_packs()
        self.assertEqual(m_rm.call_count,1)
        self.assertEqual(len(webui.map_pack_lfu),1)

        # Test when removal throws a no such file error with date
        webui.map_pack_lfu = [('test2',datetime.datetime.now()),('test1',None)]
        m_rm.side_effect = OSError("No such file")
        webui.purge_oldest_map_packs()
        self.assertEqual(len(webui.map_pack_lfu),1)

        # Test when removal throws a no such file error on a None date
        webui.map_pack_lfu = [('test1',None),
                ('test2',datetime.datetime.now())]
        m_rm.side_effect = OSError("No such file")
        webui.purge_oldest_map_packs()
        self.assertEqual(len(webui.map_pack_lfu),1)

        # Test what happens when the OSError isn't to do with a invalid file
        webui.map_pack_lfu = [('test2',datetime.datetime.now()),('test1',None)]
        m_rm.side_effect = OSError("Another OS error")
        self.assertRaises(OSError,webui.purge_oldest_map_packs)

    @patch('os.path.getsize')
    def test_get_map_pack_usage(self,m_sz):
        five_megs = 1024*1024*5
        m_sz.return_value = five_megs
        webui.map_pack_lfu = [('test1',None),
                ('test2',datetime.datetime.now())]
        usage = webui.get_map_pack_usage()
        self.assertEqual(usage, five_megs * 2 / (1024*1024))

        m_sz.side_effect = OSError()
        webui.map_pack_lfu = [('test1',None),
                ('test2',datetime.datetime.now())]
        usage = webui.get_map_pack_usage()
        self.assertEqual(usage, 0.0)
        self.assertEqual(len(webui.map_pack_lfu),1)

    def test_add_to_map_pack_lfu(self):
        webui.map_pack_lfu = []
        # test empty
        webui.add_to_map_pack_lfu('test1')
        self.assertEqual(webui.map_pack_lfu[0][0],'test1')

        # test not in lfu
        webui.add_to_map_pack_lfu('test2',nodate=True)
        self.assertEqual(webui.map_pack_lfu[1][0],'test2')
        self.assertEqual(webui.map_pack_lfu[1][1],None)

        # test replace none with date
        webui.add_to_map_pack_lfu('test2')
        self.assertNotEqual(webui.map_pack_lfu[1][1],None)
        print webui.map_pack_lfu

        # test replace with none 
        webui.add_to_map_pack_lfu('test1',nodate=True)
        print webui.map_pack_lfu
        self.assertEqual(webui.map_pack_lfu[1][1],None)

        # test update date
        old_date = webui.map_pack_lfu[0][1]
        webui.add_to_map_pack_lfu('test2')
        print webui.map_pack_lfu
        self.assertTrue(webui.map_pack_lfu[1][1]>old_date)

    def test_run_model(self):
        webui.mdig_worker_process = Mock()

        webui.models_in_queue = {}
        r = self.urlopen('/models/lifestage_test/run',method='POST',post='rerun=true')
        self.assertTrue('RUN' in webui.models_in_queue['lifestage_test']) 

        webui.models_in_queue = {'lifestage_test':
                {'OCCUPANCY_GIF': {
                    'last_update': datetime.datetime(2010, 6, 15, 16, 24, 36, 171171)
                    }
                }
            }
        r = self.urlopen('/models/lifestage_test/run',method='POST',post='rerun=true')
        self.assertTrue('RUN' in webui.models_in_queue['lifestage_test']) 
        r = self.urlopen('/models/lifestage_test/run',method='POST',post='rerun=true')
        self.assertTrue('RUN' in webui.models_in_queue['lifestage_test']) 

    def test_run_instance(self):
        webui.mdig_worker_process = Mock()
        webui.models_in_queue = {}
        r = self.urlopen('/models/lifestage_test/run',method='POST',post='instance=0&rerun=true')
        self.assertTrue('RUN' in webui.models_in_queue['lifestage_test']) 

    def test_add_model_to_repo(self):
        import tempfile
        fn = self.repo.get_models()['variables']
        dm = DispersalModel(fn)
        temp_fn = tempfile.mktemp(suffix='.xml')
        dm.set_name('variable_test')
        dm.set_location('grass_location')
        dm.save_model(temp_fn)
        f = open(temp_fn,'r')
        data = f.read()
        f.close()
        webui.add_model_to_repo(data)
        os.remove(temp_fn)
        self.assertTrue('variable_test' in self.repo.get_models())
        self.repo.remove_model('variable_test',force=True)

    def test_add_and_delete_model(self):
        import tempfile
        fn = self.repo.get_models()['variables']
        dm = DispersalModel(fn)
        temp_fn = tempfile.mktemp(suffix='.xml')
        dm.set_name('variable_test')
        dm.set_location('grass_location')
        dm.save_model(temp_fn)
        f = open(temp_fn,'r')
        data = f.read()
        f.close()
        webui.add_model_to_repo(data)
        os.remove(temp_fn)
        self.assertTrue('variable_test' in self.repo.get_models())
        r = self.urlopen('/models/variable_test/del',method='POST')
        self.assertEqual(r['code'],303)
        self.assertTrue('variable_test' not in self.repo.get_models())

    def test_delete_unknown_model(self):
        count = len(self.repo.get_models())
        r = self.urlopen('/models/fibllle/del',method='POST')
        self.assertEqual(r['code'],404)
        self.assertEqual(count,len(self.repo.get_models()))

    def test_submit_model(self):
        import tempfile
        fn = self.repo.get_models()['variables']
        dm = DispersalModel(fn)
        temp_fn = tempfile.mktemp(suffix='.xml')
        dm.set_name('variable_test')
        dm.set_location('grass_location')
        dm.save_model(temp_fn)
        f= open(temp_fn)
        import os.path
        self.postmultipart('/models/',fields={},files=[('new_model',temp_fn,f.read())])
        f.close()
        os.remove(temp_fn)
        self.assertTrue('variable_test' in self.repo.get_models())
        r = self.urlopen('/models/variable_test/del',method='POST')

    def test_submit_model_already_exists(self):
        import tempfile
        fn = self.repo.get_models()['variables']
        dm = DispersalModel(fn)
        temp_fn = tempfile.mktemp(suffix='.xml')
        dm.set_location('grass_location')
        dm.save_model(temp_fn)
        f= open(temp_fn)
        import os.path
        count=len(self.repo.get_models())
        self.postmultipart('/models/',fields={},files=[('new_model',temp_fn,f.read())])
        f.close()
        os.remove(temp_fn)
        self.assertEqual(count,len(self.repo.get_models()))
        self.assertTrue('variables' in self.repo.get_models())

    def test_submit_model_missing_files(self):
        import tempfile
        fn = self.repo.get_models()['lifestage_test']
        dm = DispersalModel(fn)
        temp_fn = tempfile.mktemp(suffix='.xml')
        dm.set_name('lifestage_test2')
        dm.set_location('grass_location')
        dm.save_model(temp_fn)
        f= open(temp_fn)
        import os.path
        r = self.postmultipart('/models/',fields={},files=[('new_model',temp_fn,f.read())])
        f.close()
        os.remove(temp_fn)
        self.assertTrue('error' in r['body'])
        self.assertTrue('lifestage_test2' not in self.repo.get_models())

    def test_submit_model_bad_xml(self):
        import tempfile
        fn = self.repo.get_models()['lifestage_test']
        dm = DispersalModel(fn)
        temp_fn = tempfile.mktemp(suffix='.xml')
        dm.set_name('lifestage_test2')
        dm.set_location('grass_location')
        dm.save_model(temp_fn)
        f= open(temp_fn)
        import os.path
        data=f.read()
        data += "</berg>"
        r = self.postmultipart('/models/',fields={},files=[('new_model',temp_fn,data)])
        f.close()
        os.remove(temp_fn)
        self.assertTrue('error' in r['body'])
        self.assertTrue('lifestage_test2' not in self.repo.get_models())






