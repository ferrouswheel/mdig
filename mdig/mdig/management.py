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
import grass 
import config
import outputformats
import grass
from grassmap import GrassMap
from grass import SetRegionException, MapNotFoundException
import model
from event import Event

class ManagementStrategy:
    """
    ManagementStrategy is a class for representing the strategies taken
    by environmental authorities to control the dispersal of a species.
    
    Each "strategy" element within the "management" element of the
    DispersalModel creates a ManagementStrategy class.
    """

    def __init__(self,node,experiment,instance=None):
        self.log = logging.getLogger("mdig.strategy")
        
        self.grass_i = grass.get_g()
        
        self.temp_map_names={}
        self.active = False
        self.treatments = None
        # We save the experiment instead of the instance
        # because instances are only temporarily associated with strategies
        self.experiment = experiment
        self.instance = instance 

        if node is None:
            self.node = self.init_strategy(experiment)
        else: self.node = node

    def set_instance(self, instance):
        self.instance = instance

    def init_strategy(self, model):
        """ Initialise the xml structure that represents a
            ManagementStrategy.
        """
        raise NotImplementedError()

    def get_name(self):
        return self.node.attrib["name"]

    def set_name(self,name):
        self.node.attrib["name"] = name

    def get_region(self):
        return self.node.attrib["region"]

    def set_region(self, r_id):
        rs = self.experiment.get_regions()
        if r_id not in rs:
            raise grass.SetRegionException("Invalid region ID %s" % r_id)
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

    def set_delay(self, delay):
        delay_node=self.node.xpath("delay")
        if len(delay_node) == 0:
            delay_node = [lxml.etree.SubElement(self.node,'delay')]
        delay_node[0].text = repr(int(delay)) # ensure it's an int

    def get_map_resources(self):
        maps = []
        ts = self.get_treatments()
        for t in ts:
            maps.extend(t.get_map_resources())
        return maps

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
            self._load_treatments()
        return self.treatments

    def get_treatments_for_param(self,var_key,timestep):
        """
        Get any treatments that affect the parameter specified by var_key
        """
        result = []
        if self.instance is None:
            self.log.error("No instance assigned to ManagementStrategy")
        if timestep < self.experiment.get_period()[0] + self.get_delay():
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
        if timestep < self.experiment.get_period()[0] + self.get_delay():
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

        self.area_ls = None
        self.areas = None

        self.event = None

        if node is None:
            self.node = self.init_treatment()
        else:
            # if node is provided then create treatment from xml
            self.node = node
        self.index = t_index
        # temporary map name
        self.area_temp = None
        # temporary map name
        self.var_temp = "x_t___strategy_" + self.strategy.get_name() + "_var_t_" + str(self.index)

    def __del__(self):
        if 'area_temp' in dir(self):
            grass.get_g().remove_map(self.area_temp)
        if 'var_temp' in dir(self):
            grass.get_g().remove_map(self.var_temp)

    def init_treatment(self):
        # TODO create the required elements with a default global area
        # and a dummy action
        raise NotImplementedError()

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

    def load_areas(self):
        if self.areas is None:
            self.areas = []
            self.area_node = self.node.xpath("area")
            if len(self.area_node) == 0: return self.areas
            assert(len(self.area_node) == 1)
            self.area_node = self.area_node[0]
            self.area_ls = self.area_node.attrib['ls']
            for a in self.area_node:
                if isinstance(a.tag, basestring):
                    # Ignore comment nodes
                    self.areas.append(TreatmentArea(a,self,len(self.areas)))
        return self.areas

    def get_treatment_area_map(self, replicate):
        """ Ensure all TreatmentAreas are initialised and then return
            a freshly merged version.
            Returns none if there is no area specified (which means the
            treatment is for the whole region)
        """
        areas = self.load_areas()
        if len(areas) == 0: return None
        return self._merge_areas(replicate)

    def _merge_areas(self, replicate):
        """
            Merge all the TreatmentArea maps based on the combine attribute
            ("and" or "or" them)
        """
        generate = False
        # Check whether the component Areas change between calls
        if self.area_temp is not None:
            for a in self.areas:
                if a.is_dynamic():
                    generate = True
                    break
            if not generate:
                return self.area_temp
        else:
            self.area_temp = "x_t___strategy_"  + self.strategy.get_name() + \
                              "_area_t_" + str(self.index)
        # What operation should we use to merge maps? Should be 'and' or 'or'
        if 'combine' not in self.area_node.attrib:
            operation = "and"
        else:
            operation = self.area_node.attrib['combine']
        assert(operation == "and" or operation == "or")

        g = grass.get_g()
        g.remove_map(self.area_temp)
        merge_str = "if("
        for a in self.areas:
            if operation == "and":
                merge_str += "!isnull(%s)" % a.get_treatment_area(replicate)
                merge_str += " && "
            else:
                merge_str += "!isnull(%s)" % a.get_treatment_area(replicate)
                merge_str += " || "
        # remove trailing operator
        merge_str = merge_str[:-4] + ",1,null())" 
        g.mapcalc(self.area_temp,merge_str)
        return self.area_temp
        
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

    def get_map_resources(self):
        # get maps from within treatment event
        m = self.strategy.experiment
        e = self.get_event()
        maps = []
        if e: maps.extend(e.get_map_resources(m))
        # get maps from within area specification
        if self.areas is None: self.load_areas()
        for a in self.areas:
            maps.extend(a.get_map_resources())
        return maps

    def get_variable_map(self, var_key, var_val, replicate):
        """
        Get the map that represents a variable that is impacted by
        affectsVarable, for the specific regions withing get_treatment_area.
        Returns None if this treatment does not affect var_key.
        """
