import unittest
from mock import *

import mdig
import mdig.GRASSInterface
from mdig.ManagementStrategy import ManagementStrategy, Treatment, TreatmentArea
from StringIO import StringIO

class ManagementStrategyTest(unittest.TestCase):
    
    @patch('mdig.GRASSInterface.get_g')
    def test_create_strategy(self,get_g):
        from lxml import etree
        xml = """
        <strategy name="decrease" region="a">
            <description>Test to check variable management works</description>
            <treatments>
            <t>
              <affectVariable var="dist">
                <decrease>1</decrease>
              </affectVariable>
            </t>
            </treatments>
        </strategy>
        """
        tree = etree.parse(StringIO(xml))
        strategy_node = tree.getroot()
        mock_model= Mock()
        s = ManagementStrategy(strategy_node,mock_model)
        self.assertEqual(s.grass_i, get_g.return_value)

        a= Mock()
        s.set_instance(a)
        self.assertEqual(s.instance, a)
        self.assertRaises(NotImplementedError,s.init_strategy, mock_model)
        self.assertRaises(NotImplementedError,ManagementStrategy,None,mock_model)

        mock_model.get_regions.return_value = ['r1','r2']
        s.set_region('r2')
        self.assertEqual(s.node.attrib['region'],'r2')

        s.set_description("test description")
        self.assertEqual(s.get_description(),"test description")
        s.set_name("meatball")
        self.assertEqual(s.get_name(),"meatball")

        mock_model.get_period.return_value = (0,10)
        self.assertEqual(len(s.get_treatments_for_param("dist",0)),1)
        self.assertEqual(len(s.get_treatments_for_param("meatball",0)),0)

        t = s.get_treatments()[0]
        self.assertEqual(t.get_treatment_area_map(None), None)
        self.assertEqual(t.get_ls(), None)

    @patch('mdig.GRASSInterface.get_g')
    def test_s_with_delay(self,get_g):
        from lxml import etree
        xml = """
        <strategy name="decrease" region="a">
            <delay>10</delay>
            <description>Test to check variable management works</description>
            <treatments>
            <t>
              <affectVariable var="dist">
                <decrease>1</decrease>
              </affectVariable>
            </t>
            </treatments>
        </strategy>
        """
        tree = etree.parse(StringIO(xml))
        strategy_node = tree.getroot()
        mock_model= Mock()
        s = ManagementStrategy(strategy_node,mock_model)
        self.assertEqual(s.get_delay(), 10)
        s.set_delay(200)
        self.assertEqual(s.get_delay(), 200)
        desc_node = s.node.xpath("delay")
        desc_node[0].text = "string_test"
        self.assertRaises(ValueError,s.get_delay)

        # test 0 delay with no element
        s.node.remove(desc_node[0])
        self.assertEqual(s.get_delay(), 0)

        # test adding a delay node
        s.set_delay(2)
        self.assertEqual(s.get_delay(), 2)

        mock_model.get_period.return_value = (0,10)
        self.assertEqual(len(s.get_treatments_for_param("dist",0)),0)
        self.assertEqual(len(s.get_treatments_for_param("dist",3)),1)

    @patch('mdig.GRASSInterface.get_g')
    def test_s_with_ls(self,get_g):
        from lxml import etree
        xml = """
    <strategy name="area_or" region="a">
      <description>Test to check map area combined with OR works.</description>
      <treatments>
        <t>
          <area ls="all" combine="or">
            <mapcalc>if(!isnull(START_MAP),1,null())</mapcalc>
            <mapcalc>if(x()&gt;3,1,null())</mapcalc>
          </area>
          <event ls="all" name="r.mdig.survival">
            <param name="survival">
              <value>80</value>
            </param>
            <!-- Survival needs seed parameter, otherwise it inits from time
                     and just removes the same cells -->
            <param name="seed">
              <seed/>
            </param>
          </event>
        </t>
      </treatments>
    </strategy>
    """
        tree = etree.parse(StringIO(xml))
        strategy_node = tree.getroot()
        mock_model= Mock()
        s = ManagementStrategy(strategy_node,mock_model)

        mock_model.get_period.return_value = (0,10)
        self.assertEqual(len(s.get_treatments_for_ls("all",0)),1)
        self.assertEqual(len(s.get_treatments_for_ls("kibble",0)),0)
        s.set_delay(2)
        self.assertEqual(len(s.get_treatments_for_ls("all",0)),0)
        self.assertEqual(len(s.get_treatments_for_ls("all",3)),1)

    @patch('mdig.GRASSInterface.get_g')
    def test_treatment_no_node(self,get_g):
        self.assertRaises(NotImplementedError,Treatment,None,None,None)

        s = Mock()
        s.get_name.return_value = 'test'
        def test_del():
            t = Treatment(s,Mock(),0)
        test_del()
        self.assertEqual(get_g.return_value.remove_map.call_count, 2)

