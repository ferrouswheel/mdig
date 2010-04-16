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

Copyright 2006, Joel Pitt

"""

import logging
import shutil
import re
import os
import time
import pdb
import string

import lxml

from Replicate import Replicate
from AnalysisCommand import AnalysisCommand
import GRASSInterface
import MDiGConfig

class DispersalInstance:
    """ A DispersalInstance is a realisation of a combination of variables
        for a particular region, time period, and initial conditions.
    """
    
    def __init__(self, node, exp, r_id, _var_keys, p_inst):
        self.log = logging.getLogger("mdig.instance")
        self.node = node
        self.experiment = exp
        self.r_id = r_id

        # Indicates whether actions should be applied to this instance
        # or whether it should be skipped.
        self.enabled = True
        if "enabled" in self.node.attrib and \
            string.lower(self.node.attrib["enabled"]) == "false":
            self.enabled = False
        
        # These could be null if no variables defined in experiment
        self.variables = None
        self.var_keys = None
        if p_inst:
            self.variables = list(p_inst)
            self.var_keys = list(_var_keys)
        
        self.listeners = []
        self.replicates = []
        
        # Control strategy that this instance is associated with, if any
        self.strategy = None
        # extract management strategy from variables
        if self.var_keys and "__management_strategy" == self.var_keys[0]:
            self.strategy = self.variables[0]
            del self.var_keys[0]
            del self.variables[0]

        self.replicates = self._load_replicates()
        self.activeReps = []
        
        self.log.debug("New instance - varkeys: %s vars: %s reps (complete/incomplete/missing): %d/%d/%d" % \
            (self.var_keys,self.variables, \
            len([x for x in self.replicates if x.complete]), \
            len([x for x in self.replicates if not x.complete]), \
            self.experiment.get_num_replicates()-len(self.replicates)) )
        self.log.debug("Management strategy for instance is %s" % self.strategy)

    def _load_replicates(self):
        c = self.experiment.get_completed_permutations()
        # c is a list of dicts with each dict being a completed replicate
        
        reps=[]
        r_index=0
        # If region is among the regions with completed replicates
        for c_i in c:
            if self.r_id == c_i["region"]:
                if self.strategy is None:
                    if "strategy" in c_i:
                        continue
                else:
                    if "strategy" in c_i and self.strategy != c_i["strategy"]:
                        # make sure the management strategy matches
                        continue
                    if "strategy" not in c_i:
                        continue
                if self.var_keys is None:
                    for r in c_i["reps"]:
                        my_rep = Replicate(r,self,r_index)
                        reps.append(my_rep)
                        r_index += 1
#print "rep " + repr(self.variables) + " st " + repr(self.strategy) + " matches c_i " + repr(c_i)
                else:
                    variable_list=[]
                    for k in self.var_keys:
                        variable_list.extend(([cvar for c_varid, cvar in c_i["variables"] if c_varid == k]))
                    # If there are variables with None as their value, replace this with
                    # NoneType so that matching works correctly
                    for i in range(0,len(variable_list)):
                        if variable_list[i] == "None":
                            variable_list[i] = None

                    if self.variables == variable_list:
                        for r in c_i["reps"]:
                            self.log.debug("loading replicate with variables " + str(self.variables))
                            my_rep = Replicate(r,self,r_index)
                            reps.append(my_rep)
                            r_index += 1
                            #self.log.debug("rep " + repr(self.variables) + \
                                    #" st " + repr(self.strategy) + " matches c_i " + repr(c_i))
        return reps

    def run(self):
        # Process replicates that exist but are incomplete
        for rep in [x for x in self.replicates if not x.complete]:
            self._run_replicate(rep)
    
        # Create and process replicates that are missing
        while len(self.replicates) < self.experiment.get_num_replicates():
            rep = Replicate(None,self)
            self.replicates.append(rep)
            self._run_replicate(rep)

    def _run_replicate(self, rep):
        """
        Run a singular replicate.
        """
        #try:
        rep.run()
        #except Exception, e:
        #   self.log.error(repr(e))
        #   pdb.set_trace()

    def run_command_on_replicates(self, cmd_string, ls=None, times=None):
        """ run_command_on_replicates runs a command across all
        replicate maps in times

        @param cmd_string is the command to run, with %0 for current map,
        %1 for previous saved map, etc.
        @param ls_id is a list of lifestages to run command on
        @param times is a list of times to run command on, -ve values are interpreted
        as indices from the end of the array e.g. -1 == last map.
        """
        if ls is None:
            ls = self.experiment.get_lifestage_ids().keys()
        elif not isinstance(ls, list):
            ls = [ls]

        self.set_region()
        if not self.is_complete():
            self.log.warning("Instance [%s] is incomplete, but will " +
                    "continue anyway" % i)
            
        ac = AnalysisCommand(cmd_string)
        for r in self.replicates:
            for ls_id in ls:
                saved_maps = r.get_saved_maps(ls_id)
                r_times = [ int(t) for t in saved_maps.keys() ]
                ac.init_output_file(self, r)
                ac.set_times(self.experiment.get_period(),times,r_times)
                ac.run_command(saved_maps)
                
                if MDiGConfig.get_config().analysis_add_to_xml:
                    # add the analysis result to xml filename
                    # under instance...
                    r.add_analysis_result(ls_id, ac)

    def run_command_on_occupancy_envelopes(self, cmd_string, ls=None,
            times=None):
        """ run_command_on_occupancy_envelopes runs a command across all
        occupancy envelopes replicate maps in times, or all envelopes.
        
        @param cmd_string is the command to run, with %0 for current map,
        %1 for previous saved map, etc.
        @param ls_id is a list of lifestages to run command on
        @param times is a list of times to run command on, -ve values are interpreted
        as indices from the end of the array e.g. -1 == last map.
        """
        if ls is None:
            ls = self.experiment.get_lifestage_ids().keys()
        elif not isinstance(ls, list):
            ls = [ls]
        
        if not self.is_complete():
            self.log.error("Incomplete instance [%s]" % i)
            raise ImcompleteInstanceException()

        ac = AnalysisCommand(cmd_string)
        self.set_region()
        envelopes = self.get_occupancy_envelopes()
        for ls_id in ls:
            e_times = [ int(t) for t in envelopes[ls_id].keys() ]
            ac.init_output_file(self)
            ac.set_times(self.experiment.get_period(),times,e_times)
            ac.run_command(envelopes[ls_id])

            if mdig_config.analysis_add_to_xml:
                # add the analysis result to xml filename
                # under instance...
                self.add_analysis_result(ls_id, ac) #TODO(cmd_string, tmp_fn))
        
    def null_bitmask(self, generate=True):
        for r in self.replicates:
            r.null_bitmask(generate)
    
    def stop(self):
        
        for ar in self.activeReps:
            self.remove_active_rep(ar)
            ar.clean_up()
            self.remove_rep(ar)
    
    def add_listener(self,listener):
        self.listeners.append(listener)
        
    def remove_listener(self,listener):
        self.listeners.remove(listener)
    
    def get_var(self,id):
        if id in self.var_keys:
            return self.variables[self.var_keys.index(id)]
        else:
            return None
        
    def clean_up(self):
        for r in self.replicates:
            r.clean_up()
    
    def pre_run(self):
        pass
    
    def is_complete(self):
        a = len([x for x in self.replicates if x.complete]) >= self.experiment.get_num_replicates() \
            and len(self.activeReps) == 0
        return a
    
    def set_replicates(self, reps):
        self.replicates = reps
    
    def remove_rep(self, rep):
        try:
            self.node.find('replicates').remove(rep.node)
        except ValueError:
            pdb.set_trace()
        self.replicates.remove(rep)
    
    def remove_active_rep(self, rep):
        self.activeReps.remove(rep)
        if len(self.activeReps) == 0:
            self.experiment.remove_active_instance(self)
    
    def add_active_rep(self, rep):
        if rep not in self.activeReps:
            self.activeReps.append(rep)
            self.experiment.add_active_instance(self)
    
    def reset(self):
        while len(self.replicates) > 0:
            self.remove_rep(self.replicates[-1])
    
    def get_occupancy_envelopes(self):
        prob_env = {}
        if not self.is_complete():
            self.log.error("Trying to obtain probability envelope for incomplete instance")
            return None
        
        ls_nodes = self.node.xpath('envelopes/lifestage')
        
        
        if len(ls_nodes) == 0:
            self.log.debug("Probability envelopes don't exist yet")
            return None
        
        for ls_node in ls_nodes:
            # For each lifestage node in envelopes
            ls_id = ls_node.attrib["id"]
            prob_env[ls_id] = {}
            for e_node in ls_node:
                if e_node.tag == "envelope":
                    time = e_node.attrib["time"]
                    map_name = e_node.text
                    prob_env[ls_id][time]=map_name

        return prob_env
                    
    def are_envelopes_fresh(self, ls, start, end, force=False):
        previous_envelopes = self.get_occupancy_envelopes()
        missing_years = {}

        envelopes_current = self.are_envelopes_newer_than_reps()
        if not envelopes_current and not force:
            self.log.warning("Envelopes are older than some replicates use -p to"
                    " regenerate.")

        # if there are no envelopes yet or we want to overwrite them 
        if force or previous_envelopes is None:
            for l in ls:
                missing_years[l] = [y for y in
                    self.experiment.map_year_generator(l, [start,end])]
            return missing_years

        for l in ls:
            interval = self.experiment.get_map_output_interval(l)
            if interval < 0:
                self.log.info("No raster output defined to create occupancy envelope"
                        " for lifestage " + l)
                return None

            missing_years[l] = []
            for t in self.experiment.map_year_generator(l, [start,end]):
                # is map in the model xml?
                if str(t) not in previous_envelopes[l]: 
                    # no, then add year
                    missing_years[l].append(t)
                else:
                    # yes... then check if map exists
                    if GRASSInterface.get_g().check_map(previous_envelopes[l][str(t)]) is None:
                        missing_years[l].append(t)
        return missing_years

    def are_envelopes_newer_than_reps(self):
        for i in self.replicates:
            if i.get_time_stamp() > self.get_envelopes_timestamp():
                return False
        return True

    def get_envelopes_timestamp(self):
        es = self.node.xpath('envelopes')
        if es:
            return float(es[0].attrib['ts'])
        return 0

    def add_analysis_result(self,ls_id,analysis_cmd):
        """
        Result is a tuple with (command executed, filename of output)
        """
        result = (analysis_cmd.cmd_string,analysis_cmd.output_fn)
        
        mdig_config = MDiGConfig.get_config()
        
        current_dir = os.path.dirname(os.path.abspath(result[1]))
        filename = os.path.basename(result[1])
        analysis_dir_abs_path = os.path.abspath(os.path.join(
                    self.experiement.base_dir,mdig_config.analysis_dir))
        
        # move filename to analysis directory
        if current_dir is not analysis_dir_abs_path:
            # if file exists and overwrite_flag is specified then overwrite
            if os.path.isfile( os.path.join(analysis_dir_abs_path,filename) ):
                if mdig_config.overwrite_flag:
                    os.remove( os.path.join(analysis_dir_abs_path,filename) )
                else:
                    self.log.error( "Can't add analysis because filename %s already exists and "\
                     "overwrite_flag is not set." % filename)
                    return
            shutil.move(result[1], analysis_dir_abs_path)
        
        filename = os.path.basename(filename)
        
        envelopes = self.node.find('envelopes')
        if envelopes is None:
            envelopes = lxml.etree.SubElement(self.node,'envelopes')
            
        all_ls = envelopes.xpath("lifestage")
        
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
        
    def set_region(self):
        current_region = self.experiment.get_region(self.r_id)
        try:
            GRASSInterface.get_g().set_region(current_region)
        except GRASSInterface.SetRegionException, e:
            pdb.set_trace()
            return
    
    def update_occupancy_envelope(self, ls, start, end, force=False):
        # Set the region in case it hasn't been yet
        self.set_region()
                
        self.log.debug("Checking whether envelopes are fresh...")
        missing_envelopes = self.are_envelopes_fresh(ls, start, end,
                force=force)
        if not missing_envelopes or not self.is_complete(): return
        
        for l in ls:
            maps = []
            for r in self.replicates:
                saved_maps = r.get_saved_maps(l)
                if saved_maps:
                    maps.append(saved_maps)
                else:
                    self.log.warning("Replicate has no maps available")
                #pdb.set_trace()
            
            for t in missing_envelopes[l]: #range(start,end):
                #print("making envelope for time %d" % t)
                #pdb.set_trace()

                maps_to_combine = []
                for r in maps:
                    if str(t) in r:
                        maps_to_combine.append(r[str(t)])
                    else:
                        self.log.warning("Missing map for time=" + str(t))
                    
                filename = self.experiment.get_name() + "_region_" + self.r_id
                if self.strategy is not None:
                    filename += "_strategy_" + self.strategy
                if self.var_keys is not None:
                    for v in self.var_keys:
                        filename += "_" + v + "_"
                        var_value=self.variables[self.var_keys.index(v)]
                        if isinstance(var_value,str):
                            filename += var_value
                        else:
                            filename += repr(var_value)
                filename += "_ls_" + l + "_" + repr(t) + "_prob"
                prob_env = GRASSInterface.get_g().occupancy_envelope(maps_to_combine,filename)
                if prob_env is not None:
                    self._add_envelope(prob_env,l,t)
                    
    def _add_envelope(self, env_name, lifestage_id, t):
        # Add envelope to completed/envelopes/lifestage[id=l]/envelope[t=t]
        es = self.node.find('envelopes')
        if es is None:
            es = lxml.etree.SubElement(self.node,'envelopes')
        es.attrib['ts'] = repr(time.time())
            
        ls = es.xpath('lifestage[@id="%s"]' % lifestage_id)
        
        if len(ls) == 0:
            ls = lxml.etree.SubElement(es,'lifestage')
            ls.attrib["id"] = lifestage_id
            ls.text = '\n'
        else:
            ls = ls[0]
            
        env = es.xpath('envelope[@time="%d"]' % t)
        if len(env) == 0:
            
            env = lxml.etree.SubElement(ls,'envelope')
            env.attrib["time"] = repr(t)
            
        env.text = env_name
    
    def update_xml(self):
        # everything else is updated as they are accessed through class methods
        if not self.enabled:
            self.node.attrib["enabled"] = "false"

    def __str__(self):
        s = "[DispersalInstance] "
        if not self.enabled:
            s += "*DISABLED* \n"
        else:
            s += "\n"
        if self.strategy is not None:
            s += "  Strategy: " + self.strategy + "; \n"
        s += "  Parameters: \n"
        for vv in zip(self.var_keys, self.variables):
             s += "    " + str(vv) + "\n"
        s += "  Region ID: " + self.r_id + "; \n"
        s += "  Replicates: " + str(len([x for x in self.replicates if x.complete])) \
              + "/" + str(self.experiment.get_num_replicates())
        if len(self.activeReps) > 0:
            s += " [Active: " + str(self.activeReps) + "]"
        else:
            s += " [Active: None] "
#s+= " (complete/total [active]) "
        return s

class ImcompleteInstanceException(Exception): pass

