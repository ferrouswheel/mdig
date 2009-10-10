#!/usr/bin/env python2.4
#
#  Copyright (C) 2009 Joel Pitt, Fruition Technology
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
Management module. Part of MDiG - Modular Dispersal in GIS
"""

import lxml.etree
import random
import logging
import shutil
import string
import os
import time
import pdb

import mdig
import GRASSInterface 
import MDiGConfig
import OutputFormats
from GrassMap import GrassMap, MapMissingException
from GRASSInterface import SetRegionException
import DispersalModel
from Event import Event

class ManagementStrategy:
    """
    ManagementStrategy is a class for representing the strategies taken
    by environmental authorities to control the dispersal of a species.
    
    Each "strategy" element within the "management" element of the
    DispersalModel creates a ManagementStrategy class.
    """

    def __init__(self,node,instance):
        self.log = logging.getLogger("mdig.strategy")
        
        self.grass_i = GRASSInterface.getG()
        
        self.temp_map_names={}
        self.active = False
        self.treatments = None
        self.instance = instance 

        if node is None:
            self.node = self.init_strategy(instance.experiment)
        else:
            self.node = node

    def set_instance(self, instance):
        self.instance = instance

    def init_strategy(self, model):
        """ Initialise the xml structure that represents a
            ManagementStrategy.
        """
        # TODO implement me
        pass

    def get_name(self):
        return self.node.attrib["name"]

    def set_name(self,name):
        self.node.attrib["name"] = name

    def get_region(self):
        return self.node.attrib["region"]

    def set_region(self, r_id):
        # TODO check that region is valid
        self.node.attrib["region"] = r_id

    def get_description(self):
        desc_node=self.node.xpath("description")
        return desc_node[0].text

    def set_description(self, desc):
        desc_node=self.node.xpath("description")
        desc_node[0].text = desc

    def get_delay(self):
        desc_node=self.node.xpath("delay")
        if len(desc_node) == 0:
            return 0
        return int(desc_node[0].text)

    def set_delay(self, desc):
        desc_node=self.node.xpath("delay")
        if len(desc_node) == 0:
            delay_node = lxml.etree.SubElement(self.node,'delay')
        desc_node[0].text = repr(desc)

    def _load_treatments(self):
        """
        Initialise treatments list
        @TODO sort according to treatment index
        """
        self.treatments = []
        self.log.debug("Parsing management strategies")
        treatment_nodes=self.node.xpath("treatments/t")
        self.log.debug("%d treatments found for strategy %s (%s)" %
                (len(treatment_nodes),self.get_name(),self.get_description()) )
        index_counter = 0
        for t_node in treatment_nodes:
            self.treatments.append(Treatment(self,t_node,index_counter))
            index_counter += 1

    def get_treatments(self):
        """
        Get all treatments
        """
        if self.treatments is None:
            try:
                self._load_treatments()
            except MapMissingException, e:
                raise
        return self.treatments

    def get_treatments_for_param(self,var_key,timestep):
        """
        Get any treatments that affect the parameter specified by var_key
        """
        result = []
        if timestep < self.instance.experiment.get_period()[0] + self.get_delay():
            return result
        for t in self.get_treatments():
            if t.affects_var(var_key):
                result.append(t)
        return result # return an empty list if there are none
        
    def get_treatments_for_ls(self,ls_id,timestep):
        """
        Get any treatments that affect the lifestage specified by ls_id
        """
        result = []
        if timestep < self.instance.experiment.get_period()[0] + self.get_delay():
            return result
        for t in self.get_treatments():
            if t.affects_ls(ls_id):
                result.append(t)
        return result # return an empty list if there are none

class Treatment:

    def __init__(self, strategy, node, t_index):
        self.strategy = strategy
        self.log = logging.getLogger("mdig.treatment")
        self.treatment_type = None

        self.area_type = None
        self.area_map = None
        self.area_ls = None
        self.area_filter = None
        self.area_filter_output = None

        self.event = None

        if node is None:
            self.node = self.init_treatment(self.strategy)
        else:
            # if node is provided then create treatment from xml
            self.node = node
        self.index = t_index
        # temporary map name
        self.area_temp = "x___strategy_"  + self.strategy.get_name() + "_area_t_" + str(self.index)
        # temporary map name
        self.var_temp = "x___strategy_" + self.strategy.get_name() + "_var_t_" + str(self.index)

    def __del__(self):
        GRASSInterface.getG().removeMap(self.area_temp)
        GRASSInterface.getG().removeMap(self.var_temp)

    def init_treatment(self):
        # TODO create the required elements with a default global area
        # and a dummy action
        raise NotImplementError

    def affects_var(self, var_key):
        """
        Return whether the treatment modifies the variable specified by var_key
        """
        av_node = self.node.xpath("affectVariable")
        if len(av_node) > 0:
            assert len(av_node) == 1
            self.treatment_type = "affectVariable"
            if av_node[0].attrib["var"] == var_key:
                return True
        return False

    def affects_ls(self, ls_id):
        """
        Return whether this treatment affects a particular lifestage.
        Note, this doesn't check whether a treatment that affects a variable, has
        that variable within the lifestage specified by ls_id.

        Event variable parameters should be checked individually using
        affects_var()
        """
        if ls_id == self.get_ls():
            return True
        return False

    def get_ls(self):
        ls_node = self.node.xpath("event")
        if len(ls_node) > 0:
            assert len(ls_node) == 1
            self.treatment_type = "event"
            return ls_node[0].attrib["ls"]
        return None
        
    def get_treatment_area(self,replicate):
        """
        Get the map name representing the treatment area, generating it
        dynamically if necessary Returns none if there is none (which means the
        treatment is for the whole region)

        @todo support multiple area maps and take the intersection.
        @todo clean up filter map when Treatment is deleted
        """
        if self.area_filter is None and \
                self.area_map is None:
            area_node = self.node.xpath("area")
            if len(area_node) == 0: return None
            assert(len(area_node) == 1)
            mfilter_node = area_node[0].xpath("mfilter")
            self.area_ls = area_node[0].attrib['ls']
            if len(mfilter_node) == 1:
                self.area_type = "filter"
                self.area_filter = Event(mfilter_node[0])
            else:
                # If it's not an mfilter it must be a map
                self.area_type = "map"
                self.area_map = GrassMap(area_node[0])
        dist_map = replicate.temp_map_names[self.area_ls][0]
        if self.area_filter is not None:
            if self.area_filter_output is not None:
                GRASSInterface.getG().removeMap(self.area_filter_output)
            self.area_filter.run( dist_map, \
                    self.area_temp, replicate, False)
            self.area_filter_output = self.area_temp
            return self.area_filter_output
        if self.area_map is not None:
            return self.area_map.getMapFilename(dist_map) #replicate.get_previous_map(self.area_ls))
        
    def get_event(self):
        """
        If the treatment runs an event at the end of the lifestage, create and
        return it. Otherwise return None.
        """
        if self.event is not None:
            return self.event
        e_node = self.node.xpath("event")
        if len(e_node) > 0:
            assert len(e_node) == 1
            self.treatment_type = "event"
            self.event = Event(e_node[0])
        return self.event

    def get_variable_map(self, var_key, var_val, replicate):
        """
        Get the map that represents a variable that is impacted by
        affectsVarable, for the specific regions withing get_treatment_area.
        Returns None if this treatment does not affect var_key.
        """
#if self.strategy.instance is None:
#            self.log.error("Not connected to a DispersalInstance.")
#            return None
        if not self.affects_var(var_key):
            return None
        area_mask_map = self.get_treatment_area(replicate)
        if area_mask_map is None:
            # This means the treatment is applied globally, no need to return a
            # map
            return None
        altered_value = self.get_altered_variable_value(var_key,var_val)
        orig_value = var_val
        GRASSInterface.getG().mapcalc(self.var_temp, \
                "if(" + area_mask_map + "==1," \
                + str(altered_value) + "," + str(orig_value))
        return self.var_temp

    def get_altered_variable_value(self,var_key,var_val):
        """
        Get the value of the variable after it is altered by affectVariable
        """
        if not self.affects_var(var_key):
            return None
        #if self.strategy.instance is None:
            #self.log.error("Not connected to a DispersalInstance.")
            #return None
        orig_value = var_val #self.strategy.instance.get_var(var_key)
        # handle decrease, increase, ratio
        av_node = self.node.xpath("affectVariable")
        # should only be one affectVariable element, and only one child indicating
        # effect
        effect = av_node[0][0].tag
        effect_amount = av_node[0][0].text
        new_value = float(orig_value)
        if effect == "decrease":
            new_value -= float(effect_amount)
        elif effect == "increase":
            new_value += float(effect_amount)
        elif effect == "ratio":
            new_value *= float(effect_amount)
        else:
            self.log.error("Unknown management effect: " + effect)
            sys.exit(mdig.mdig_exit_codes["treatment_effect"])
        return new_value









