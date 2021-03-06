#  Copyright (C) 2006,2008 Joel Pitt, Fruition Technology
#
#  This file is part of Modular Dispersal In GIS.
#
#  Modular Dispersal In GIS is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your
#  option) any later version.
#
#  Modular Dispersal In GIS is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
#  Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with Modular Dispersal In GIS.  If not, see <http://www.gnu.org/licenses/>.

import logging
import string

import grass
from mdig.tempresource import trm

class Event(object):
    """
    The Event class represents the use of a singular module or command within
    the MDiG simulation. It is used for running events in the lifestage loop,
    calculating treatment areas, and applying treatments as part of management
    strategies.
    """

    def __init__(self, node):
        self.log = logging.getLogger("mdig.event")
        self.xml_node = node
        self.fixed_input = None

    def get_command(self):
        """ Get the module/command name """

        if "name" in self.xml_node.attrib.keys():
            return self.xml_node.attrib["name"]
        else:
            self.log.error('Event has no "name" attribute')

    def _get_attrib(self,x,default=""):
        i = default
        if x in self.xml_node.attrib:
            i = self.xml_node.attrib[x]
        return i

    def get_input_name(self):
        input_name = self._get_attrib("input",default="input")
        return input_name if input_name else None

    def get_output_name(self):
        output = self._get_attrib("output",default="output")
        return output if output else None

    def uses_random_seed(self):
        """ Check if the module has a parameter that uses a random seed """
        if len(self.xml_node.find("seed")) > 0:
            return True
        else:
            return False

    def get_params(self, is_pop=False, start_node=None):
        """
        Get the parameters as a dictionary.
        
        This function is recursively called when <if(Not)PopulationBased> nodes
        are encountered.
        """
        if start_node is None:
            nodes = self.xml_node.getchildren()
        else:
            nodes = start_node.getchildren()
            
        params={}
        for node in nodes:
            # Go through each <param> node
            if node.tag == "ifPopulationBased" and is_pop:
                params2 = self.get_params(is_pop,node)
                params.update(params2)
            elif node.tag == "ifNotPopulationBased" and not is_pop:
                params2 = self.get_params(is_pop,node)
                params.update(params2)
            else:
                if node.tag == "flag":
                    a = ("FLAG", None)
                    params[node.attrib["name"]] = a
                elif node.tag == "param":
                    for v in node:
                        if v.tag == "value":
                            a = ("VALUE", string.strip(v.text))
                        if v.tag == "map":
                            a = ("MAP", string.strip(v.text))
                        elif v.tag == "variable":
                            a = ("VAR", v.attrib["id"])
                        elif v.tag == "seed":
                            a = ("SEED", None)
                        elif v.tag == "reportFile":
                            a = ("REPORT_FILE", None)
                    params[node.attrib["name"]]=a
                elif node.tag == "input":
                    # Default input that doesn't change, only for Treatments
                    self.fixed_input = node.text.strip()
        return params

    def run(self, in_name, out_name, rep, is_pop):
        """
        Run the event using in_name as the input map and out_name as the output map. 
        """
        template_p = self.get_params(is_pop,None)
        p = {}
        
        # If this event has a fixed input specified
        if self.fixed_input is not None:
            in_name = self.fixed_input

        # Parameter names for input and output maps
        in_param = self.get_input_name()
        if in_param is not None:
            template_p[in_param] = ("IN", in_name)
        out_param = self.get_output_name()
        if out_param is not None:
            template_p[out_param] = ("OUT", out_name)

        # Some commands report some interesting information to aggregate,
        # like r.mdig.survival's AREA_EVALUATED
        report_file = None

        s_name = rep.instance.strategy
        s = rep.instance.experiment.get_management_strategy(s_name)
        # TODO strategies should be pre initialised with instances
        if s is not None:
            s.set_instance(rep.instance)
        for p_name, value in template_p.items():
            p_type, p_value = value
            # print 'name is', p_name,
            # print 'value is', value
            if p_type == "VAR":
                instance_value = rep.instance.get_var(p_value)
                instance_map = None
                treatments = []
                if s:
                    treatments = s.get_treatments_for_param(p_value,rep.current_t)
                    if treatments:
                        self.log.debug("treatments for variable %s are: %s" % (p_value, repr(treatments)))
                        # TODO support blending of multiple treatments on param
                        # (move below operations from treatment to strategy)
                        assert len(treatments) == 1, "MDiG does not currently support multiple treatments to a parameter"
                        instance_map = treatments[0].get_variable_map(p_value, instance_value, rep)
                        if instance_map is None:
                            instance_value = treatments[0].get_altered_variable_value(p_value,instance_value)
                            assert instance_value is not None
                if instance_value:
                    p[p_name]=instance_value
                    self.log.debug("Variable %s has value %s for this instance" %
                            (p_name, instance_value))
                elif instance_map:
                    p[p_name]=instance_map
                    self.log.debug("Variable %s is map %s for this instance" %
                            (p_name, instance_map))
                else:
                    self.log.debug("Variable %s has None value for this instance" %
                            p_name)
            elif p_type == "SEED":
                p[p_name] = rep.random.randint(-2.14748e+09,2.14748e+09)
            elif p_type == "REPORT_FILE":
                report_file = trm.temp_filename(prefix='mdig_event_report')
                p[p_name] = report_file
            elif p_type in ["VALUE", "MAP", "IN", "OUT"]:
                p[p_name] = p_value
            elif p_type == "FLAG":
                p[p_name] = "FLAG"
            else: 
                raise Exception("Unknown parameter type %s" % p_type)
        
        cmd=self.create_cmd_string(p)
        
        grass.get_g().remove_map(out_name)
        grass.get_g().run_command(cmd)

        metrics = {}
        if report_file:
            metrics = self.read_report_file(report_file)
        return metrics

    def read_report_file(self, filename):
        results = {}
        with open(filename, 'r') as f:
            for l in f.readlines():
                ll = l.strip().split('=')
                assert len(ll) == 2, "Badly formatted report file line: %s" % l
                results[ll[0]] = ll[1]
        return results

    def get_map_resources(self,model):
        var_maps = model.get_variable_maps()
        params = self.get_params()
        maps = []
        for p_key in params:
            p = params[p_key]
            if p[0] == "MAP":
                maps.append(p[1])
            elif p[0] == "VAR":
                maps.extend(var_maps[p[1]])
        maps_w_mapset = grass.get_g().find_mapsets(maps)
        return maps_w_mapset

    def create_cmd_string(self,params):
        """
        Create an actual command line string to run in GRASS
        """
        cmd = self.get_command()
        for p_name, value in params.items():
            if value == "FLAG":
                cmd += (" -" + p_name)
            else:
                cmd += (" " + p_name + "=" + str(value))
        return cmd + " "
