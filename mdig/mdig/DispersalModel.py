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
import logging.handlers
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

class MissingFileException(Exception):
    def __init__(self,desc,files=[]):
        Exception(desc)
        self.desc = desc
        self.files = files

    def __str__(self):
        return "RepositoryException: " + self.desc + str(self.files)

# Thrown when repository needs to be migrated
class UpgradeRequired(Exception): pass

class DispersalModel(object):
    """ DispersalModel keeps track of general model data and allows high level
        control of running simulations and analysis.
    """

    def __init__(self, model_file=None, the_action = None, setup=True):
        self.action = the_action
        
        self.log = logging.getLogger("mdig.model")
	self.log_handler=None

        self.model_file = model_file
        self.backup_filename = None
        self.regions={}
        self.ls_ids=None
        self.lifestages={}
        self.instances = None
        self.strategies = None
        self.activeInstances = []
        self.lifestage_transitions = None
        self.listeners = []

        schema_file = os.path.join(os.path.dirname(__file__),"mdig.xsd")
        if model_file:
            self.load_xml(model_file)
            self.validate_xml(schema_file)
            outputListeners = self.get_output_listeners()
            for l in outputListeners:
                self.add_listener(l)
        else:
            self.xml_model = lxml.etree.Element("model")
        
        self.grass_i=GRASSInterface.get_g()
        self.random = None
        
        self.active=False
        self.start_time = None
        self.end_time = None
        
        self.start = {}
        self.instance_mapsets = []
        
        if self.action is not None:
            try:
                if self.action.check_model:
                    self.check_model()
            except CheckModelException, e:
                print e
                
        self.base_dir = None
        if self.model_file:
            self.log_file = None
            if self.action is not None:
                self.set_base_dir(self.action.output_dir)
                self.setup_logfile()
            elif setup:
                self.set_base_dir() 
            if setup:
                self.init_mapset()
                self.setup_logfile()

    def setup_logfile(self):
        if self.log_file: return 
        self.log_file = os.path.join(self.base_dir, "model.log")
        logformat = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt='%Y%m%d %H:%M:%S')
        rollover=False
        if os.path.isfile(self.log_file):
            rollover=True
        count=0
        fh = None
	# next two lines are hack to avoid using RotatingFileHandler in
	# Windows
	if sys.platform == "win32":
	    # Windows isn't a real operating system and when there a multiple
	    # threads it complains about renaming files that are open by another
	    # thread... so instead, we have to create another name...
	    base_fn = self.log_file
	    try:
		if rollover: self.backup_file(self.log_file)
	    except OSError, e:
		# If we couldn't backup file then we need to find a free file
		self.log_file = os.path.join(self.base_dir, "model_process_%d.log" % count)
	    while fh is None and count < 10:
		try:
		    fh = logging.FileHandler(self.log_file)
		except OSError, e:
		    count += 1
		    self.log_file = os.path.join(self.base_dir, "model_process_%d.log" % count)
	    # TODO, delete the file
	else:
	    fh = logging.handlers.RotatingFileHandler(self.log_file,maxBytes=0,backupCount=5)
	    if rollover: fh.doRollover()
        fh.setFormatter(logformat)
        # If we start having multiple simulations at once, then this should be
        # changed (and also areas that are not under mdig.model)
        logging.getLogger("mdig").addHandler(fh)
	self.log_handler=fh

    def __del__(self):
	self.remove_log_handler()

    def remove_log_handler(self):
	""" Manually clean up logs since Windows can't handler renaming an
	open file and things get messed up
	"""
	if self.log_handler:
            logging.getLogger("mdig").removeHandler(self.log_handler)
	    self.log_handler.close()
	    self.log_handler=None
	    self.log_file=None

    def set_base_dir(self, dir=None):
        # Set up base directory for output
        self.base_dir = None
        if dir is not None:
            self.base_dir = dir
        elif self.model_file:
            self.base_dir = os.path.dirname(self.model_file)
        if self.base_dir:
            # Initialise paths
            self.init_paths()

    def init_paths(self):
        c = MDiGConfig.get_config()
        assert( self.base_dir is not None )
        base_d = self.base_dir
        filename = os.path.join(base_d, c.analysis_dir)
        MDiGConfig.makepath(filename)
        filename = os.path.join(base_d, c.maps_dir)
        MDiGConfig.makepath(filename)
        filename = os.path.join(base_d, c.output_dir)
        MDiGConfig.makepath(filename)

    def _load(self, model_file):
        """load XML input source, return parsed XML document
        must be a filename of a local XML file
        """
        sock = open(model_file)
        
        try:
            parser = lxml.etree.XMLParser(remove_blank_text=True)
            xmltree = lxml.etree.parse(sock,parser)
        except lxml.etree.XMLSyntaxError, e:
            self.log.error("Error parsing %s", model_file)
            if hasattr(e,"error_log"):
                log = e.error_log.filter_levels(lxml.etree.ErrorLevels.FATAL)
                print log
            sys.exit(3)
        
        sock.close()
        return xmltree

    def load_xml(self, model_file):
        """load mdig model file"""
        self.log.debug("Opening %s", model_file)
        self.xml_model = self._load(model_file) 
        
    def validate_xml(self, schema_file):
        #self.log.debug("Loading schema %s", schema_file)
        try:
            self.schema_doc = lxml.etree.parse(schema_file)
            self.xml_schema = lxml.etree.XMLSchema(self.schema_doc)
        except lxml.etree.XMLSyntaxError, e:
            log = e.error_log
            self.log.error(log)
            raise e
        except lxml.etree.XMLSchemaParseError, e:
            log = e.error_log
            self.log.error(log)
            raise e
            
        if not self.xml_schema.validate(self.xml_model):
            self.log.error("%s not valid according to Schema %s",
                    self.model_file,schema_file)
            
            # early versions of lxml didn't support verbose error information
            if "error_log" in dir(self.xml_schema):
                log = self.xml_schema.error_log
                errors = log.filter_from_errors()
                print errors
            raise ValidationError()
        
        self.schema_file=schema_file
            
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
        
        for i in [ii for ii in instances if ii.enabled]:
            completed = len([x for x in i.replicates if x.complete])
            if not i.is_complete() and (completed > max_reps or min_instance == None):
                min_instance = i
                max_reps = completed
            
        return min_instance

    def create_instance_mapset_name(self):
        """ To be called by Dispersal instances when they want a mapset to do
        their simulations in - this may use the suffix # which is the same the
        instance's index, but it's not guaranteed (depends what mapsets already
        exist) """
        base_mapset_name = self.get_mapset()
        counter=0
        mapset_exists = True
        g = self.grass_i
        # also check whether the mapset is in the model.xml (because an instance
        # might not have actually created the mapset yet)
        while mapset_exists:
            i_mapset = base_mapset_name + "_i" + str(counter)
            if i_mapset not in self.instance_mapsets:
                mapset_exists = g.check_mapset(i_mapset,self.infer_location())
            counter+=1
        self.instance_mapsets.append(i_mapset)
        return i_mapset
    
    def reset_instances(self):
        instances = self.get_instances()
        for i in [x for x in instances if x.enabled]:
            i.reset()

    def get_instance_mapsets(self):
        """ Get instance mapsets by directly obtaining the xml references and
        mapsets that refer to the model's main mapset """

        # Get directly from instances
        maps = set([])
        instances = self.get_instances()
        for i in instances:
            maps.add(i.get_mapset())
        # Also check GRASS DB for orphaned mapsets
        g = GRASSInterface.get_g()
        db = g.grass_vars['GISDBASE']
        location = self.infer_location()
        mapsets_dir = os.path.join(db,location)
        if os.path.isdir(mapsets_dir):
            for mapset in os.listdir(mapsets_dir):
                mdig_dir = os.path.join(mapsets_dir,mapset,'mdig')
                fn = os.path.join(mdig_dir, 'original_model')
                if os.path.isdir(mdig_dir) and os.path.isfile(fn):
                    f = open(fn,'r')
                    model_name=f.readlines()[0].strip()
                    if model_name == self.get_name():
                        maps.add(mapset)
        return maps

    def hard_reset(self):
        """ A hard reset actually deletes entire instance mapsets and removes
        any xml traces of prior runs. This is probably preferable in most
        cases... but reset_instances was appropriate for when everything was
        in a single mapset """
        g = GRASSInterface.get_g()
        for mapset in self.get_instance_mapsets():
            # Don't let the core mapset disappear
            if self.get_name() == mapset: continue
            db = g.grass_vars['GISDBASE']
            location = self.infer_location()
            ms_dir = os.path.join(db,location,mapset)
            try:
                shutil.rmtree(ms_dir)
            except OSError, e:
                # it's okay if the directories don't actually exist, as we want
                # to want to remove them anyhow
                if "No such file or directory" in str(e): pass
                else: raise e
        instances_node = self.xml_model.xpath('/model/instances')
        if len(instances_node) > 0:
            i = instances_node[0]
            i.getparent().remove(i)

    def get_resources(self):
        """ Aggregate all the files the simulation depends on.
        returns a list of 3-tuples:
        (type,name,location) ...
        type is one of 'map','region','popmod','coda'
        name is the name of resource
        location is None if resource is missing, otherwise it's a filename or
        mapset
        """
        # change into appropriate mapset
        g = GRASSInterface.get_g()
        g.change_mapset(self.get_mapset())
        # get maps
        maps = self.get_map_resources()
        # get saved regions
        regions = [r.get_name() for r in self.get_regions().values() if r.get_name() is not None]
        regions = set(regions)
        # get popmod files
        popmod_files = self.get_popmod_files()
        popmod_files = set(popmod_files)
        all_coda_files = []
        for lt in self.get_lifestage_transitions():
            all_coda_files.extend(lt.get_coda_files_in_xml())
        all_coda_files = set(all_coda_files)
        # join them all together
        resources = []
        if maps is not None:
            for m,mapset in maps:
                resources.append(('map',m,mapset))
        for r in regions:
            # check where regions exist
            r_mapset = None
            try:
                import StringIO
                # -u avoids changing region
                ret = g.run_command('g.findfile element=windows file=%s' % r)
                out_lines = StringIO.StringIO(g.stdout).readlines()
                r_mapset = out_lines[1].split('=')[1].strip("\n'")
            except GRASSInterface.GRASSCommandException, e:
                # none
                pass
            resources.append(('region',r,r_mapset))
        for pf in popmod_files:
            fn = None
            if os.path.exists(pf): fn = pf
            resources.append(('popmod',pf,fn))
        for cf in all_coda_files:
            fn = self.find_file(cf)
            resources.append(('coda',cf,fn))
        return resources

    def get_map_resources(self):
        """ Aggregate all the maps that this model depends on.
        Returns a list of 2-tuples, the first part being the name
        of the map as specified in the model definition, and the second
        containing the mapset it exists in (or None if the map can't be found)
        """
        maps = []
        # get background maps for each region (...now in config file)
        #regions = [r.get_name() for r in self.get_regions().values() if r.get_name() is not None]
        # get parameters that are maps

        # in lifestages
        ls_ids = self.get_lifestage_ids()
        for ls_id in ls_ids:
            ls = self.get_lifestage(ls_id)
            maps.extend(ls.get_map_resources(self))
        # in management strategies
        for ms in self.get_management_strategies():
            maps.extend(ms.get_map_resources())
        return list(set(maps)) # get rid of any duplicates
    
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

    def log_instance_times(self):
        self.log.info("Average time to run replicates for each instance:")
        for i in self.get_instances():
            if i.enabled:
                self.log.info("%s: %s" % (str(i), str(i.get_average_time())))
        
    def is_complete(self):
        for i in self.get_instances():
            if i.enabled and not i.is_complete():
                return False
        return True
    
    def null_bitmask(self, generate=True):
        instances = self.get_instances()
        for i in instances:
            if not i.enabled:
                continue
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
            
            # check and clean deprecated instances dir
            completed_node = self.xml_model.xpath("/model/instances")
            if len(completed_node) > 0:
                if "baseDir" in completed_node[0].attrib.keys():
                    del completed_node[0].attrib["baseDir"]
                    self.log.warning("Removed deprecated baseDir attribute")

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
                else:
                    for i in range(0, num_perms):
                        node = self.get_completed_node(r_id,p["var_keys"],p["var"][i])
                        # NOTE instance will parse management strategy out of var_keys
                        self.instances.append( \
                           DispersalInstance(node,self,r_id,p["var_keys"],p["var"][i]))
            
            for instance in self.instances:
                instance.listeners.extend(self.listeners)
        return self.instances
    
    def get_incomplete_instances(self):
        return [i for i in self.get_instances() if not i.is_complete()]

    def get_initial_maps(self):
        initial_maps = {}
        for ls_key in self.get_lifestage_ids():
            ls = self.get_lifestage(ls_key)
            initial_maps[ls_id] = ls.initial_maps
        return initial_maps
                
    def check_model(self):
        self.log.debug("Checking model maps exist")
        
        # - can check maps just by attempting to get the map
        # - functions create GrassMap's automatically and
        # checks the map exists
        
        empty_region = False
        #check background map
        for r_id, region in self.get_regions().items():
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
        
        #self.grass_i.check_map(self.model.getBackgroundMap())
        return True
    
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

    def get_location(self):
        nodes = self.xml_model.xpath('/model/GISLocation')
        if len(nodes) == 0:
            return None
        return nodes[0].text.strip()

    def remove_location(self):
        nodes = self.xml_model.xpath('/model/GISLocation')
        assert len(nodes) == 1
        model_node = self.xml_model.getroot()
        model_node.remove(nodes[0])
        
    def infer_location(self):
        """ Older model format didn't include GIS location name.

        This method is to try to infer the location from the path. But obviously
        won't work unless the model has actually been added to the in-GRASS repository.
        """
        if not self.model_file or not os.path.isfile(self.model_file):
            return None
        the_dir = os.path.dirname(self.model_file)
        if not os.path.isdir(os.path.join(the_dir, "../../PERMANENT")):
            return None
        # this long expression returns the location part of the path
        return os.path.split(os.path.normpath(os.path.join(the_dir, "../..")))[1]

    def set_location(self, loc):
        nodes = self.xml_model.xpath('/model/GISLocation')
        if len(nodes) == 0:
            n = lxml.etree.Element('GISLocation')
            n.text = loc
            nodes = self.xml_model.xpath('/model/random')
            nodes[0].addnext(n)
        else:
            nodes[0].text = loc
        
    def find_file(self,fn):
        # Check for absolute path
        if os.path.exists(fn):
            return fn
        # Check for file in instances dir first...
        i_dir = self.base_dir
        if i_dir:
            fn2 = os.path.join(i_dir, fn)
            if os.path.exists(fn2):
                return fn2
        # Check relative to model file
        fn2 = os.path.join(os.path.dirname(self.model_file), fn)
        if os.path.exists(fn2):
            return os.path.normpath(fn2)
        return None
        
    def get_popmod_files(self):
        nodes = self.xml_model.xpath('/model/lifestages/transition/popMod')
        files = []
        missing = []
        for i in nodes:
            fn = i.attrib['file']
            fn2 = self.find_file(fn)
            if fn2 is None:
                missing.append(fn)
            files.append(fn2)
        if len(missing) > 0:
            errstr = "Can't find files" + str(missing)
            self.log.error(errstr)
            raise MissingFileException("Can't find popmod files",files=missing)
        return files

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
        value[0].text = str(max_r)
        
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

    def remove_duplicates(self, list_of_lists):
        filtered = [tuple(x) for x in list_of_lists]
        list_of_lists = list(set(filtered))
        return [list(x) for x in list_of_lists]
    
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
            p_r["var"] = self.remove_duplicates(p_r["var"])
                
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
            # If there are variables with None as their value, replace this with
            # NoneType so that matching works correctly
            for i in range(0,len(variable_list)):
                if variable_list[i] == "None":
                    variable_list[i] = None

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
                err_str = "Completed instance doesn't match any expected instances"
                self.log.error(err_str)
                raise Exception(err_str)
            
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
                elif node.tag=='novalue':
                    var_values[i].append(None)
                elif node.tag=='range':
                    j=int(node.attrib['start'])
                    k=int(node.attrib['end'])
                    step=int(node.attrib['step'])
                    var_values[i].extend([str(x) for x in range(j,k+1,step)])
                elif node.tag=='map':
                    var_values[i].append(node.text.strip())
        return var_values

    def get_variable_maps(self):
        var_maps={}
        param_variables=self.xml_model.xpath("//lifestage/event/param/variable")
        for variable in param_variables:
            i = variable.attrib['id']
            var_maps[i]=[]
            for node in variable:
                if node.tag=='map':
                    var_maps[i].append(node.text.strip())
        return var_maps
                    
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
                        filename=self.grass_i.get_blank_map())
        return maps
    
    def get_lifestage_ids(self):
        if not self.ls_ids:
            self.ls_ids = []
            nodes = self.xml_model.xpath('/model/lifestages/lifestage')
            for node in nodes:
                self.ls_ids.append(node.attrib["name"])
        return self.ls_ids
        
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

    def get_map_dependencies(self, just_permanent=False):
        """ Return all maps referenced by model, and whether they exist in the
        mapset search path.

        @param just_permanent indicates that only the PERMANENT mapset should
        be searched (which is useful before a model is in the repository)

        @returns dictionary of map names with value as what they are used for.
        """
        # TODO implement get_map_dependencies
        return {}
        pass

        
    def get_lifestage_transitions(self):
        if self.lifestage_transitions is None:
            self.lifestage_transitions = []
            popmod_xml_files = self.get_popmod_files()
            for popmod_xml in popmod_xml_files:
                self.lifestage_transitions.append( \
                    LifestageTransition(popmod_xml, self))
        return self.lifestage_transitions

    def get_period(self):
        start_time = int(self.xml_model.xpath(
                    '/model/period/startTime/text()')[0])
        end_time = int(self.xml_model.xpath(
                    '/model/period/endTime/text()')[0])
        
        return (start_time, end_time)
    
    def update_occupancy_envelope(self, ls=None, time=None, force=False):
        instances = self.get_instances()
        
        if ls is None:
            ls = self.get_lifestage_ids()
        
        for i in [x for x in instances if x.enabled]:
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
        for i in [x for x in self.get_instances() if x.enabled]:
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
        # This breaks pretty printing
        #replicate_node.text = "\n"
        
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
        mdig_config = MDiGConfig.get_config()
        
        model_node=self.xml_model.getroot()
        
        completed_node=model_node.find('instances')
        if completed_node is None:
            completed_node = lxml.etree.SubElement(model_node,"instances")
        
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
        completed_node.attrib["mapset"] = self.create_instance_mapset_name()
            
        self.log.debug('Added "completed" node: ' + repr(completed_node))
    
        return completed_node   
    
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

    def get_management_strategy(self, name):
        s = self.get_management_strategies()
        for x in s:
            if x.get_name() == name:
                return x
        return None
        
    def get_management_strategies(self):
        if self.strategies is None:
            self.strategies = []
            # Load each strategy
            s_nodes = self.xml_model.xpath('/model/management/strategy')
            if len(s_nodes) == 0:
                return self.strategies
            for s_node in s_nodes:
                # Create strategy unassigned to any instance
                m = ManagementStrategy(s_node,self)
                self.strategies.append(m)
        return self.strategies

    def init_mapset(self):
        g = self.grass_i
        loc = self.get_location()
        if loc:
            self.log.warning("Location %s in model definition for '%s' but should have been removed on addition to the db." % (loc,self.get_name()))
        loc = self.infer_location()
        if not g.check_location(loc):
            self.log.error("Location %s in model definition does not exist" % loc)
            return False
        g.grass_vars['LOCATION_NAME'] = loc
        g.set_gis_env()
        result = False
        if g.check_mapset(self.get_name(),location=loc):
            result=g.change_mapset(self.get_name(),location=loc)
        else:
            self.log.info("Mapset " +self.get_name() + \
                    " doesn't exist, creating it.")
            result=g.change_mapset(self.get_name(),location=loc,create=True)
        return result

    def get_instance_index(self, i):
        """ Return the index of the passed instance """
        return self.get_instances().index(i)

    def get_mapset(self):
        """ Get the mapset where this model's maps are contained.

            Currently is the same as the model name. Not sure whether to change
            this?
        """
        return self.get_name()

    def get_mapsets(self, include_root=True):
        """ Return all the mapsets that instances refer to.
        @param include_root defines whether to include the root model mapset or
        whether the method only returns instance mapsets.
        """
        root = self.get_mapset()
        mapsets = [i.get_mapset() for i in self.get_instances() if i != root]
        return mapsets

    def move_mapset(self, new_mapset):
        """
        Moves all Grass related files to another mapset. Files that have mapset given
        using map@mapset notation are not moved, but others are.
        """
        G = self.grass_i

        if G.check_mapset(new_mapset):
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
                    x_info=G.get_map_info(x.filename)
                    components[x_info["type"]].append((x_info["name"],x_info["mapset"]))

        self.log.debug("Processing region files for copying")
        # Add region files and background maps if they exist
        for r in self.get_regions():
            # Regions
            r_name = self.get_regions()[r].get_name()
            if r_name and G.no_mapset_component(r_name):
                r_info = G.get_map_info(r_name)
                components["region"].append((r_info["name"],r_info["mapset"]))

            # Background maps
            b_map = self.get_regions()[r].getBackgroundMap()
            add_map_to_move(b_map)         

            #if not bmap.temporary:
            #   if G.no_mapset_component(b_map.filename):
            #       b_info=G.get_map_info(bmap.filename)
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
                            r_info=G.get_map_info(r_map)
                            components[r_info["type"]].append((r_info["name"],r_info["mapset"]))
                            
            # Envelopes
            prob_env = i.get_occupancy_envelopes()
            if prob_env:
                for ls_id in self.get_lifestage_ids():
                    for t in prob_env[ls_id]:
                        e_map=prob_env[ls_id][t]
                        if G.no_mapset_component(e_map):
                            e_info=G.get_map_info(e_map)
                            components[e_info["type"]].append((e_info["name"],e_info["mapset"]))
        ## Copy all maps ##
        self.log.debug("%d region to copy" % len(components["region"]))
        self.log.debug("%d raster maps to copy" % len(components["raster"]))
        self.log.debug("%d vector maps to copy" % len(components["vector"]))
        
        # Change into new mapset
        G.change_mapset(new_mapset, create=True)

        # Copy regions
        for r in components["region"]:
            r_map, r_mapset = r
            G.run_command('g.copy region=%s@%s,%s' % (r_map, r_mapset, r_map), logging.DEBUG)

        # Copy rasters
        for r in components["raster"]:
            r_map, r_mapset = r
            G.run_command('g.copy rast=%s@%s,%s' % (r_map, r_mapset, r_map), logging.DEBUG)

        # Copy vectors
        for v in components["vector"]:
            v_map, v_mapset = v
            G.run_command('g.copy vect=%s@%s,%s' % (r_map, r_mapset, r_map), logging.DEBUG)

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
                G.change_mapset(r_mapset)
                current_mapset = r_mapset
            G.run_command('g.remove region=%s' % r_map, logging.DEBUG)

        # Del rasters
        for r in components["raster"]:
            r_map, r_mapset = r
            if r_mapset != current_mapset:
                G.change_mapset(r_mapset)
                current_mapset = r_mapset
            G.run_command('g.remove rast=%s' % r_map, logging.DEBUG)

        # Del vectors
        for v in components["vector"]:
            v_map, v_mapset = v
            if v_mapset != current_mapset:
                G.change_mapset(v_mapset)
                current_mapset = v_mapset
            G.run_command('g.remove vect=%s' % r_map, logging.DEBUG)

        # Change into new mapset again
        G.change_mapset(new_mapset)

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

	# remove the log handler
	self.remove_log_handler()

    def _indent_xml(self, elem, level=0):
        """ in-place prettyprint formatter - used because lxml one
            is picky about existing whitespace.
        """
        i = "\n" + level*"  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                indent(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
            
    def save_model(self, filename=None):
        if filename is None: filename = self.model_file
        try:
            if os.path.isfile(filename):
		 if self.backup_filename is None:
	             self.backup_filename = self.backup_file(filename)
		 else:
	             self.backup_file(filename,self.backup_filename)
            fo = open(filename,'w')
#print >>fo, self._indent_xml(self.xml_model)
            print >>fo, lxml.etree.tostring(self.xml_model,pretty_print=True)
            fo.close()
            self.model_file = filename
        except OSError, e:
            self.log.error("Couldn't save updated version of model file")
            self.log.error(e)

    def backup_file(self, filename, backup_filename=None):
	""" Backup filename and return the name of the backup file """
	if backup_filename is None:
	    count = 0
	    fn = filename + "." + repr(count)
	    # If model filename exists then try rotate the backups
	    # (keeps 4 backups by default, but original is preserved 
	    # from the initial add to repository) 
	    while os.path.isfile(fn) and count < 5:
		# count files
		count += 1
		fn = filename + "." + repr(count)
	    count -= 1
	    if count == 4:
		fn = filename + "." + repr(count)
		os.remove(fn)
	    while count > 0:
		# rotate files
		fn = filename + "." + repr(count)
		os.remove(fn)
		count -= 1
		shutil.move(filename + "." + repr(count), fn)
	    backup_filename = filename + ".0"
	shutil.move(filename, backup_filename)
	return backup_filename
            
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
