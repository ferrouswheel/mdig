#!/usr/bin/env python2.4
#
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
#
""" 
Event module. Part of MDiG - Modular Dispersal in GIS
"""

import logging
import string
import pdb

import GRASSInterface

class Event:
    """
    The Event class represents the use of a singular module or command
    within the MDiG simulation. It is used for running events in the lifestage
    loop, calculating treatment areas, and applying treatments as part of
    management strategies.
    """

    def __init__(self, node):
        self.log = logging.getLogger("mdig.event")
        self.xml_node = node

    def get_command(self):
        """ Get the module/command name """

        if "name" in self.xml_node.attrib.keys():
            return self.xml_node.attrib["name"]
        else:
            self.log.error('Event has no "name" attribute')

    def uses_random_seed(self):
        """ Check if the module has a parameter that uses a random seed """
        if len(self.xml_node.find("seed")) > 0:
            return True
        else:
            return False

    def get_params(self, is_pop, start_node):
        """
        Get the parameters as a dictionary. This function is recursively called
        when <if(Not)PopulationBased> nodes are encountered.
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
                    a=("FLAG",None)
                    params[node.attrib["name"]]=a
                elif node.tag == "param":
                    for v in node:
                        if v.tag == "value":
                            a=("VALUE",string.strip(v.text))
                        elif v.tag == "variable":
                            a=("VAR",v.attrib["id"])
                        elif v.tag == "seed":
                            a=("SEED",None)
                        elif v.tag == "inputMap":
                            a=("INPUT",None)
                        elif v.tag == "outputMap":
                            a=("OUTPUT",None)
                    params[node.attrib["name"]]=a
        return params

    def run(self,in_name,out_name,rep,is_pop):
        """
        Run the event using in_name as the input map and out_name as the output
        map. 
        """
        p=self.get_params(is_pop,None)
        
        # Default parameter names for input and output maps if none explicitly defined:
        if ("INPUT",None) not in p.values():
            p["input"]=in_name
        if ("OUTPUT",None) not in p.values():
            p["output"]=out_name

        s_name = rep.instance.strategy
        s = rep.instance.experiment.get_management_strategy(s_name)
        for p_name,value in p.items():
            if value[0] == "VAR":
                instance_value = rep.instance.get_var(value[1])
                treatments = []
                if s is not None:
                    treatments = s.get_treatments_for_param(value[1])
                    self.log.info("treatments is " + repr(treatments))
                    # TODO support blending of multiple treatments on param
                    # (move below operations from treatment to strategy)
                    if len(treatments) > 0:
                        assert ( len(treatments) == 1 )
                        instance_map = treatments[0].get_variable_map(value[1],
                                instance_value, rep)
                        if instance_map is None:
                            instance_value = treatments[0].get_altered_variable_value(value[1],instance_value)
                        assert( instance_value is not None )
                if instance_value is not None:
                    p[p_name]=instance_value
                else:
                    self.log.error("Variable ID doesn't exist in variable list")
            elif value[0] == "SEED":
                p[p_name]=rep.random.randint(-2.14748e+09,2.14748e+09)
            elif value[0] == "INPUT":
                p[p_name]=in_name
            elif value[0] == "OUTPUT":
                p[p_name]=out_name
            elif value[0] == "VALUE":
                p[p_name]=value[1]
            elif value[0] == "FLAG":
                p[p_name]="FLAG"
        
        cmd=self.create_cmd_string(p)
        
        GRASSInterface.getG().removeMap(out_name)
        GRASSInterface.getG().runCommand(cmd)
        #self.log.debug(cmd)

    def create_cmd_string(self,params):
        """
        Create an actual command line string to run in GRASS
        """
        cmd=self.get_command() + ' '
        for p_name,value  in params.items():
            if value == "FLAG":
                cmd = cmd + "-" + p_name + " "
            else:
                cmd = cmd + p_name + "=" + str(value) + " "
        return cmd
