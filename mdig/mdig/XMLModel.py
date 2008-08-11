#!/usr/bin/env python2.4
""" XMLModel module for MDiG - Modular Dispersal in GIS

Usage: python XMLModel.py [model=model.xml] [schema=model.xsd] to run
unit test on model.xml and validating with the schema model.xsd

By default example.xml will be loaded and validated with mdig.xsd

Copyright 2006, Joel Pitt
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
from ExperimentInstance import ExperimentInstance
from Event import Event
from Lifestage import Lifestage
from Analysis import Analysis
from Replicate import Replicate
from GrassMap import GrassMap

_debug=0


# An Experiment keeps track of general model data
class Experiment:

    def __init__(self, model_file):
        mdig_config = MDiGConfig.getConfig()
        
        self.log = logging.getLogger("mdig.exp")
        
        self.model_filename = model_file
        self.backup_filename = None
        self.regions={}
        self.lifestages={}
        self.instances = None
        self.activeInstances = []
        
        schema_file = sys.path[0]+"/mdig/mdig.xsd"
        self.loadXML(model_file)
        self.validateXML(schema_file)
        
        try:
            if mdig_config.check_model:
                self.checkModel()
        except CheckModelException, e:
            print e
            
        self.listeners = []
        outputListeners = self.getOutputListeners()
        for l in outputListeners:
            self.addListener(l)
    
        self.grass_i=GRASSInterface.getG()
        self.random = None
        
        self.active=False
        self.start_time = None
        self.end_time = None
        
        self.start = {}
        
        # Set up base directory for output
        if mdig_config.base_dir is None:
            if self.getBaseDir() is None:
                mdig_config.base_dir = os.path.dirname(mdig_config.model_file)
            else:
                mdig_config.base_dir = self.getBaseDir()
        else:
            if self.getBaseDir() is not None:
                logger.warning ("Model already specifies base directory, ignoring command line option")
                mdig_config.base_dir = self.getBaseDir()
        
        # Initialise paths
        mdig_config.makepaths()

    def _load(self, model_file):
        """load XML input source, return parsed XML document
        can be:
        - a URL of a remote XML file ("http://diveintopython.org/kant.xml")
        - a filename of a local XML file ("~/diveintopython/common/py/kant.xml")
        - standard input ("-")
        - the actual XML document, as a string
        """
        self.log.debug("Opening %s", model_file)
        sock = openAnything(model_file)
        
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

    def loadXML(self, model_file):
        """load mdig model file"""
        self.xml_model = self._load(model_file) 
        
    def validateXML(self, schema_file):
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
            
    def _getInstancesByRegion(self):
        instances = self.getInstances()
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
            if not i.isComplete() and (completed > max_reps or min_instance == None):
                min_instance = i
                max_reps = completed
            
        return min_instance
    
    def resetInstances(self):
        instances = self.getInstances()
        for i in instances:
            i.reset()
    
    def addListener(self,l):
        self.listeners.append(l)
        
    def removeListener(self,l):
        self.listeners.remove(l)
    
    def run(self):
        self.active = True
        self.start_time = datetime.now()
        self.log.info("Starting simulations at " + self.start_time.isoformat())
        
        r_instances = self._getInstancesByRegion()
        
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
        
    def isComplete(self):
        for i in self.getInstances():
            if not i.isComplete():
                return False
        return True
    
    def runCommandOnMaps(self, cmd_string, ls = None, times=None, prob=False):
        """ runCommandOnMaps
        
        cmd_string is the command to run, with %0 for current map,
        %1 for previous saved map, etc.
        
        ls_id is a list of lifestages to run command on
        
        times is a list of times to run command on
        
        prob specifies whether to run on the replicate maps or the probabilityEnvelopes
        
        """
        
        if ls is None:
            ls = self.getLifestageIDs().keys()
        elif not isinstance(ls, list):
            ls = [ls]
        
        if not self.isComplete():
            self.log.warning("Simulation is not complete")
        
        # Find earliest map in cmd_string (represented by %\d)
        earliest_map = 0
        map_matches = re.findall('(?<!%)%\d',cmd_string)
        for map_d in map_matches:
            map_index = int(map_d[1:])
            if map_index > earliest_map:
                earliest_map = map_index
        print ("Earliest map in cmd_string is %d before present" % earliest_map)
        
        mdig_config = MDiGConfig.getConfig()
        if mdig_config.analysis_filename is None:
            #create random name
            mdig_config.analysis_filename = repr(os.getpid()) +"_"+ repr(int(random.random()*1000000)) + ".dat"
        
        period = self.getPeriod()
        
        if prob:
            # if prob = True then only run on the probabilityEnvelopes
            for i in self.getInstances():
                if i.isComplete():
                    envelopes = i.getProbabilityEnvelopes()
                    for ls_id in ls:
                        e_times = [ int(t) for t in envelopes[ls_id].keys() ]
                        e_times.sort()
                        if times is None:
                            # if no time is user-specified, use all existing times,
                            # and sort because the return from keys() isn't guaranteed to be in order
                            times = e_times
                        else:
                            #check times
                            for t in times:
                                if t < 0:
                                    t = e_times[t]
                                if t < period[0] or t > period[1]:
                                    self.log.warning("Time outside simulation range: %d" % t)
                                if t not in e_times:
                                    self.log.warning("Time not in saved maps: %d" % t)
                            times.sort()
                        
                        tmp_fn = mdig_config.analysis_filename
                        #   append variable/ls/region info
                        tmp_fn = OutputFormats.createFilename(i) + "_" + tmp_fn
                        
                        # check if file exists
                        if os.path.isfile(tmp_fn):
                            
                            if mdig_config.overwrite_flag:
                                self.log.warning("Analysis output file exists")
                                os.remove(tmp_fn)
                            else:
                                self.log.error("Analysis output file exists")
                                sys.exit(9)
                        
                        # replace %f with analysis_filename (or generated name)
                        # if it exists in cmd_string
                        tmp_cmd_string = cmd_string
                        if re.search("%f",tmp_cmd_string) is not None:
                            # do reg ex replace
                            tmp_cmd_string = re.sub("%f", tmp_fn, tmp_cmd_string)
                        else:
                            # otherwise add output redirection >> to cmd_string
                            tmp_cmd_string += (" >> %s" % tmp_fn)
                        
                        # check that there are enough maps to satisfy the command line
                        # at least once.
                        if (len(times) - 1) < earliest_map:
                            self.log.warning("Not enough past maps to fulfill command line with earliest map %d maps before present" % earliest_map)
                        else:
                            # Skip ahead to the first time that has enough past maps to
                            # satisfy the command line.
                            for t in times[earliest_map:]:
                                # replace %t with current time if it exists in cmd_string
                                tmp_cmd_string2 = re.sub("%t", repr(t), tmp_cmd_string)
                                
                                # Replace %(number) references with the map names
                                map_matches = re.findall('(?<!%)%\d',tmp_cmd_string2)
                                for map_d in map_matches:
                                    map_index = int(map_d[1:])
                                    
                                    tmp_cmd_string2 = re.sub("%" + repr(map_index), envelopes[ls_id][repr(times[times.index(t)-map_index])], tmp_cmd_string2)
                                
                                if mdig_config.analysis_print_time:
                                    file = open(tmp_fn,'a')
                                    file.write('%d ' % t)
                                    file.close()
                                
                                # run command on prob env map
                                self.log.debug("Running analysis command: " + tmp_cmd_string2 )
                                cmd_stdout = os.popen(tmp_cmd_string2,"r")
                                stdout = cmd_stdout.read()
                                ret = cmd_stdout.close()
                                if ret is not None:
                                    self.log.error("Analysis command did not return 0")
                                
                            if mdig_config.analysis_add_to_xml:
                                # add the analysis result to xml filename
                                # under instance...
                                i.addAnalysisResult(ls_id, (cmd_string, tmp_fn))
                                
                                pass
                else:
                    self.log.warning("Skipping incomplete instance [%s]" % i)

        else:
            # otherwise run on each replicate map
            for i in self.getInstances():
                if not i.isComplete():
                    self.log.warning("Instance [%s] is incomplete" % i)
                
                #for r in i.replicates:
                    #envelopes = i.getProbabilityEnvelopes()
                    #e_times = [ int(t) for t in envelopes.keys() ]
                    #if times is none:
                    #times = e_times
                
                #for t in times:
                    #if t < 0:
                        # t = period[1] + t
                    #if t < period[0] or t > period[1]:
                        #self.log.warning("Time outside simulation range: %d" % t)
                    #elif t not in e_times:
                        #self.log.warning("Time not in saved maps: %d" % t)
                    #else:
                        # replace %t with current time if it exists in cmd_string
                            
                        # replace %f with analysis_filename (or generated name)
                        # if it exists in cmd_string
                        
                        # run command on prob env map
                
            
        
        
        # run command only on maps that have past maps that satisfy cmd_string.
        
        
        # replace %\d with the appropriate map names using re.sub and a calleable.
    
    def nullBitmask(self, generate=True):
        instances = self.getInstances()
        for i in instances:
            if generate:
                log_str = "Generating"
            else:
                log_str = "Deleting"
            log_str=log_str+" bitmasks for instance %d of %d." % (instances.index(i)+1,len(instances))
            self.log.info(log_str)
            i.nullBitmask(generate)
    
    def prepareRun(self):
        pass
    
    def getInstances(self):
        if self.instances is None:
            self.instances = []
            permutations = self.getInstancePermutations()
            
            # Turn each returned variable combination into an actual
            # ExperimentInstance object instance
            for r_id, p in permutations.items():
                num_perms = len(p["var"])
                # If no variables in experiment:
                if num_perms == 0:
                    node = self.getCompletedNode(r_id,None,None)
                    self.instances.append( \
                           ExperimentInstance(node,self,r_id,None,None))
                # If variables are in experiment:
                else:
                    for i in range(0, num_perms):
                        node = self.getCompletedNode(r_id,p["var_keys"],p["var"][i])
                        self.instances.append( \
                           ExperimentInstance(node,self,r_id,p["var_keys"],p["var"][i]))
            
            for instance in self.instances:
                #instance.setReplicates(self.getCompletedReplicates(instance))
                instance.listeners.extend(self.listeners)
            
        return self.instances
                
    
    def getIncompleteInstances(self):
        return [i for i in self.getInstances() if not i.isComplete()]
    
                
    def checkModel(self):
        
        self.log.info(self.getDescription())
        self.log.debug("Checking model maps exist")
        
        # - can check maps just by attempting to get the map
        # - functions create GrassMap's automatically and
        # checks the map exists
        
        #check background map
        for r_id, region in self.getRegions().items():
            region.getBackgroundMap()
        #check initial map for each lifestage exists
            for ls_key in self.getLifestageIDs():
                ls = self.getLifestage(ls_key)
                
        #check phenology maps exist
        
        #Check that the event commands exist or are supported.
        
        
        #self.grass_i.checkMap(self.model.getBackgroundMap())
    
    def getUser(self):
        nodes = self.xml_model.xpath('user/email')
        if len(nodes) == 1:
            return nodes[0].text.strip()
        
    def setUser(self,email):
        nodes = self.xml_model.xpath('user/email')
        if len(nodes) == 1:
            nodes[0].text = email
        
    def getName(self):
        nodes = self.xml_model.xpath('/model/name')
        return nodes[0].text.strip()
        
    def setName(self,name):
        nodes = self.xml_model.xpath('/model/name')
        nodes[0].text = name
        
    def getInitialRandomSeed(self):
        nodes = self.xml_model.xpath('/model/random/initialSeed')
        if len(nodes) == 1:
            return int(nodes[0].text)
        else:
            return None
                
    #def setRandom(self, seed, state):
    #   nodes = self.xml_model.xpath('/model/random/initialSeed')
    #   nodes[0].text = repr(seed)
    #   nodes = self.xml_model.xpath('model/random/lastState')
    #   nodes[0].text = repr(state)

    def initRandomWithOffset(self,seed,offset):
        i_seed = self.getInitialRandomSeed()
        my_random = random.Random()
        
        my_random.seed(i_seed)
        
        if i_seed is None:
            # ignore offset if seed isn't specified
            self.log.warning('No initial seed specified - using OS generated seed. You will not be able to rerun this exact simulation in future')
        else:
            my_random.seed(i_seed)
            while offset > 0:
                my_random.randint(-2.14748e+09,2.14748e+09)
                offset -= 1
            
        return my_random
        
    def getNextRandomValue(self):
        if self.random is None:
            offset = self.getRandomOffset()
            seed = self.getInitialRandomSeed()
            self.random = self. initRandomWithOffset(seed,offset)
            
        value=self.random.randint(-2.14748e+09,2.14748e+09)
        self.incRandomOffset()
        return value
    
    def incRandomOffset(self):
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
    
    def getRandomOffset(self):
        nodes = self.xml_model.xpath('/model/random/offset')
        if len(nodes) == 1:
            return int(nodes[0].text)
        else:
            return None
        #[int(child.attrib["a"]),int(child.attrib["b"]),int(child.attrib["c"])]
        
    def getVersion(self):
        nodes = self.xml_model.xpath('model')
        if len(nodes) > 0 and "version" in nodes[0].attrib.keys():
            return nodes[0].attrib["version"]
        else:
            return None
    
    def setVersion(self,version):
        nodes = self.xml_model.xpath('model')
        nodes[0].attrib["version"] = version

    def getRegions(self):
        regions={}
        for id in self.getRegionIDs():
            regions[id]=self.getRegion(id)
        return regions
    
    def getOutputListeners(self):
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


    def getNumberOfReplicates(self, node=None):
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
        
    def setNumberOfReplicates(self,max_r):
        value = self.xml_model.xpath("/model/random/replicates")
        value[0].text = repr(max_r)
        
    def getCompletedPermutations(self):
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
    
    def getInstancePermutations(self):
        ''' getInstances - return a list of instances
        '''
        instances={}
        permutations={}
        region_ids=self.getRegionIDs()
        param_variables=self.getVariableValues()
        param_keys=param_variables.keys()
        total_instances=0
        
        for r_id in region_ids:
            permutations[r_id] = {}
            p_r = permutations[r_id]
            
            p_r["var"] = self.permuteVariables(param_variables, param_keys)
            p_r["var_keys"] = param_keys
            p_r["reps"]=[self.getNumberOfReplicates() for i in p_r["var"]]
            
            # If p_r["var"] length is 0 then there should still be
            # at least one instance that has no variables.
            total_instances += max(len(p_r["var"]),1)
            
        self.log.debug("Total number of instances: %d", total_instances)
        
        completed = self.getCompletedPermutations()
        
        for c in completed:
            r_id = c["region"]
            p = permutations[r_id]
            
            variable_list=[]
            for k in param_keys:
                variable_list.extend([cvar for c_varid, cvar in c["variables"] if c_varid == k])
            
            v_index=-1
            if variable_list in p["var"]:
                v_index = p["var"].index(variable_list)
            elif len(variable_list) == 0 and len(p["var"]) == 0:
                # if there are no variables:
                v_index = 0
            
            #pdb.set_trace()
            if v_index != -1:
                if len(c["reps"]) >= self.getNumberOfReplicates():
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
                        p["reps"].append(self.getNumberOfReplicates() - len(c["reps"]))
                    else:
                        p["reps"][v_index] = p["reps"][v_index] - len(c["reps"])
            
        self.log.debug(permutations)
        return permutations
        
    def permuteVariables(self, variables, keys):
        results=[]
        if len(keys) > 0:
            current_key = keys[0]
            
            for i in variables[current_key]:
                results2=[]
            
                results2.extend(self.permuteVariables(variables,keys[1:]))
                
                if len(results2)==0: results2=[[i]]
                else:
                    for r in results2: r.insert(0,i)
                
                results.extend(results2)
        return results
    
    def getVariableValues(self):
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
                    
    def getDescription(self):
        desc=self.xml_model.xpath("/model/description")
        return desc[0].text.strip()
        
    def setDescription(self,desc):
        node=self.xml_model.xpath("/model/description")
        node[0].text = desc
        
    def getInitialMaps(self, r_id):
        maps={}
        ls_ids = self.getLifestageIDs()
        for id in ls_ids:
            lmap = self.getLifestage(id).initial_maps[r_id]
            if lmap is not None: maps[id] = lmap
            
        return maps
    
    def getLifestageIDs(self):
        nodes = self.xml_model.xpath('/model/lifestages/lifestage')
        ls = {}
        for node in nodes:
            ls[node.attrib["name"]] = node
        return ls
        
    def getLifestage(self, ls_id):
        if ls_id in self.lifestages.keys():
            return self.lifestages[ls_id]
        else:
            nodes = self.xml_model.xpath('/model/lifestages/lifestage[@name="%s"]' % ls_id)
            if len(nodes) == 1:
                self.lifestages[ls_id]=Lifestage(nodes[0])
                return self.lifestages[ls_id]
            else:
                self.log.error("Could not get unique lifestage from id '%s'" % ls_id)
        
    def getPeriod(self):
        start_time = int(self.xml_model.xpath('/model/period/startTime/text()')[0])
        end_time = int(self.xml_model.xpath('/model/period/endTime/text()')[0])
        
        return (start_time, end_time)
    
    def updateProbabilityEnvelope(self, ls=None, time=None, force=False):
        instances = self.getInstances()
        
        if ls is None:
            ls = self.getLifestageIDs().keys()
        
        for i in instances:
            self.log.debug( "Updating prob. envelope for instance %s" % repr(i) )
            period = self.getPeriod()
            if time is None:
                i.updateProbabilityEnvelope(ls, period[0], period[1],
                        force=force)
            else:
                if time < 0:
                    time = time + period[1]
                if time < period[0] or time > period[1]:
                    self.logger.error( "while creating probability envelope: time %d is outside of range [%d, %d]" % ( time, period[0], period[1] ) )
                    sys.exit(2)
                i.updateProbabilityEnvelope(ls, time, time, force=force)
                
        
        
    def addReplicate(self,completed_node):
        #search for completed/replicates node otherwise create
        replicates_node=completed_node.find('replicates')
        if replicates_node is None:
            replicates_node=lxml.etree.SubElement(completed_node,'replicates')
        
        replicate_node=lxml.etree.SubElement(replicates_node,'replicate')
        
        # Add new line so that completed section doesn't produce insanely long lines
        replicate_node.text = "\n"
        
        return replicate_node
        
    def getCompletedNode(self,r_id,var_keys,var):
        
        xpath_str = '/model/instances/completed[region[@id="%s"]]' % r_id
        
        if var_keys is not None:
            for i in range(0,len(var_keys)):
                xpath_str += '[variable[@id="%s"]="%s"]' % (var_keys[i],var[i])
        
        completed_node=self.xml_model.xpath(xpath_str)
        
        if len(completed_node) == 0:
            model_node=self.xml_model.getroot()
            completed_node=self._addCompleted(r_id,var_keys,var)
        elif len(completed_node) == 1:
            completed_node = completed_node[0]
        else:
            self.log.warning("Multiple instances with same region and variable values, returning first")
            completed_node = completed_node[0]
            
        
        return completed_node
        
    def _addCompleted(self,r_id,var_keys,var):
        mdig_config = MDiGConfig.getConfig()
        
        model_node=self.xml_model.getroot()
        
        completed_node=model_node.find('instances')
        if completed_node is None:
            completed_node = lxml.etree.SubElement(model_node,"instances")
            if mdig_config.base_dir is not None:
                completed_node.attrib["baseDir"] = mdig_config.base_dir
        
        completed_node = lxml.etree.SubElement(completed_node,"completed")
        
        region_node = lxml.etree.SubElement(completed_node,"region",{"id":r_id})
        if var_keys is not None:
            for i in range(len(var_keys)):
                var_node = lxml.etree.SubElement(completed_node,"variable",{"id":var_keys[i]})
                if isinstance(var[i],str):
                    var_node.text = var[i]
                else:
                    var_node.text = repr(var[i])
            
        self.log.debug('Added "completed" node: ' + repr(completed_node))
    
        return completed_node   
    
    def getBaseDir(self):
        completed_node = self.xml_model.xpath("/model/instances")
        
        if len(completed_node) > 0:
            if "baseDir" in completed_node[0].attrib.keys():
                return completed_node[0].attrib["baseDir"]
        return None
    
    def getRegionIDs(self):
        nodes = self.xml_model.xpath("//regions/region/@id")
        #r_ids = {}
        #for node in nodes:
        #   r_ids[node.attrib["name"]] = node
        return nodes
        
    def getRegion(self, r_id):
        if r_id in self.regions.keys():
            return self.regions[r_id]
        else:
            nodes = self.xml_model.xpath('/model/regions/region[@id="%s"]' % r_id)
            if len(nodes) == 1:
                self.regions[r_id]=Region(nodes[0])
                return self.regions[r_id]
            else:
                self.log.error("Could not get unique region from id '%s'" % r_id)

    def getMaximumPhenologyInterval(self,region_id):
        maxInterval=-1
        for id in self.getLifestageIDs():
            intervals=self.getLifestage(id).getPhenologyIntervals(region_id)
            if len(intervals) > 0:
                maxInterval=max(maxInterval,max(intervals))
        return maxInterval
    
    def phenologyIterator(self,region_id):
        current_interval = -1
        max_interval = self.getMaximumPhenologyInterval(region_id)
        while current_interval < max_interval:
            (ls, interval)=self.getEarliestLifestage(region_id, current_interval)
            current_interval=interval
            
            for l in ls:
                #TODO: Make the lifestage ordering predictable (when interval is the same)
                yield (interval, ls)

    def getEarliestLifestage(self, region_id, from_interval):
        earliest_interval = self.getMaximumPhenologyInterval(region_id)
        earliest_ls = []
        
        for ls_id in self.getLifestageIDs():
            ls=self.getLifestage(ls_id)
            intervals = ls.getPhenologyIntervals(region_id)
            intervals = [i for i in intervals if i > from_interval]
            if min(intervals) < earliest_interval:
                earliest_ls.append(ls)
                earliest_interval=min(intervals)
            elif min(intervals) == earliest_interval:
                earliest_ls = [ls]
        return (earliest_ls,earliest_interval)
            
    def removeActiveInstance(self, instance):
        if instance in self.activeInstances:
            self.activeInstances.remove(instance)
        
    def addActiveInstance(self, instance):
        if instance not in self.activeInstances:
            self.activeInstances.append(instance)
    
    def intervalModulus(self, interval, t):
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
        period = self.getPeriod()
        multiple = (t - period[0]) / interval
        remainder = (t - period[0]) - (multiple * interval)
        return remainder

    def intervalModulusByLifestage(self, ls_id, year):
        """
        Check that modulus of value - start of simulation period is 0
        Used for checking whether a map should be output etc.
        Get interval from lifestage
        """
        interval = self.getMapOutputInterval(ls_id)
        return self.intervalModulus(interval, year)

    def mapYearGenerator(self, ls_id, period=[]):
        """
        Generate years that maps are supposed to be generated for a given lifestage
        """
        interval = self.getMapOutputInterval(ls_id)
        if interval <= 0:
            return
        if not period:
            period = self.getPeriod()
        period = self.getPeriod()
        t = period[0]
        while t <= period[1]:
            yield t
            t = t + interval
        
    def getMapOutputInterval(self,ls_id):
        nodes = self.xml_model.xpath('/model/output/raster')
            
        for n in nodes:
            ls_node = [ls for ls in n.getchildren() if ls.tag == "lifestage"]
            if len(ls_node) > 1:
                self.warning("More than 1 raster output, will only return "
                        "interval the first.")
            if ls_node[0].text.strip() == ls_id:
                i_node = [i for i in n.getchildren() if i.tag == "interval"]
                return int(i_node[0].text)
        self.log.warning("No raster output for lifestage " + ls_id)
        return -1

    def moveMapset(self, new_mapset):
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
        
        # Function to check mapset isn't in map name
        def noMapsetComponent(x):
            if x.find("@") == -1:
                return True
            else:
                return False

        # Function to add map only if necessary, and put into correct array
        def addMapToMove(x):
            if not x.temporary:
                if noMapsetComponent(x.filename):
                    x_info=G.getMapInfo(x.filename)
                    components[x_info["type"]].append((x_info["name"],x_info["mapset"]))

        self.log.debug("Processing region files for copying")
        # Add region files and background maps if they exist
        for r in self.getRegions():
            # Regions
            r_name = self.getRegions()[r].getName()
            if r_name and noMapsetComponent(r_name):
                r_info = G.getMapInfo(r_name)
                components["region"].append((r_info["name"],r_info["mapset"]))

            # Background maps
            b_map = self.getRegions()[r].getBackgroundMap()
            addMapToMove(b_map)         

            #if not bmap.temporary:
            #   if noMapsetComponent(b_map.filename):
            #       b_info=G.getMapInfo(bmap.filename)
            #       components[b_info["type"]]=b_map.filename

            for ls_id in self.getLifestageIDs():
                # Add initial distribution maps
                i_map = self.getLifestage(ls_id).initial_maps[r]
                addMapToMove(i_map)
                # Add phenology maps
                if r in self.getLifestage(ls_id).p_map_names:
                    p_map = self.getLifestage(ls_id).p_map_names[r]
                    addMapToMove(p_map)

        # TODO: Moving Param maps?
        
        for i in self.getInstances():
            self.log.debug("Processing instance %s files for copying" % repr(i.variables))
            # Replicate maps
            for rep in i.replicates:
                for ls_id in self.getLifestageIDs():
                    for r_id in rep.getSavedMaps(ls_id):
                        r_map = rep.getSavedMaps(ls_id)[r_id]
                        # r_map is just the map name not a GrassMap
                        
                        if noMapsetComponent(r_map):
                            r_info=G.getMapInfo(r_map)
                            components[r_info["type"]].append((r_info["name"],r_info["mapset"]))
                            
            # Envelopes
            prob_env = i.getProbabilityEnvelopes()
            if prob_env:
                for ls_id in self.getLifestageIDs():
                    for t in prob_env[ls_id]:
                        e_map=prob_env[ls_id][t]
                        if noMapsetComponent(e_map):
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

    def deleteMaps(self):
        pass

    def cleanUp(self):
        # stop any active instances
        for ai in self.activeInstances:
            ai.stop()
        
        # cleanup instances if they have been initialised
        if self.instances:
            for i in self.instances:
                i.cleanUp()
        
        # cleanup lifestage maps if they have been initialised
        if len(self.lifestages.keys()) > 0:
            ls_ids = self.getLifestageIDs()
            for id in ls_ids:
                self.getLifestage(id).cleanUpMaps()
            
    def saveModel(self, filename=None):
        
        if filename is None:
            filename = self.model_filename
        
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
        
        try:
            os.remove(filename)
            self.xml_model.write(filename)
        except OSError, e:
            self.log.error("Could save updated version of model file")
            self.log.error(e)
            
    def __repr__(self):
        # Prefixes attributes that are not None     
        return '; '.join([ ":".join([j,i]) for j,i in [
            ("Name",self.name),
            ("Version",self.version),
            ("User",self.user),
            ("Description",self.description)] if i ] )

class CheckModelException(Exception): pass

class ValidationError(Exception): pass

class InvalidXMLException(Exception): pass

def openAnything(source):
        """URI, filename, or string --> stream
    
        This function lets you define parsers that take any input source
        (URL, pathname to local or network file, or actual data as a string)
        and deal with it in a uniform manner.  Returned object is guaranteed
        to have all the basic stdio read methods (read, readline, readlines).
        Just .close() the object when you're done with it.
        
        Examples:
        >>> from xml.dom import minidom
        >>> sock = openAnything("http://localhost/kant.xml")
        >>> doc = minidom.parse(sock)
        >>> sock.close()
        >>> sock = openAnything("c:\\inetpub\\wwwroot\\kant.xml")
        >>> doc = minidom.parse(sock)
        >>> sock.close()
        >>> sock = openAnything("<ref id='conjunction'><text>and</text><text>or</text></ref>")
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
    
    doc = Experiment(modelFile, schemaFile)
    print repr(doc.getInstances())
    
    #print doc.getCompleted()
    #print doc.getIncomplete()
    
    print doc.xml_model.xpath('/model/instances/completed[region[@id="%s"]][variable[@id="test"]="3"]' % "a")
    
    print "Number of replicates = " + repr(doc.getNumberOfReplicates())

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
