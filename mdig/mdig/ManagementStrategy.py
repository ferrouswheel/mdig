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

        if node is None:
            self.node = self.model.add_management()
        else:
            # if node is provided then create replicate node from xml
            self.node = node


    def _load_treatments(self):
        """
        Initialise treatments list
        """


        
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

    def get_treatment_for_param(self,var_key):
        """
        Get any treatments that affect the parameter specified by var_key
        """
        return [] # return an empty list if there are none
        
