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
import datetime

import mdig

import GRASSInterface 
import MDiGConfig
import OutputFormats
from GRASSInterface import MapNotFoundException, SetRegionException
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
        
        self.grass_i = GRASSInterface.get_g()
        
        self.temp_map_names={}
        self.active = False
        self.current_t = -1
        self.initial_maps = {}
        self.previous_maps = None
        self.saved_maps = None
        self.map_intervals = None
        # used to keep track of index in replicates while loading:
        self.r_index = r_index
        # used to calculate time taken to complete
        self.start_time = None

        if node is None:
            self.node = self.instance.experiment.add_replicate(self.instance.node)
            self.complete = False
            self.set_seed(self.instance.experiment.next_random_value())
        else:
            # if node is provided then create replicate node from xml
            self.node = node
            c = MDiGConfig.get_config()
            if "replicate" not in c or \
                "check_complete" not in c["replicate"] or \
                c["replicate"]["check_complete"] != "false":
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
            except MapNotFoundException, e:
                missing_maps[ls_key]=e.map_name
                complete=False
                self.log.warning("Maps missing from replicate, marked as " + \
                        "incomplete: %s", repr(missing_maps[ls_key]))

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
                        if not GRASSInterface.get_g().check_map(m.text,self.instance.get_mapset()):
                            missing_maps.append(m.text)
                        else:
                            self.saved_maps[ls_key][time_step] = m.text
            elif len(ls_maps_node) > 1:
                raise DispersalModel.InvalidXMLException, "More than one maps node"

        if missing_maps:
            raise MapNotFoundException(missing_maps)
    
    def get_saved_maps(self, ls_id):
        """
        Get maps that are generated by rasterOutput and saved in XML
        """
        if self.saved_maps is None:
            try:
                self._load_saved_maps()
            except MapNotFoundException, e:
                raise
        
        if ls_id in self.saved_maps:
            return self.saved_maps[ls_id]
        else: return []

    def delete_maps(self):
        """ Deletes all maps created by replicate, this currently
        DOES NOT update the xml, as it's only used by the
        DispersalInstance.remove_rep method which removes the entire replicate
        xml node.
        TODO: update xml 
        """
        g = GRASSInterface.get_g()
        for ls_id in self.instance.experiment.get_lifestage_ids():
            try:
                ls_saved_maps = self.get_saved_maps(ls_id)
            except GRASSInterface.MapNotFoundException, e:
                # If maps are missing, there still might be some found, even
                # though it's unlikely
                ls_saved_maps = self.get_saved_maps(ls_id)
            finally:
                for m in ls_saved_maps:
                    # remove map
                    g.remove_map(m,self.instance.get_mapset())
        
            ls_node = self.node.xpath('lifestage[@id="%s"]' % ls_id)
            if len(ls_node) == 0: continue

            maps_node = ls_node[0].xpath('maps')
            if len(maps_node) != 0:
                ls_node[0].remove(maps_node[0])
        
    def null_bitmask(self, generate_null=True):
        """ Create null bitmasks for raster maps"""
        ls_keys = self.instance.experiment.get_lifestage_ids()
        for ls_key in ls_keys:
            maps=self.get_saved_maps(ls_key)
            for m in maps.values():
                GRASSInterface.get_g().null_bitmask(m,generate=generate_null)
    
    def get_img_filenames(self, ls="all", extension=True, gif=False):
        """ Get a dict of time:image_filename pairs for outputting maps to.
        Warning, this doesn't check that ls is an actual lifestage.
        If gif is true, then returns a single string
        """
        output_dir = os.path.join(self.instance.experiment.base_dir,"output")
        fn = OutputFormats.create_filename(self)
        if gif:
            result = os.path.join(output_dir,fn + "_ls_" + ls + "_anim")
            if extension: result += '.gif'
        else: 
            result = {}
            env = self.get_saved_maps(ls)
            # If there are no occupancy envelopes return None
            if env is None: return None
            times = env.keys()
            times.sort(key=lambda x: float(x))
            for t in times:
                result[t] = os.path.join(output_dir, fn + "_ls_" + ls + "_" + str(t))
                if extension: result[t] += '.png'
        return result
        
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
            self.push_previous_map(ls_id,GRASSInterface.get_g().generate_map_name(ls_id))
            #if first_year:
                #self.grass_i.copy_map(self.initial_maps[ls_id].get_map_filename(),self.get_previous_map(ls_id),True)
            #else:
            self.grass_i.copy_map(self.temp_map_names[ls_id][0],self.get_previous_map(ls_id),True)
            if remove_null:
                self.grass_i.null_bitmask(self.get_previous_map(ls_id),generate=False)

    def run(self,remove_null=False):
        self.reset()
        self.active = True
        self.instance.add_active_rep(self)
        
        exp = self.instance.experiment
        
        var_dict = None
        if self.instance.var_keys:
            var_dict = dict(zip(self.instance.var_keys, self.instance.variables)) 
        rep_info_str = "Replicate %d/%d of exp. instance" % \
            (self.instance.replicates.index(self) + 1, exp.get_num_replicates())
        if var_dict:
            rep_info_str += " [vars: %s]" % repr(var_dict)
        if self.instance.strategy:
            rep_info_str += " [strategy: %s]" % self.instance.strategy
        if MDiGConfig.get_config().output_level == "normal":
            print rep_info_str
        self.log.log(logging.INFO, rep_info_str)
        
        self.instance.set_region()
        
        # Get the initial distribution maps for the region
        self.initial_maps = exp.get_initial_maps(self.instance.r_id)
        initial_maps = self.initial_maps

        ls_keys = exp.get_lifestage_ids()
        
        for ls_key in ls_keys:
            # Create temporary map names
            # - input is in [0], output in [1]
            self.temp_map_names[ls_key] = [
                GRASSInterface.get_g().generate_map_name(ls_key),
                GRASSInterface.get_g().generate_map_name(ls_key)
            ]
            
            # copy initial map to temporary source map, overwrite if necessary
            self.grass_i.copy_map( \
                    initial_maps[ls_key].get_map_filename(), \
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
                str_maps += ' ' + m.get_map_filename()
            self.log.debug("Initial maps: " + str_maps)
        
        period = exp.get_period()
        self.log.debug("Simulation period is " + str(period))

        strategy = exp.get_management_strategy(self.instance.strategy)
        # TODO strategies should be pre initialised with instances
        if strategy is not None:
            strategy.set_instance(self.instance)

        self.start_time = datetime.datetime.now()
        
        for t in range(period[0],period[1]+1):
            self.current_t = t
            self.log.log(logging.INFO, "t=%d", t)

            # keep a record of previous maps by saving to a non-temporary name
            self.record_maps(remove_null)

            # invoke lifestage transitions
            ls_trans = self.instance.experiment.get_lifestage_transitions()
            for ls_transition in ls_trans:
                # 
                # build lists of source/dest maps
                source_maps = []
                dest_maps = []
                for ls_id in ls_keys:
                    source_maps.append(self.temp_map_names[ls_id][0])
                    dest_maps.append(self.temp_map_names[ls_id][1])
                # Lifestage transition should automatically swap source/dest
                # maps
                self.log.debug("Applying lifestage transition matrix")
                ls_transition.apply_transition(ls_keys, source_maps,dest_maps)
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
                self.log.log(logging.INFO, 'Interval %d completed.',current_interval)

            # Run Analyses for each lifestage
            for ls_id in ls_keys:
                l = self.instance.experiment.get_lifestage(ls_id)
                analyses = l.analyses()
                if len(analyses) > 0:
                    self.log.info('Lifestage %s - Running analyses',ls_id)
                    for a in analyses:
                        a.run(self.temp_map_names[ls_key][0], self)
                    self.log.info('Lifestage %s - Analyses complete',ls_id)
                else:
                    self.log.debug('Lifestage %s - No analyses',ls_id)
            self.fire_time_completed(t)

        self.instance.rep_times.append(datetime.datetime.now() - self.start_time)

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

        mdig_config = MDiGConfig.get_config()
        
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
            self.grass_i.remove_map(l[0])
            self.grass_i.remove_map(l[1])
        for ls_key in self.instance.experiment.get_lifestage_ids():
            prev_maps = self.get_previous_maps(ls_key)
            for m in prev_maps:
                self.grass_i.remove_map(m)
        self.previous_maps = None
                        
    def fire_time_completed(self,t):
        for l in self.instance.listeners:
            #pdb.set_trace()
            if "replicate_update" in dir(l):
                ls_filename = l.replicate_update(self,t)
            
                if l.__class__ == OutputFormats.RasterOutput and ls_filename[0] is not None:
                    self.add_completed_raster_map(self.current_t, ls_filename[0], ls_filename[1], l.interval)
        # set time of last change
        self.update_time_stamp()
    
    def update_time_stamp(self):
        """
        Update the time stamp for when the last map
        was completed.
        """
        self.node.attrib['ts'] = datetime.datetime.now().isoformat()

    def get_time_stamp(self):
        import dateutil.parser
        # First check for old style timestamp
        try:
            ts = float(self.node.attrib['ts'])
            self.node.attrib['ts'] = datetime.datetime.fromtimestamp(ts).isoformat()
        except ValueError, e:
            pass
        ###
        return dateutil.parser.parse(self.node.attrib['ts'])
    
    def add_completed_raster_map(self,t,ls,file_name,interval=1):
        mdig_config = MDiGConfig.get_config()
        
        # If the command line has specified that the null bitmask
        # of completed raster maps should be removed:
        if mdig_config.remove_null:
            GRASSInterface.get_g().null_bitmask(file_name,generate="False")
        
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

