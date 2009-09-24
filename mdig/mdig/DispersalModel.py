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
""" DispersalModel class for MDiG - Modular Dispersal in GIS

Test usage: python DispersalModel.py [model=model.xml] [schema=model.xsd] to run
unit test on model.xml and validating with the schema model.xsd

By default example.xml will be loaded and validated with mdig.xsd

Copyright 2006-2007, Joel Pitt, Lincoln University
Copyright 2008-2009, Dr. Joel Pitt, Fruition Technology
"""

import lxml.etree
import random
import getopt
import sys
import pdb
import logging
import string
import os
import shutil
import re

from datetime import datetime
from UserDict import UserDict

import OutputFormats
import GRASSInterface
import MDiGConfig

from Region import Region
from DispersalInstance import DispersalInstance
from Event import Event
from Lifestage import Lifestage
from Analysis import Analysis
from Replicate import Replicate
from GrassMap import GrassMap
from LifestageTransition import LifestageTransition
from ManagementStrategy import ManagementStrategy

_debug=0

class DispersalModel(object):
    """ DispersalModel keeps track of general model data and allows high level
        control of running simulations and analysis.
    """

    def __init__(self, model_file, the_action = None, setup=True):
        self.action = the_action
        
        self.log = logging.getLogger("mdig.model")
        
        self.model_filename = model_file
        self.backup_filename = None
        self.regions={}
        self.lifestages={}
        self.instances = None
        self.strategies = None
        self.activeInstances = []
        self.lifestage_transition = None
        
        schema_file = sys.path[0]+"/mdig/mdig.xsd"
        self.load_xml(model_file)
        self.validate_xml(schema_file)
        
        self.listeners = []
        outputListeners = self.get_output_listeners()
        for l in outputListeners:
            self.add_listener(l)
    
        self.grass_i=GRASSInterface.getG()
        self.random = None
        
        self.active=False
        self.start_time = None
        self.end_time = None
        
        self.start = {}
        
        if self.action is not None:
            try:
                if self.action.check_model:
                    self.check_model()
            except CheckModelException, e:
                print e
                
        self.base_dir = None
        if self.action is not None:
            self.set_base_dir(self.action.output_dir)
        elif setup:
            self.set_base_dir() 

        if setup:
            self.init_mapset()

    def set_base_dir(self, dir=None):
        # Set up base directory for output
        existing_base_dir = self.get_base_dir()
        if dir is not None:
            self.base_dir = dir
        else:
            self.base_dir = os.path.dirname(self.model_file)
        if existing_base_dir not in [None, ""] and \
            self.base_dir != existing_base_dir:
            self.log.warn("Current base dir is different to that already " +
                    "set... some analysis results may be unavailable. " + 
                    "This could break things.")
            raw_input("Press enter to continue, or CTRL-C to abort.")
        # Initialise paths
        self.init_paths()

    def init_paths(self):
        c = MDiGConfig.getConfig()
        if self.base_dir is None:
            base_d = './'
        else:
            base_d = self.base_dir
        filename = os.path.join(base_d, c.analysis_dir)
        MDiGConfig.makepath(filename)
        filename = os.path.join(base_d, c.maps_dir)
        MDiGConfig.makepath(filename)
        filename = os.path.join(base_d, c.output_dir)
        MDiGConfig.makepath(filename)

    def _load(self, model_file):
        """load XML input source, return parsed XML document
        can be:
        - a URL of a remote XML file ("http://diveintopython.org/kant.xml")
        - a filename of a local XML file ("~/diveintopython/common/py/kant.xml")
        - standard input ("-")
        - the actual XML document, as a string
        """
        self.log.debug("Opening %s", model_file)
        sock = open_anything(model_file)
        
        try:
            self.log.debug("Parsing %s", model_file)
            xmltree = lxml.etree.parse(sock)
        except lxml.etree.XMLSyntaxError, e:
            self.log.error("Error parsing %s", model_file)
            if hasattr(e,"error_log"):
                log = e.error_log.filter_levels(lxml.etree.ErrorLevels.FATAL)
                print log
            sys.exit(3)
        
        sock.close()
        self.model_file=model_file
        return xmltree

    def load_xml(self, model_file):
        """load mdig model file"""
        self.xml_model = self._load(model_file) 
        
    def validate_xml(self, schema_file):
        self.log.debug("Loading schema %s", schema_file)
        try:
            self.schema_doc = lxml.etree.parse(schema_file)
            self.xml_schema = lxml.etree.XMLSchema(self.schema_doc)
        except lxml.etree.XMLSyntaxError, e:
            log = e.error_log
            print log
        except lxml.etree.XMLSchemaParseError, e:
            log = e.error_log
            print log
            
        if not self.xml_schema.validate(self.xml_model):
            self.log.error("%s not valid according to Schema", self.model_file)
            
            # early versions of lxml didn't support verbose error information
            if "error_log" in dir(self.xml_schema):
                log = self.xml_schema.error_log
                errors = log.filter_from_errors()
                print errors
            raise ValidationError()
        
        self.schema_file=schema_file
        self.log.debug("%s is valid", self.model_file)
            
    def _get_instances_by_region(self):
        instances = self.get_instances()
        r_inst = {}
        
        for i in instances:
            if i.r_id not in r_inst.keys():
                r_inst[i.r_id]=[]
            r_inst[i.r_id].append(i)
            
        return r_inst
    
    def _getInstanceWithSmallestRepsRemaining(self,instances):
        # find instance with smallest number of reps left
        
        # max_reps because instances count completed reps rather than counting
        # down.
        max_reps = 0
        min_instance = None
        
        for i in instances:
            completed = len([x for x in i.replicates if x.complete])
            if not i.is_complete() and (completed > max_reps or min_instance == None):
                min_instance = i
                max_reps = completed
            
        return min_instance
    
    def resetInstances(self):
        instances = self.get_instances()
        for i in instances:
            i.reset()
    
    def add_listener(self,l):
        self.listeners.append(l)
        
    def remove_listener(self,l):
        self.listeners.remove(l)
    
    def run(self):
        self.active = True
        self.start_time = datetime.now()
        self.log.info("Starting simulations at " + self.start_time.isoformat())
        
        r_instances = self._get_instances_by_region()
        
        # incomplete's keys are regions
        for r_id,instances in r_instances.items():
            
            self.log.debug("Running instances in region %s", r_id)
            
            instance = self._getInstanceWithSmallestRepsRemaining(instances)
            
            # while there are still something in the queue to be simulated
            while instance is not None:
                
                instance.run()
                
                instance = self._getInstanceWithSmallestRepsRemaining(instances)
                
        self.active = False
        self.end_time = datetime.now()
        
    def is_complete(self):
        for i in self.get_instances():
            if not i.is_complete():
                return False
        return True
    
    def null_bitmask(self, generate=True):
        instances = self.get_instances()
        for i in instances:
            if generate:
                log_str = "Generating"
            else:
                log_str = "Deleting"
            log_str=log_str+" bitmasks for instance %d of %d." % (instances.index(i)+1,len(instances))
            self.log.info(log_str)
            i.null_bitmask(generate)
    
    def pre_run(self):
        pass
    
    def get_instances(self):
        if self.instances is None:
            self.instances = []
            permutations = self.get_instance_permutations()
            
            # Turn each returned variable combination into an actual
            # DispersalInstance object instance
            for r_id, p in permutations.items():
                num_perms = len(p["var"])
                # If no variables in experiment:
                if num_perms == 0:
                    node = self.get_completed_node(r_id,None,None)
                    self.instances.append( \
                           DispersalInstance(node,self,r_id,None,None))
                # If variables are in experiment:
                # TODO this needs to be updated to handle management strategy as
                # the first "variable"
                else:
                    for i in range(0, num_perms):
                        node = self.get_completed_node(r_id,p["var_keys"],p["var"][i])
                        self.instances.append( \
                           DispersalInstance(node,self,r_id,p["var_keys"],p["var"][i]))
            
            for instance in self.instances:
                #instance.set_replicates(self.getCompletedReplicates(instance))
                instance.listeners.extend(self.listeners)
            
        return self.instances
                
    
    def get_incomplete_instances(self):
        return [i for i in self.get_instances() if not i.is_complete()]
    
                
    def check_model(self):
        self.log.debug("Checking model maps exist")
        
        # - can check maps just by attempting to get the map
        # - functions create GrassMap's automatically and
        # checks the map exists
        
        empty_region = False
        #check background map
        for r_id, region in self.get_regions().items():
            region.getBackgroundMap()
        #check initial map for each lifestage exists
            total_initial_maps = 0
            for ls_key in self.get_lifestage_ids():
                ls = self.get_lifestage(ls_key)
                total_initial_maps += len(ls.initial_maps)
            if total_initial_maps == 0:
                self.error("Region %s has no initial maps defined" % r_id)
                empty_region = True
            
        if empty_region:
            exit(mdig.mdig_exit_codes["no_initial_maps"])
                
        #check phenology maps exist
        
        #Check that the event commands exist or are supported.
        
        
        #self.grass_i.checkMap(self.model.getBackgroundMap())
    
    def get_user(self):
        nodes = self.xml_model.xpath('user/email')
        if len(nodes) == 1:
            return nodes[0].text.strip()
        
    def set_user(self,email):
        nodes = self.xml_model.xpath('user/email')
        if len(nodes) == 1:
            nodes[0].text = email
        
    def get_name(self):
        nodes = self.xml_model.xpath('/model/name')
        return nodes[0].text.strip()
        
    def set_name(self,name):
        nodes = self.xml_model.xpath('/model/name')
        nodes[0].text = name
        
    def get_popmod_file(self):
        nodes = self.xml_model.xpath('/model/lifestages/transition/popMod')
        if len(nodes) == 1:
            return nodes[0].attrib['file']
        else:
            return None

    def set_popmod_file(self,filename):
        nodes = self.xml_model.xpath('/model/lifestages/transition/popMod')
        if len(nodes) == 1:
            nodes[0].attrib['file'] = filename
            return filename
        else:
            return None
        
    def get_initial_random_seed(self):
        nodes = self.xml_model.xpath('/model/random/initialSeed')
        if len(nodes) == 1:
            return int(nodes[0].text.strip())
        else:
            return None
                
    #def setRandom(self, seed, state):
    #   nodes = self.xml_model.xpath('/model/random/initialSeed')
    #   nodes[0].text = repr(seed)
    #   nodes = self.xml_model.xpath('model/random/lastState')
    #   nodes[0].text = repr(state)

    def init_random(self,seed,offset):
        i_seed = self.get_initial_random_seed()
        my_random = random.Random()
        
        my_random.seed(i_seed)
        
        if i_seed is None:
            # ignore offset if seed isn't specified
            self.log.warning("No initial seed specified - using OS generated" +
                    " seed. You will not be able to rerun this exact " +
                    "simulation in future")
        else:
            my_random.seed(i_seed)
            while offset > 0:
                my_random.randint(-2.14748e+09,2.14748e+09)
                offset -= 1
            
        return my_random
        
    def next_random_value(self):
        if self.random is None:
            offset = self.get_random_offset()
            seed = self.get_initial_random_seed()
            self.random = self.init_random(seed,offset)
            
        value=self.random.randint(-2.14748e+09,2.14748e+09)
        self.inc_random_offset()
        return value
    
    def inc_random_offset(self):
        nodes = self.xml_model.xpath('/model/random/offset')
        if len(nodes) < 1:
            random_node = self.xml_model.xpath('/model/random')
            #pdb.set_trace()
            ls_node = lxml.etree.SubElement(random_node[0],'offset')
            ls_node.text = "0"
        else:
            ls_node = nodes[0]
            
        value = int(ls_node.text)
        value += 1
        ls_node.text = repr(value)
    
    def get_random_offset(self):
        nodes = self.xml_model.xpath('/model/random/offset')
        if len(nodes) == 1:
            return int(nodes[0].text)
        else:
            return None
        #[int(child.attrib["a"]),int(child.attrib["b"]),int(child.attrib["c"])]
        
    def get_version(self):
        nodes = self.xml_model.xpath('model')
        if len(nodes) > 0 and "version" in nodes[0].attrib.keys():
            return nodes[0].attrib["version"]
        else:
            return None
    
    def set_version(self,version):
        nodes = self.xml_model.xpath('model')
        nodes[0].attrib["version"] = version

    def get_regions(self):
        regions={}
        for id in self.get_region_ids():
            regions[id]=self.get_region(id)
        return regions
    
    def get_output_listeners(self):
        nodes = self.xml_model.xpath('/model/output')
        listeners = []
        
        for n in nodes[0]:
            if n.tag == "raster":
                l = OutputFormats.RasterOutput(n)
                listeners.append(l)
            elif n.tag == "png":
                l = OutputFormats.PngOutput(n)
                listeners.append(l)
        return listeners

    def get_num_replicates(self, node=None):
        ''' If node == none then return the total number of replicates
        to run for each instance, otherwise return the number of completed
        replicates referred to by the node.
        
        '''
        if node is None:
            value = self.xml_model.xpath("/model/random/replicates")
            return int(value[0].text)
        else:
            nodes=node.xpath("replicates/replicate")
            return len(nodes)
        
    def set_num_replicates(self,max_r):
        value = self.xml_model.xpath("/model/random/replicates")
        value[0].text = repr(max_r)
        
    def get_completed_permutations(self):
        completed=[]
        nodes=self.xml_model.xpath("//instances/completed")
        
        for c_node in nodes:
            c = {}
            c["reps"] = []
            
            for c_detail in c_node:
                if c_detail.tag == "name":
                    c[c_detail.tag] = c_detail.text.strip()
                elif c_detail.tag == "region":
                    c[c_detail.tag] = c_detail.attrib["id"]
                elif c_detail.tag == "strategy":
                    c[c_detail.tag] = c_detail.attrib["name"]
                elif c_detail.tag == "variable":
                    if "variables" not in c.keys():
                        c["variables"] = []
                    c["variables"].append((c_detail.attrib["id"],
                                c_detail.text.strip()))
                elif c_detail.tag == "replicates":
                    rep_list = c_detail.xpath("child::replicate")
                    c["reps"] = rep_list
            completed.append(c)
        
        return completed
    
    def get_instance_permutations(self):
        ''' get_instances - return a list of instances
        '''
        instances={}
        permutations={}
        region_ids=self.get_region_ids()
        param_variables=self.get_variable_values()
        param_keys=param_variables.keys()
        total_instances=0
        strategies=self.get_management_strategies()
        if len(strategies) > 0:
            # Add a strategy of doing nothing for comparison
            strategies = [None] + strategies
        
        for r_id in region_ids:
            permutations[r_id] = {}
            p_r = permutations[r_id]
            
            p_r["var"] = self.permute_variables(param_variables, param_keys)
            p_r["var_keys"] = param_keys
            if len(strategies) > 0:
                p_r["var_keys"].insert(0,"__management_strategy")
                orig_permutations = p_r["var"]
                p_r["var"] = []
                for s in strategies:
                    if s is None:
                        for p in orig_permutations:
                            # add the strategy name to each variable permutation
                            p_r["var"].append([None] + p)
                    elif s.get_region() == r_id:
                        for p in orig_permutations:
                            # add the strategy name to each variable permutation
                            p_r["var"].append([s.get_name()] + p)

            p_r["reps"]=[self.get_num_replicates() for i in p_r["var"]]
            
            # If p_r["var"] length is 0 then there should still be
            # at least one instance that has no variables.
            total_instances += max(len(p_r["var"]),1)
            
        self.log.debug("Total number of instances: %d", total_instances)
        
        completed = self.get_completed_permutations()
        
        for c in completed:
            r_id = c["region"]
            strategy_name = None
            if "strategy" in c:
                strategy_name = c["strategy"]
                if strategy_name == "None":
                    strategy_name = None
            p = permutations[r_id]
            
            variable_list=[]
            for k in param_keys:
                variable_list.extend([cvar for c_varid, cvar in c["variables"] if c_varid == k])

            if len(strategies) > 0:
                variable_list.insert(0,strategy_name)
            
            v_index=-1
            if variable_list in p["var"]:
                v_index = p["var"].index(variable_list)
            elif len(variable_list) == 0 and len(p["var"]) == 0:
                # if there are no variables:
                v_index = 0
            
            if v_index != -1:
                if len(c["reps"]) >= self.get_num_replicates():
                    if len(p["reps"]) == 0:
                        # If there there are no variables
                        p["reps"].append(0)
                    else:
                        p["reps"][v_index] = 0
                    #p["var"].remove(variable_list)
                    #p["reps"].pop(v_index)
                else:
                    if len(p["reps"]) == 0:
                        # If there there are no variables
                        p["reps"].append(self.get_num_replicates() - len(c["reps"]))
                    else:
                        p["reps"][v_index] = p["reps"][v_index] - len(c["reps"])
            else:
                self.log.error("Completed instance doesn't match any expected instances")
                pdb.set_trace()
            
        self.log.debug(permutations)
        return permutations
        
    def permute_variables(self, variables, keys):
        results=[]
        if len(keys) > 0:
            current_key = keys[0]
            
            for i in variables[current_key]:
                results2=[]
                results2.extend(self.permute_variables(variables,keys[1:]))
                
                if len(results2)==0: results2=[[i]]
                else:
                    for r in results2: r.insert(0,i)
                
                results.extend(results2)
        return results
    
    def get_variable_values(self):
        var_values={}
        param_variables=self.xml_model.xpath("//lifestage/event/param/variable")
        for variable in param_variables:
            i = variable.attrib['id']
            var_values[i]=[]
            for node in variable:
                if node.tag=='value':
                    var_values[i].append(string.strip(node.text,"'"))
                elif node.tag=='range':
                    j=int(node.attrib['start'])
                    k=int(node.attrib['end'])
                    step=int(node.attrib['step'])
                    var_values[i] = range(j,k+1,step)
        return var_values
                    
    def get_description(self):
        desc=self.xml_model.xpath("/model/description")
        return desc[0].text.strip()
        
    def set_description(self,desc):
        node=self.xml_model.xpath("/model/description")
        node[0].text = desc
        
    def get_initial_maps(self, r_id):
        maps={}
        ls_ids = self.get_lifestage_ids()
        for id in ls_ids:
            imaps = self.get_lifestage(id).initial_maps
            if r_id in imaps:
                maps[id] = imaps[r_id]
            else:
                # lifestage doesn't have an initial map for this region
                maps[id] = GrassMap( \
                        filename=GRASSInterface.getG().get_blank_map())
        return maps
    
    def get_lifestage_ids(self):
        nodes = self.xml_model.xpath('/model/lifestages/lifestage')
        ls = {}
        for node in nodes:
            ls[node.attrib["name"]] = node
        return ls
        
    def get_lifestage(self, ls_id):
        if ls_id in self.lifestages.keys():
            return self.lifestages[ls_id]
        else:
            nodes = self.xml_model.xpath(
                    '/model/lifestages/lifestage[@name="%s"]' % ls_id)
            if len(nodes) == 1:
                self.lifestages[ls_id]=Lifestage(nodes[0])
                return self.lifestages[ls_id]
            else:
                self.log.error(
                        "Could not get unique lifestage from id '%s'" % ls_id)
        
    def get_lifestage_transition(self):
        if self.lifestage_transition is None:
            popmod_xml = self.get_popmod_file()
            if popmod_xml is not None:
                self.lifestage_transition = \
                    LifestageTransition(os.path.join(self.get_base_dir(), \
                                popmod_xml), self)
        return self.lifestage_transition

    def get_period(self):
        start_time = int(self.xml_model.xpath(
                    '/model/period/startTime/text()')[0])
        end_time = int(self.xml_model.xpath(
                    '/model/period/endTime/text()')[0])
        
        return (start_time, end_time)
    
    def update_occupancy_envelope(self, ls=None, time=None, force=False):
        instances = self.get_instances()
        
        if ls is None:
            ls = self.get_lifestage_ids().keys()
        
        for i in instances:
            self.log.debug( "Updating prob. envelope for instance %s" % repr(i) )
            period = self.get_period()
            if time is None:
                i.update_occupancy_envelope(ls, period[0], period[1],
                        force=force)
            else:
                if time < 0:
                    time = time + period[1]
                if time < period[0] or time > period[1]:
                    self.logger.error( "while creating probability envelope: " +
                            "time %d is outside of range [%d, %d]" %
                            ( time, period[0], period[1] ) )
                    sys.exit(2)
                i.update_occupancy_envelope(ls, time, time, force=force)
                
    def run_command_on_maps(self,cmd,ls,times=None,prob=True):
        for i in self.get_instances():
            if not i.is_complete():
                self.log.warning("Skipping incomplete instance " + repr(i))
                continue
            if prob:
                i.run_command_on_occupancy_envelopes(cmd,ls,times)
            else:
                i.run_command_on_replicates(cmd,ls,times)
        
    def add_replicate(self,completed_node):
        #search for completed/replicates node otherwise create
        replicates_node=completed_node.find('replicates')
        if replicates_node is None:
            replicates_node=lxml.etree.SubElement(completed_node,'replicates')
        
        replicate_node=lxml.etree.SubElement(replicates_node,'replicate')
        
        # Add new line so that completed section doesn't produce insanely long lines
        replicate_node.text = "\n"
        
        return replicate_node
        
    def get_completed_node(self,r_id,var_keys,var):
        
        xpath_str = '/model/instances/completed[region[@id="%s"]]' % r_id
        
        strat=0
        if var_keys is not None:
            for i in range(0,len(var_keys)):
                if var_keys[i] != '__management_strategy':
                    xpath_str += '[variable[@id="%s"]="%s"]' % (var_keys[i],var[i])
                elif var[i] is not None:
                    strat=1
                    xpath_str += '[strategy[@name="%s"]]' % (var[i])
        if strat==0:
            xpath_str+='[not(strategy)]'
        
        completed_node=self.xml_model.xpath(xpath_str)
        
        if len(completed_node) == 0:
            model_node=self.xml_model.getroot()
            completed_node=self._add_completed(r_id,var_keys,var)
        elif len(completed_node) == 1:
            completed_node = completed_node[0]
        else:
            self.log.warning("Multiple instances with same region and variable values, returning first")
            completed_node = completed_node[0]
        
        return completed_node
        
    def _add_completed(self,r_id,var_keys,var):
        mdig_config = MDiGConfig.getConfig()
        
        model_node=self.xml_model.getroot()
        
        completed_node=model_node.find('instances')
        if completed_node is None:
            completed_node = lxml.etree.SubElement(model_node,"instances")
        if self.base_dir is not None:
            completed_node.attrib["baseDir"] = self.base_dir
        
        completed_node = lxml.etree.SubElement(completed_node,"completed")
        
        region_node = lxml.etree.SubElement(completed_node,"region",{"id":r_id})
        if var_keys is not None:
            for i in range(len(var_keys)):
                if var_keys[i] == '__management_strategy':
                    if var[i] is not None:
                        lxml.etree.SubElement(completed_node,"strategy",{"name":var[i]})
                else:
                    var_node = lxml.etree.SubElement(completed_node,"variable",{"id":var_keys[i]})
                    if isinstance(var[i],str):
                        var_node.text = var[i]
                    else:
                        var_node.text = repr(var[i])
            
        self.log.debug('Added "completed" node: ' + repr(completed_node))
    
        return completed_node   
    
    def get_base_dir(self):
        completed_node = self.xml_model.xpath("/model/instances")
        
        if len(completed_node) > 0:
            if "baseDir" in completed_node[0].attrib.keys():
                return completed_node[0].attrib["baseDir"]
        return None
    
    def get_region_ids(self):
        nodes = self.xml_model.xpath("//regions/region/@id")
        #r_ids = {}
        #for node in nodes:
        #   r_ids[node.attrib["name"]] = node
        return nodes
        
    def get_region(self, r_id):
        if r_id in self.regions.keys():
            return self.regions[r_id]
        else:
            nodes = self.xml_model.xpath('/model/regions/region[@id="%s"]' % r_id)
            if len(nodes) == 1:
                self.regions[r_id]=Region(nodes[0])
                return self.regions[r_id]
            else:
                self.log.error("Could not get unique region from id '%s'" % r_id)

    def get_max_phenology_interval(self,region_id):
        maxInterval=-1
        for id in self.get_lifestage_ids():
            intervals=self.get_lifestage(id).getPhenologyIntervals(region_id)
            if len(intervals) > 0:
                maxInterval=max(maxInterval,max(intervals))
        return maxInterval
    
    def phenology_iterator(self,region_id):
        current_interval = -1
        max_interval = self.get_max_phenology_interval(region_id)
        while current_interval < max_interval:
            (ls, interval)=self.get_earliest_lifestage(region_id, current_interval)
            current_interval=interval
            
            for l in ls:
                #TODO: Make the lifestage ordering predictable (when interval is the same)
                yield (interval, ls)

    def get_earliest_lifestage(self, region_id, from_interval):
        earliest_interval = self.get_max_phenology_interval(region_id)
        earliest_ls = []
        
        for ls_id in self.get_lifestage_ids():
            ls=self.get_lifestage(ls_id)
            intervals = ls.getPhenologyIntervals(region_id)
            intervals = [i for i in intervals if i > from_interval]
            if len(intervals) == 0:
                # No more intervals in this lifestage
                continue
            if min(intervals) < earliest_interval:
                earliest_ls = [ls]
                earliest_interval=min(intervals)
            elif min(intervals) == earliest_interval:
                earliest_ls.append(ls)
        return (earliest_ls,earliest_interval)
            
    def remove_active_instance(self, instance):
        if instance in self.activeInstances:
            self.activeInstances.remove(instance)
        
    def add_active_instance(self, instance):
        if instance not in self.activeInstances:
            self.activeInstances.append(instance)
    
    def interval_modulus(self, interval, t):
        """
        Check that modulus of value - start of simulation period is 0
        Used for checking whether a map should be output etc.
        """
        if interval == 0:
            # If interval is zero we have to avoid divide by zero
            return 0
        elif interval == -1:
            # Always return 1 if there is not valid raster output interval
            return 1
        period = self.get_period()
        multiple = (t - period[0]) / interval
        remainder = (t - period[0]) - (multiple * interval)
        return remainder

    def interval_modulus_by_lifestage(self, ls_id, year):
        """
        Check that modulus of value - start of simulation period is 0
        Used for checking whether a map should be output etc.
        Get interval from lifestage
        """
        interval = self.get_map_output_interval(ls_id)
        return self.interval_modulus(interval, year)

    def map_year_generator(self, ls_id, period=[]):
        """
        Generate years that maps are supposed to be generated for a given lifestage
        """
        interval = self.get_map_output_interval(ls_id)
        if interval <= 0:
            return
        if not period:
            period = self.get_period()
        period = self.get_period()
        t = period[0]
        while t <= period[1]:
            yield t
            t = t + interval
        
    def get_map_output_interval(self,ls_id):
        """
        @todo make this obsolete, it's too much trouble to work out the logic
         for when not all past maps are available and just makes things
         confusing.
        """
        nodes = self.xml_model.xpath('/model/output/raster')
            
        for n in nodes:
            ls_node = [ls for ls in n.getchildren() if ls.tag == "lifestage"]
            if len(ls_node) > 1:
                self.log.warning("More than 1 raster output, will only return "
                        "interval the first.")
            if ls_node[0].text.strip() == ls_id:
                i_node = [i for i in n.getchildren() if i.tag == "interval"]
                return int(i_node[0].text)
        self.log.warning("No raster output for lifestage " + ls_id)
        return -1

    def get_management_strategies(self):
        if self.strategies is None:
            self.strategies = []
            # Load each strategy
            s_nodes = self.xml_model.xpath('/model/management/strategy')
            if len(s_nodes) == 0:
                return self.strategies
            for s_node in s_nodes:
                # Create strategy unassigned to any instance
                m = ManagementStrategy(s_node,None)
                self.strategies.append(m)
        return self.strategies

    def init_mapset(self):
        G = GRASSInterface.getG()
        if G.checkMapset(self.get_name()):
            G.changeMapset(self.get_name())
        else:
            self.log.info("Mapset " +self.get_name() + \
                    " doesn't exist, creating it.")
            G.changeMapset(self.get_name(),True)

    def get_mapset(self):
        """ Get the mapset where this model's maps are contained.

            Currently is the same as the model name. Not sure whether to change
            this?
        """
        return self.get_name()

    def move_mapset(self, new_mapset):
        """
        Moves all Grass related files to another mapset. Files that have mapset given
        using map@mapset notation are not moved, but others are.
        """
        G = GRASSInterface.getG()

        if G.checkMapset(new_mapset):
            self.log.error("Mapset %s already exists, shouldn't move into an existing mapset!" % new_mapset)
            raw_input("press enter to continue")

        ## Get all map names ##
        # create a dictionary, keys are filetype (vector/raster/region)
        # items are component names.
        components={}
        components["region"]=[]
        components["raster"]=[]
        components["vector"]=[]
        
        # Function to add map only if necessary, and put into correct array
        def add_map_to_move(x):
            if not x.temporary:
                if G.no_mapset_component(x.filename):
                    x_info=G.getMapInfo(x.filename)
                    components[x_info["type"]].append((x_info["name"],x_info["mapset"]))

        self.log.debug("Processing region files for copying")
        # Add region files and background maps if they exist
        for r in self.get_regions():
            # Regions
            r_name = self.get_regions()[r].get_name()
            if r_name and G.no_mapset_component(r_name):
                r_info = G.getMapInfo(r_name)
                components["region"].append((r_info["name"],r_info["mapset"]))

            # Background maps
            b_map = self.get_regions()[r].getBackgroundMap()
            add_map_to_move(b_map)         

            #if not bmap.temporary:
            #   if G.no_mapset_component(b_map.filename):
            #       b_info=G.getMapInfo(bmap.filename)
            #       components[b_info["type"]]=b_map.filename

            for ls_id in self.get_lifestage_ids():
                # Add initial distribution maps
                i_map = self.get_lifestage(ls_id).initial_maps[r]
                add_map_to_move(i_map)
                # Add phenology maps
                if r in self.get_lifestage(ls_id).p_map_names:
                    p_map = self.get_lifestage(ls_id).p_map_names[r]
                    add_map_to_move(p_map)

        # TODO: Moving Param maps?
        for i in self.get_instances():
            self.log.debug("Processing instance %s files for copying" % repr(i.variables))
            # Replicate maps
            for rep in i.replicates:
                for ls_id in self.get_lifestage_ids():
                    for r_id in rep.get_saved_maps(ls_id):
                        r_map = rep.get_saved_maps(ls_id)[r_id]
                        # r_map is just the map name not a GrassMap
                        
                        if G.no_mapset_component(r_map):
                            r_info=G.getMapInfo(r_map)
                            components[r_info["type"]].append((r_info["name"],r_info["mapset"]))
                            
            # Envelopes
            prob_env = i.get_occupancy_envelopes()
            if prob_env:
                for ls_id in self.get_lifestage_ids():
                    for t in prob_env[ls_id]:
                        e_map=prob_env[ls_id][t]
                        if G.no_mapset_component(e_map):
                            e_info=G.getMapInfo(e_map)
                            components[e_info["type"]].append((e_info["name"],e_info["mapset"]))
        ## Copy all maps ##
        self.log.debug("%d region to copy" % len(components["region"]))
        self.log.debug("%d raster maps to copy" % len(components["raster"]))
        self.log.debug("%d vector maps to copy" % len(components["vector"]))
        
        # Change into new mapset
        G.changeMapset(new_mapset, create=True)

        # Copy regions
        for r in components["region"]:
            r_map, r_mapset = r
            G.runCommand('g.copy region=%s@%s,%s' % (r_map, r_mapset, r_map), logging.DEBUG)

        # Copy rasters
        for r in components["raster"]:
            r_map, r_mapset = r
            G.runCommand('g.copy rast=%s@%s,%s' % (r_map, r_mapset, r_map), logging.DEBUG)

        # Copy vectors
        for v in components["vector"]:
            v_map, v_mapset = v
            G.runCommand('g.copy vect=%s@%s,%s' % (r_map, r_mapset, r_map), logging.DEBUG)

        ## Delete all maps ##
        self.log.debug("regions to delete: %s" % components["region"])
        self.log.debug("raster maps to delete: %s" % components["raster"])
        self.log.debug("vector maps to delete: %s" % components["vector"])

        if raw_input("Okay to delete these files (type yes if okay):") != "yes":
            return

        current_mapset = new_mapset # Remember mapset, only change if necessary

        # Del regions
        for r in components["region"]:
            r_map, r_mapset = r
            if r_mapset != current_mapset:
                G.changeMapset(r_mapset)
                current_mapset = r_mapset
            G.runCommand('g.remove region=%s' % r_map, logging.DEBUG)

        # Del rasters
        for r in components["raster"]:
            r_map, r_mapset = r
            if r_mapset != current_mapset:
                G.changeMapset(r_mapset)
                current_mapset = r_mapset
            G.runCommand('g.remove rast=%s' % r_map, logging.DEBUG)

        # Del vectors
        for v in components["vector"]:
            v_map, v_mapset = v
            if v_mapset != current_mapset:
                G.changeMapset(v_mapset)
                current_mapset = v_mapset
            G.runCommand('g.remove vect=%s' % r_map, logging.DEBUG)

        # Change into new mapset again
        G.changeMapset(new_mapset)

    def delete_maps(self):
        # TODO: implement me
        pass

    def clean_up(self):
        # stop any active instances
        for ai in self.activeInstances:
            ai.stop()
        
        # cleanup instances if they have been initialised
        if self.instances:
            for i in self.instances:
                i.clean_up()
        
        # cleanup lifestage maps if they have been initialised
        if len(self.lifestages.keys()) > 0:
            ls_ids = self.get_lifestage_ids()
            for id in ls_ids:
                self.get_lifestage(id).clean_up_maps()
            
    def save_model(self, filename=None):
        if filename is None:
            filename = self.model_filename
        
        try:
            if os.path.isfile(filename):
                if self.backup_filename is None:
                    fn = filename
                    count = 0
                    # If model filename exists then try and back it up first:
                    while os.path.isfile(fn):
                        fn = filename + ".bak"
                        if count > 0:
                            fn += repr(count)
                        count += 1
                    self.backup_filename = fn
                shutil.copyfile(filename, self.backup_filename)
                os.remove(filename)
        
            self.xml_model.write(filename)
        except OSError, e:
            self.log.error("Could save updated version of model file")
            self.log.error(e)
            
    def __repr__(self):
        # Prefixes attributes that are not None     
        mstr = []
        mstr.append( "Name: " + self.get_name() )
        mstr.append( "Version: " + str(self.get_version()) )
        mstr.append( "User: " + self.get_user() )
        mstr.append( "Description: " + self.get_description() )
        mstr.append( "#Lifestages: " + repr(len(self.get_lifestage_ids())) )
        mstr.append( "Time period: " + repr(self.get_period()) )
        return '\n'.join(mstr)