#if self.strategy.instance is None:
#            self.log.error("Not connected to a instance.")
#            return None
        if not self.affects_var(var_key):
            return None
        area_mask_map = self.get_treatment_area_map(replicate)
        if area_mask_map is None:
            # This means the treatment is applied globally, no need to return a
            # map
            return None
        altered_value = self.get_altered_variable_value(var_key,var_val)
        if altered_value is None:
            altered_value = "null()"
        orig_value = var_val
        if orig_value is None:
            orig_value = "null()"
        grass.get_g().mapcalc(self.var_temp, \
                "if(" + area_mask_map + "==1," \
                + str(altered_value) + "," + str(orig_value) + ")")
        return self.var_temp

    def get_altered_variable_value(self,var_key,var_val):
        """
        Get the value of the variable after it is altered by affectVariable
        """
        if not self.affects_var(var_key):
            return None
        #if self.strategy.instance is None:
            #self.log.error("Not connected to a instance.")
            #return None
        orig_value = var_val #self.strategy.instance.get_var(var_key)
        # handle decrease, increase, ratio
        av_node = self.node.xpath("affectVariable")
        # should only be one affectVariable element, and only one child indicating
        # effect
        effect = None
        # Find the first non-comment element
        for i in av_node[0]:
            if isinstance(i.tag, basestring):
                effect = i.tag
                effect_amount = i.text
                break
        assert(effect is not None)
        new_value=None
        if orig_value is not None:
            new_value = float(orig_value)
        if effect == "decrease":
            if new_value is not None:
                new_value -= float(effect_amount)
            else:
                raise InvalidAlterationException()
        elif effect == "increase":
            if new_value is not None:
                new_value += float(effect_amount)
            else:
                raise InvalidAlterationException()
        elif effect == "ratio":
            if new_value is not None:
                new_value *= float(effect_amount)
            else:
                raise InvalidAlterationException()
        elif effect == "value":
            new_value = float(effect_amount)
        else:
            self.log.error("Unknown management effect: " + str(effect) )
            sys.exit(mdig.mdig_exit_codes["treatment_effect"])
        return new_value

class TreatmentArea:

    def __init__(self, node, treatment, a_index):
        """ Node is the xml node defining the TreatmentArea.
            treatment is the parent Treatment this area is for.
            a_index is the area index used to create the temp map name.
        """
        self.treatment = treatment
        self.node = node
        self.area = None
        self.area_filter_output = None
        self.index = a_index
        # temporary map name
        self.area_temp = "x_t___strategy_"  + self.treatment.strategy.get_name() + \
            "_area_t_" + str(self.treatment.index) + "_" +  str(self.index)
        self.init_from_xml()

    def __del__(self):
        if self.area_filter_output is not None:
            grass.get_g().remove_map(self.area_filter_output)

    def init_from_xml(self):
        if self.node.tag == "mfilter":
            self.area = Event(self.node)
        else:
            # If it's not an mfilter it must be a map
            self.area = GrassMap(self.node)

    def is_dynamic(self):
        """ Return whether this Area changes each timestep or not
            (Due to using a filter or mapcalc)
        """
        if isinstance(self.area, Event): return True
        elif isinstance(self.area, GrassMap): return self.area.refresh
        else: raise Exception("Unknown area type")

    def get_map_resources(self):
        maps = []
        if isinstance(self.area, Event):
            m = self.treatment.strategy.experiment
            maps.extend(self.area.get_map_resources(m))
        elif isinstance(self.area, GrassMap):
            if self.area.xml_map_type=="name":
                g = grass.get_g()
                maps.append((self.area.filename,g.find_mapset(self.area.filename)))
        return maps

    def get_treatment_area(self,replicate):
        """
        Get the map name representing the treatment area, generating it
        dynamically if necessary.
        """
        if isinstance(self.area, Event):
            if self.area_filter_output is not None:
                grass.get_g().remove_map(self.area_filter_output)
            dist_map = replicate.temp_map_names[self.treatment.area_ls][0]
            self.area.run( dist_map, \
                    self.area_temp, replicate, False)
            self.area_filter_output = self.area_temp
            return self.area_filter_output
        elif isinstance(self.area, GrassMap):
            replacements = {
                "POP_MAP": replicate.temp_map_names[self.treatment.area_ls][0],
                "START_MAP": replicate.initial_maps[self.treatment.area_ls].get_map_filename()
            }
            return self.area.get_map_filename(replacements)
        





