#!/usr/bin/env python2.4
""" 

Copyright 2006, Joel Pitt

"""

import logging
import shutil
import re
import os
import time
import pdb

import lxml

from Replicate import Replicate
import GRASSInterface
import MDiGConfig

# An Experiment Instance is a realisation of a combination of variables
class ExperimentInstance:
    
    def __init__(self, node, exp, r_id, _var_keys, p_inst):
        self.log = logging.getLogger("mdig.instance")
        self.node = node
        self.experiment = exp
        self.r_id = r_id
        
        # These could be null if no variables defined in experiment
        self.variables = p_inst
        self.var_keys = _var_keys
        
        self.listeners = []
        self.replicates = []
        
        self.replicates = self._loadReplicates()
        self.activeReps = []
        
        self.log.debug("New instance - varkeys: %s vars: %s reps (complete/incomplete/missing): %d/%d/%d" % \
            (self.var_keys,self.variables, \
            len([x for x in self.replicates if x.complete]), \
            len([x for x in self.replicates if not x.complete]), \
            self.experiment.getNumberOfReplicates()-len(self.replicates)) )

    def _loadReplicates(self):
        c = self.experiment.getCompletedPermutations()
        # c is a list of dicts with each dict being a completed replicate
        
        reps=[]
        # If region is among the regions with completed replicates
        for c_i in c:
            if self.r_id == c_i["region"]:
                if self.var_keys is None:
                    for r in c_i["reps"]:
                        my_rep = Replicate(r,self)
                        reps.append(my_rep)
                else:
                    variable_list=[]
                    for k in self.var_keys:
                        variable_list.extend(([cvar for c_varid, cvar in c_i["variables"] if c_varid == k]))

                    if self.variables == variable_list:
                        for r in c_i["reps"]:
                            my_rep = Replicate(r,self)
                            reps.append(my_rep)
        
        return reps

    def run(self):
        # Process replicates that exist but are incomplete
        for rep in [x for x in self.replicates if not x.complete]:
            self._run_replicate(rep)
    
        # Create and process replicates that are missing
        while len(self.replicates) < self.experiment.getNumberOfReplicates():
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
        
    def nullBitmask(self, generate=True):
        for r in self.replicates:
            r.nullBitmask(generate)
    
    def stop(self):
        
        for ar in self.activeReps:
            self.removeActiveRep(ar)
            ar.cleanUp()
            self.removeRep(ar)
    
    def addListener(self,listener):
        self.listeners.append(listener)
        
    def removeListerner(self,listener):
        self.listeners.remove(listener)
    
    def getVar(self,id):
        if id in self.var_keys:
            return self.variables[self.var_keys.index(id)]
        else:
            return None
        
    def cleanUp(self):
        for r in self.replicates:
            r.cleanUp()
    
    def prepareRun(self):
        pass
    
    def isComplete(self):
        a = len([x for x in self.replicates if x.complete]) >= self.experiment.getNumberOfReplicates() \
            and len(self.activeReps) == 0
        return a
    
    def setReplicates(self, reps):
        self.replicates = reps
    
    def removeRep(self, rep):
        
        self.node.find('replicates').remove(rep.node)
        self.replicates.remove(rep)
    
    def removeActiveRep(self, rep):
        self.activeReps.remove(rep)
        if len(self.activeReps) == 0:
            self.experiment.removeActiveInstance(self)
    
    def addActiveRep(self, rep):
        if rep not in self.activeReps:
            self.activeReps.append(rep)
            self.experiment.addActiveInstance(self)
    
    def reset(self):
        while len(self.replicates) > 0:
            self.removeRep(self.replicates[-1])
    
    def getProbabilityEnvelopes(self):
        prob_env = {}
        if not self.isComplete():
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
                    
    def areEnvelopesUpToDate(self, ls, start, end, force=False):
        previous_envelopes = self.getProbabilityEnvelopes()
        missing_years = {}

        envelopes_current = self.areEnvelopesNewerThanReplicates()
        if not envelopes_current and not force:
            self.log.warning("Envelopes are older than some replicates use -p to"
                    " regenerate.")

        # if there are no envelopes yet or we want to overwrite them 
        if force or previous_envelopes is None:
            for l in ls:
                missing_years[l] = [y for y in
                    self.experiment.mapYearGenerator(l, [start,end])]
            return missing_years

        for l in ls:
            interval = self.experiment.getMapOutputInterval(l)
            if interval < 0:
                self.log.info("No raster output defined to create occupancy envelope"
                        " for lifestage " + l)
                return None

            missing_years[l] = []
            for t in self.experiment.mapYearGenerator(l, [start,end]):
                # is map in the model xml?
                if str(t) not in previous_envelopes[l]: 
                    # no, then add year
                    missing_years[l].append(t)
                else:
                    # yes... then check if map exists
                    if GRASSInterface.getG().checkMap(previous_envelopes[l][str(t)]) is None:
                        missing_years[l].append(t)
        return missing_years

    def areEnvelopesNewerThanReplicates(self):
        for i in self.replicates:
            if i.getTimeStamp() > self.getEnvelopesTimeStamp():
                return False
        return True

    def getEnvelopesTimeStamp(self):
        es = self.node.xpath('envelopes')
        if es:
            return float(es[0].attrib['ts'])
        return 0

    def addAnalysisResult(self,ls_id,result):
        """
        Result is a tuple with (command executed, filename of output)
        """
        
        mdig_config = MDiGConfig.getConfig()
        
        current_dir = os.path.dirname(os.path.abspath(result[1]))
        filename = os.path.basename(result[1])
        
        # move filename to analysis directory
        if current_dir is not os.path.abspath(mdig_config.analysis_dir):
            # if file exists and overwrite_flag is specified then overwrite
            if os.path.isfile( os.path.join(mdig_config.analysis_dir,filename) ):
                if mdig_config.overwrite_flag:
                    os.remove( os.path.join(mdig_config.analysis_dir,filename) )
                else:
                    self.log.error( "Can't add analysis because filename %s already exists and "\
                     "overwrite_flag is not set." % filename)
                    return
            
            shutil.move(result[1], mdig_config.analysis_dir)
        
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
        
    
    def updateProbabilityEnvelope(self, ls, start, end, force=False):
        
        # Set the region in case it hasn't been yet
        current_region = self.experiment.getRegion(self.r_id)
        GRASSInterface.getG().setRegion(current_region)
        
        missing_envelopes = self.areEnvelopesUpToDate(ls, start, end,
                force=force)
        if not missing_envelopes or not self.isComplete(): return
        
        for l in ls:
            maps = []
            for r in self.replicates:
                saved_maps = r.getSavedMaps(l)
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
                    
                filename = self.experiment.getName() + "_region_" + self.r_id
                if self.var_keys is not None:
                    for v in self.var_keys:
                        filename += "_" + v + "_"
                        var_value=self.variables[self.var_keys.index(v)]
                        if isinstance(var_value,str):
                            filename += var_value
                        else:
                            filename += repr(var_value)
                filename += "_ls_" + l + "_" + repr(t) + "_prob"
                prob_env = GRASSInterface.getG().occupancyEnvelope(maps_to_combine,filename)
                if prob_env is not None:
                    self._addEnvelope(prob_env,l,t)
                    
    def _addEnvelope(self, env_name, lifestage_id, t):
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
    
    def updateXML(self):
        pass