class CheckModelException(Exception): pass

class ValidationError(Exception): pass

class InvalidXMLException(Exception): pass

def open_anything(source):
        """URI, filename, or string --> stream
    
        This function lets you define parsers that take any input source
        (URL, pathname to local or network file, or actual data as a string)
        and deal with it in a uniform manner.  Returned object is guaranteed
        to have all the basic stdio read methods (read, readline, readlines).
        Just .close() the object when you're done with it.
        
        Examples:
        >>> from xml.dom import minidom
        >>> sock = open_anything("http://localhost/kant.xml")
        >>> doc = minidom.parse(sock)
        >>> sock.close()
        >>> sock = open_anything("c:\\inetpub\\wwwroot\\kant.xml")
        >>> doc = minidom.parse(sock)
        >>> sock.close()
        >>> sock = open_anything("<ref id='conjunction'><text>and</text><text>or</text></ref>")
        >>> doc = minidom.parse(sock)
        >>> sock.close()
        """
        if hasattr(source, "read"):
            return source
    
        if source == '-':
            import sys
            return sys.stdin
    
        # try to open with urllib (if source is http, ftp, or file URL)
        import urllib
        try:
            return urllib.urlopen(source)
        except (IOError, OSError):
            pass
        
        # try to open with native open function (if source is pathname)
        try:
            return open(source)
        except (IOError, OSError):
            pass
        
        print("Could not open %s as a file, using as a string instead", source)
        
        # treat source as string
        import StringIO
        return StringIO.StringIO(str(source)) 

def usage():
    print __doc__

def main(argv):
    modelFile = "example.xml"
    schemaFile = "mdig.xsd"
    try:
        opts, args = getopt.getopt(argv, "dm:s:", ["model=","schema="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-d':
            global _debug
            _debug = 1
        elif opt in ("-m", "--model"):
            modelFile = arg
        elif opt in ("-s", "--schema"):
            schemaFile = arg
    
    logger=setupLogger()
    logger.debug("Testing model interface")
    
    doc = DispersalModel(modelFile, schemaFile)
    print repr(doc.get_instances())
    
    #print doc.getCompleted()
    #print doc.getIncomplete()
    
    print doc.xml_model.xpath('/model/instances/completed[region[@id="%s"]][variable[@id="test"]="3"]' % "a")
    
    print "Number of replicates = " + repr(doc.get_num_replicates())

def setupLogger():
    logger = logging.getLogger("mdig")
    logger.setLevel(logging.INFO)
    #create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    #create formatter
    formatter = logging.Formatter("%(msecs)d - %(name)s - %(levelname)s - %(message)s")
    #add formatter to ch
    ch.setFormatter(formatter)
    #add ch to logger
    logger.addHandler(ch)
    
    return logger

if __name__ == "__main__":
    main(sys.argv[1:])
