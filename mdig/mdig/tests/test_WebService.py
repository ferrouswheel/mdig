import unittest
from mock import *

import os
import datetime

import mdig
from mdig import MDiGConfig
from mdig import GRASSInterface 
from mdig.DispersalModel import DispersalModel
from mdig.ModelRepository import ModelRepository,RepositoryException

from StringIO import StringIO
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

    @patch('mdig.GRASSInterface.get_g')
    @patch('mdig.bottle.run')
    def test_start_webapp(self,m_run,m_g):
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

    def test_add_to_map_pack_lfu(self):
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
        print WebService.map_pack_lfu
        self.assertTrue(WebService.map_pack_lfu[1][1]>old_date)

    def test_run_model(self):
        WebService.mdig_worker_process = Mock()

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

