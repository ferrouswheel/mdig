import unittest
from mock import *

import mdig
from mdig.DispersalModel import DispersalModel
from mdig.ModelRepository import ModelRepository,RepositoryException

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
