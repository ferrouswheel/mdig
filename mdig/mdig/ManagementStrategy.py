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

import GRASSInterface 
import MDiGConfig
import OutputFormats
from GrassMap import MapMissingException
from GRASSInterface import SetRegionException
import DispersalModel

class ManagementStrategy:
    """
    ManagementStrategy is a class for representing the strategies taken
    by environmental authorities to control the dispersal of a species.
    
    Each "strategy" element within the "management" element of the
    DispersalModel creates a ManagementStrategy class.
    """

    def __init__(self,node,model):
        self.log = logging.getLogger("mdig.strategy")
        
        self.grass_i = GRASSInterface.getG()
        
        self.temp_map_names={}
        self.active = False
        self.treatments = None

        self.area_type = None
        self.treatment_area = None

        if node is None:
            self.node = self.init_strategy(model)
        else:
            self.node = node

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

    def _load_treatments(self):
        """
        Initialise treatments list
        """
        self.treatments = []
        self.log.debug("Parsing management strategies")
        treatment_nodes=self.node.xpath("treatments/t")
        self.log.debug("%d treatments found for strategy %s" %
                (len(treatment_nodes),self.get_description()) )
        for t_node in treatment_nodes:
            self.treatments.append(Treatment(self,t_node))

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

    def get_treatments_for_param(self,var_key):
        """
        Get any treatments that affect the parameter specified by var_key
        """
        result = []
        for t in self.get_treatments():
            if t.affects_var(var_key):
                result.append(t)
        return result # return an empty list if there are none
        
    def get_treatments_for_ls(self,ls_id):
        """
        Get any treatments that affect the lifestage specified by ls_id
        """
        result = []
        for t in self.get_treatments():
            if t.affects_ls(ls_id):
                result.append(t)
        return result # return an empty list if there are none

    def get_treatment_map(self,replicate):
        """
        Get the treatment map, generating it dynamically if necessary
        Returns none if there is none (i.e. the treatment is for the whole
        region)
        """
        if self.area_filter is None and \
                self.area_map is None:
            area_node = self.node.xpath("area")
            if len(area_node) == 0: return None
            assert(len(area_node) == 1)
            mfilter_node = self.node.xpath("mfilter")
            if len(area_node) == 1:
                self.area_type = "filter"
                    self.area_filter = Event(mfilter_node)
            else:
                self.area_map = GrassMap(area_node)
        if self.area_filter is not None:
            #TODO work out what the in and out maps are
            self.area_filter.run(input_map, output_map, false, rep)
            return output_map
        if self.area_map is None:
            self.area_map.getMapFilename()
        
class Treatment:

    def __init__(self, strategy, node):
        self.strategy = strategy
        self.treatment_type = None
        if node is None:
            self.node = self.init_treatment(self.strategy)
        else:
            # if node is provided then create treatment from xml
            self.node = node

    def affects_var(self, var_key):

        pass

    def get_impact

    def affects_ls(self, ls_id):
        

