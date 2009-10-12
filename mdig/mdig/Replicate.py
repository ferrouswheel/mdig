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
Replicate module. Part of MDiG - Modular Dispersal in GIS
"""

import lxml.etree
import random
import logging
import shutil
import string
import os
import time
import pdb

import GRASSInterface 
import MDiGConfig
import OutputFormats
from GrassMap import MapMissingException
from GRASSInterface import SetRegionException
import DispersalModel

class Replicate:
    """
    Replicate is a class for each replication simulated for an DispersalInstance

    @todo: load/store and use previous maps. getprevious_map doesn't work as
    intended.
    """

    def __init__(self,node,instance,r_index=0):
        self.instance = instance
        self.log = logging.getLogger("mdig.replicate")
        
        self.grass_i = GRASSInterface.getG()
        
        self.temp_map_names={}
        self.active = False
        self.current_t = -1
        self.initial_maps = {}
        self.previous_maps = None
        self.saved_maps = None
        self.map_intervals = None
        # used to keep track of index in replicates while loading:
        self.r_index = r_index

        if node is None:
            self.node = self.instance.experiment.add_replicate(self.instance.node)
            self.complete = False
            self.set_seed(self.instance.experiment.next_random_value())
        else:
            # if node is provided then create replicate node from xml
            self.node = node
            c = MDiGConfig.getConfig()
            if "replicate" not in c or \
                "check_complete" not in c["replicate"] or \
                c["replicate"]["check_complete"] != "no":
                self.complete = self.check_complete()
            else:
                # If the mdig.conf file has turned off check
                # then we just assume the replicate is complete
                self.complete = True

        self.random = random.Random()
        self.random.seed(self.get_seed())
        
    def check_complete(self):
        complete = True
        missing_maps = {}
        total_reps = self.instance.experiment.get_num_replicates()
        self.log.debug("Checking replicate %d/%d is complete" % \
            (self.r_index,total_reps)) 
        ls_keys = self.instance.experiment.get_lifestage_ids()
        for ls_key in ls_keys:
            try:
                self.get_saved_maps(ls_key)
            except MapMissingException, e:
                missing_maps[ls_key]=e.missing_maps
                complete=False
                self.log.warning("Maps missing from replicate %s", repr(missing_maps[ls_key]))

        # If all maps listed in xml are present, then check there is one for
        # every year that is expected to have map output
        if complete:
            exp = self.instance.experiment
            period = exp.get_period()
            for ls_key in ls_keys:
                maps = self.get_saved_maps(ls_key)
                for t in exp.map_year_generator(ls_key):
                    if maps is None:
                        complete = False
                        break
                    elif str(t) not in maps:
                        complete = False
                        break
        return complete
            
        
    def _load_saved_maps(self):
        self.saved_maps = {}
        self.map_intervals = {}
        missing_maps=[]
        ls_keys = self.instance.experiment.get_lifestage_ids()
        for ls_key in ls_keys:
            self.map_intervals[ls_key] = 0 # If no maps node exist then interval is 0
            ls_maps_node = self.node.xpath('lifestage[@id="%s"]/maps' % ls_key)
            
            if len(ls_maps_node) == 1:
                self.saved_maps[ls_key] = {}
                if "interval" in ls_maps_node[0].attrib:
                    self.map_intervals[ls_key] = int(ls_maps_node.attrib["interval"])
                else: self.map_intervals[ls_key] = 1

                for m in ls_maps_node[0]:
                    if m.tag == "map":
                        time_step=m.attrib["time"]
                        if not GRASSInterface.getG().checkMap(m.text):
                            missing_maps.append(m.text)
                        else:
                            self.saved_maps[ls_key][time_step] = m.text
            elif len(ls_maps_node) > 1:
                raise DispersalModel.InvalidXMLException, "More than one maps node"

        if missing_maps:
            raise MapMissingException(missing_maps)
    
    def get_saved_maps(self, ls_id):
        """
        Get maps that are generated by rasterOutput and saved in XML
        """
        if self.saved_maps is None:
            try:
                self._load_saved_maps()
            except MapMissingException, e:
                raise
        
        if ls_id in self.saved_maps:
            return self.saved_maps[ls_id]
        else: return None
        
    def null_bitmask(self, generate_null=True):
        """ Create null bitmasks for raster maps"""
        ls_keys = self.instance.experiment.get_lifestage_ids()
        for ls_key in ls_keys:
            maps=self.get_saved_maps(ls_key)
            for m in maps.values():
                GRASSInterface.getG().null_bitmask(m,generate=generate_null)
    
    def set_seed(self,s):
        seed_node=lxml.etree.SubElement(self.node,'seed')
        seed_node.text = repr(s)
        self.seed = s
        
    def get_seed(self):
        if "node" not in dir(self): pdb.set_trace()
        seed_node=self.node.find('seed')
        return int(seed_node.text)
    
    def get_previous_maps(self,ls_id):
        """ Return map names
        
        for lifestage with id ls_id
        
        """
        if self.previous_maps == None:
            self.previous_maps = {}
            ls_keys = self.instance.experiment.get_lifestage_ids()
            for ls_key in ls_keys:
                self.previous_maps[ls_key] = []
        
        maps = self.previous_maps[ls_id]
        return maps
        
    def get_previous_map(self,ls_id,offset=1):
        maps = self.get_previous_maps(ls_id)
        if offset <= len(maps):
            return maps[-offset]
        else:
            return None
    
    def push_previous_map(self,ls_id,map_name):
        maps = self.get_previous_maps(ls_id)
        maps.append(map_name)
        
    def getInitialMap(self,ls_id):
        return self.initial_maps[ls_id]
    
    def reset(self):
        # Map are removed/overwritten automatically
        self.node.getparent().remove(self.node)
        del self.node
        self.node = self.instance.experiment.add_replicate(self.instance.node)
        self.complete = False
        self.set_seed(self.instance.experiment.next_random_value())

    def record_maps(self, remove_null=False):
        for ls_id in self.instance.experiment.get_lifestage_ids():
            self.push_previous_map(ls_id,GRASSInterface.getG().generateMapName(ls_id))
            #if first_year:
                #self.grass_i.copyMap(self.initial_maps[ls_id].getMapFilename(),self.get_previous_map(ls_id),True)
            #else:
            self.grass_i.copyMap(self.temp_map_names[ls_id][0],self.get_previous_map(ls_id),True)
            if remove_null:
                self.grass_i.null_bitmask(self.get_previous_map(ls_id),generate=False)

    def run(self,remove_null=False):
        self.reset()
        self.active = True
        self.instance.add_active_rep(self)
        
        exp = self.instance.experiment
        
        self.log.log(logging.INFO, "Replicate %d/%d of exp. instance [var_keys: %s, vars: %s ]"\
                     % (self.instance.replicates.index(self) + 1, exp.get_num_replicates(),\
                        repr(self.instance.var_keys),repr(self.instance.variables)))
        self.log.log(logging.INFO, "Management strategy is %s" % self.instance.strategy)
        
        self.instance.set_region()
        
        # Get the initial distribution maps for the region
        self.initial_maps = exp.get_initial_maps(self.instance.r_id)
        initial_maps = self.initial_maps

        ls_keys = exp.get_lifestage_ids()
        
        for ls_key in ls_keys:
            # Create temporary map names
            # - input is in [0], output in [1]
            self.temp_map_names[ls_key] = [
                GRASSInterface.getG().generateMapName(ls_key),
                GRASSInterface.getG().generateMapName(ls_key)
            ]
            
            # copy initial map to temporary source map, overwrite if necessary
            self.grass_i.copyMap( \
                    initial_maps[ls_key].getMapFilename(), \
                    self.temp_map_names[ls_key][0],True)
            
            # Set up phenology maps (LS initialises them on init)
            ls = exp.get_lifestage(ls_key)
            # Set up lifestage analysis
            for a in ls.analyses():
                a.pre_run(self)
        
        # If in debug mode print out the names of the initial maps
        if self.log.getEffectiveLevel() <= logging.DEBUG:
            str_maps=''
            for m in initial_maps.values():
                str_maps += ' ' + m.getMapFilename()
            self.log.debug("Initial maps: " + str_maps)
        
        period = exp.get_period()
        self.log.debug("Simulation period is " + str(period))

        strategy = exp.get_management_strategy(self.instance.strategy)
        # TODO strategies should be pre initialised with instances
        if strategy is not None:
            strategy.set_instance(self.instance)
        
        for t in range(period[0],period[1]+1):
            self.current_t = t
            self.log.log(logging.INFO, "t=%d", t)

            # keep a record of previous maps by saving to a non-temporary name
            self.record_maps(remove_null)

            # invoke lifestage transitions
            ls_trans = self.instance.experiment.get_lifestage_transition()
            if ls_trans:
                # build lists of source/dest maps
                source_maps = []
                dest_maps = []
                for ls_id in ls_keys:
                    source_maps.append(self.temp_map_names[ls_id][0])
                    dest_maps.append(self.temp_map_names[ls_id][1])
                # Lifestage transition should automatically swap source/dest
                # maps
                self.log.debug("Applying lifestage transition matrix" + str(period))
                ls_trans.apply_transition(source_maps,dest_maps)
                # clean up the source/dest maps so that source=dest and
                # dest=source
                for ls_id in ls_keys:
                    self.temp_map_names[ls_id].reverse()
            
            phenology_iterator = exp.phenology_iterator(self.instance.r_id)
            
            # Run through phenology intervals
            for current_interval, p_lifestages in phenology_iterator:
                for lifestage in p_lifestages:
                    ls_key = lifestage.name
                    self.log.log(logging.INFO, 'Interval %d - Lifestage "%s"' \
                            ' started',current_interval,ls_key)
                    lifestage.run(current_interval,self,self.temp_map_names[ls_key],strategy)
                    print self.temp_map_names
                self.log.log(logging.INFO, 'Interval %d completed.',current_interval)

            # Run Analyses for each lifestage
            for ls_id in ls_keys:
                l = self.instance.experiment.get_lifestage(ls_id)
                analyses = l.analyses()
                self.log.log(logging.INFO, 'Lifestage %s - Running analyses',ls_id)
                for a in analyses:
                    a.run(self.temp_map_names[ls_key][0], self)
                self.log.log(logging.INFO, 'Lifestage %s - Analyses complete',ls_id)
            
            self.fire_time_completed(t)

        self.instance.remove_active_rep(self)
        self.instance.experiment.save_model()
        self.active = False
        self.current_t = -1
        self.complete = True
        self.clean_up()
    
    def add_analysis_result(self,ls_id,analysis_cmd):
        """
        Result is a tuple with (command executed, filename of output)
        """
        result = (analysis_cmd.cmd_string,analysis_cmd.output_fn)

        mdig_config = MDiGConfig.getConfig()
        
        current_dir = os.path.dirname(os.path.abspath(result[1]))
        filename = os.path.basename(result[1])
        destination_path = os.path.join(self.instance.experiment.base_dir, mdig_config.analysis_dir)
        
        # move filename to analysis directory
        if current_dir != destination_path:
            # if file exists and overwrite_flag is specified then overwrite
            if os.path.isfile( os.path.join(destination_path,filename) ):
                if mdig_config.overwrite_flag:
                    os.remove( os.path.join(destination_path,filename) )
                else:
                    self.log.error( "Can't add analysis because filename %s already exists and "\
                     "overwrite_flag is not set." % filename)
                    return
            
            shutil.move(result[1], destination_path)
        
        filename = os.path.basename(filename)
        
        all_ls = self.node.xpath("lifestage")
        
        ls_node = None
        for a_ls_node in all_ls:
            if a_ls_node.attrib["id"] == ls_id:
                ls_node = a_ls_node
                break
        
        if ls_node is None:
            ls_node = lxml.etree.SubElement(self.node,'lifestage')
            ls_node.attrib["id"] = ls_id
                
        # find analyses node
        analyses = ls_node.find('analyses')
        if analyses is None:
            analyses = lxml.etree.SubElement(ls_node,'analyses')
        
        # get analysis nodes
        all_a = analyses.xpath("analysis")
        
        a = None
        for i_a in all_a:
            # check for existing analysis command node
            if i_a.attrib["name"] == result[0]:
                # analysis already in file, update filename
                a = i_a
            # check filename isn't used in another analysis
            elif i_a.text == filename:
                self.log.warning("Removing analysis node that uses same output file")
                # Remove analysis node
        
        # add new node if it doesn't exist
        if a is None:
            a = lxml.etree.SubElement(analyses,'analysis')
            a.attrib["name"] = result[0]
            
        # set analysis node text to filename
        a.text = filename

    def clean_up(self):
        for l in self.temp_map_names.values():
            self.grass_i.removeMap(l[0])
            self.grass_i.removeMap(l[1])
        for ls_key in self.instance.experiment.get_lifestage_ids():
            prev_maps = self.get_previous_maps(ls_key)
            for m in prev_maps:
                self.grass_i.removeMap(m)
        self.previous_maps = None
                        
    def fire_time_completed(self,t):
        for l in self.instance.listeners:
            #pdb.set_trace()
            ls_filename = l.replicateUpdate(self,t)
            
            if l.__class__ == OutputFormats.RasterOutput and ls_filename[0] is not None:
                self.add_completed_raster_map(self.current_t, ls_filename[0], ls_filename[1], l.interval)
        # set time of last change
        self.update_time_stamp()
    
    def update_time_stamp(self):
        """
        Update the time stamp for when the last map
        was completed.
        """
        self.node.attrib['ts'] = repr(time.time())

    def get_time_stamp(self):
        return float(self.node.attrib['ts'])
    
    def add_completed_raster_map(self,t,ls,file_name,interval=1):
        mdig_config = MDiGConfig.getConfig()
        
        # If the command line has specified that the null bitmask
        # of completed raster maps should be removed:
        if mdig_config.remove_null:
            GRASSInterface.getG().null_bitmask(file_name,generate="False")
        
        # TODO: Check if the filename has already been associated with an analysis
        
        ls_node = self.node.xpath('lifestage[@id="%s"]' % ls)
        if len(ls_node) == 0:
            ls_node.append(lxml.etree.SubElement(self.node,'lifestage'))
            ls_node[0].attrib["id"] = ls
            ls_node[0].text = '\n'

        maps_node = ls_node[0].xpath('maps')
        if len(maps_node) == 0:
            new_maps_node = lxml.etree.SubElement(ls_node[0],'maps')
            if interval != 1:
                new_maps_node.attrib['interval']=interval
            maps_node.append(new_maps_node)
        
        correct_m = None
        for m in maps_node[0]:
            if string.atoi(m.attrib["time"]) == t:
                correct_m = m
        if correct_m is None:
            # Not found, so add:
            correct_m=lxml.etree.SubElement(maps_node[0],'map')
        
        correct_m.attrib["time"]="%d" % t
        correct_m.text = file_name

