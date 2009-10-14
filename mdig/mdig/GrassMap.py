#!/usr/bin/env python2.4
#
#  Copyright (C) 2008 Joel Pitt, Fruition Technology
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
GrassMap module. Part of MDiG - Modular Dispersal in GIS
Copyright 2006, Joel Pitt
"""

import logging

import MDiGConfig
import GRASSInterface

class GrassMap:
    """
    GrassMap - encapsulates a map object, generating/refreshing it as needed
    """
    
    def __init__(self,xml_node=None,filename=None):
        # Get the logger object
        self.log = logging.getLogger("mdig.map")
        # Set the xml_node if one exists for this map
        self.xml_node = xml_node
        # Set the filename is one exists
        self.filename = filename

        # Initialise values
        self.map_type=None # type of map: raster or vector
        self.xml_map_type=None # type of map as defined by xml
        self.value=None # For maps that are just a constant value or for a mapcalc expression
        self.ready=False # Is the map ready for use?
        self.refresh=False # Should the map be refreshed any time someone attempts to obtain the filename?
        self.temporary = True # Should this map be deleted on quit?
    
        if self.xml_node is not None:
            # Read xml settings if this map is based on an xml node
            self._readXML()
        elif self.filename is not None:
            # If a filename was passed, check it's type and if it exists
            self.map_type = GRASSInterface.getG().checkMap(self.filename)
            if self.map_type is None:
                # ... raise an exception if it doesn't
                raise MapMissingException([self.filename])
        
        if self.xml_map_type in ["map",None]:
            # Only maps specified in xml that are not existing maps
            # are temporary by default
            self.temporary = False

    def __del__ (self):
        if self.temporary and self.ready:
            GRASSInterface.getG().destructMap(self.filename)
        
    def _readXML(self):
        """
        Parse map node XML
        """
        node = self.xml_node
        # If node is "sites" then it contains a list of coordinates
        if node.tag == "sites":
            self.xml_map_type = "sites"
            self.value=[]
            for s in node:
                x=int(s.attrib["x"])
                y=int(s.attrib["y"])
                if "count" in s.attrib.keys():
                    count=float(s.attrib["count"])
                else:
                    count=1
                self.value.append( (x,y,count) )
        # If node is "map" it contains the name of an existing map
        elif node.tag == "map":
                
            self.xml_map_type="name"
            self.value=node.text
            self.filename = node.text
            # Don't need to check map exists because it is done in __init__
        
        # If node is "value" it creates a raster map with a constant value
        elif node.tag == "value":
            self.xml_map_type="value"
            self.value=node.text
            
        # If node is "mapcalc" it computes the result of a mapcalc expression
        elif node.tag == "mapcalc":
            self.xml_map_type="mapcalc"
            self.value=node.text
            if 'refresh' in node.attrib.keys():
                if node.attrib['refresh'].lower() == "true":
                    self.refresh = True

    def changeMapType(self,maptype,value):
        """
        Convert map between raster/vector (not implemented)
        """
        # TODO implement conversion between raster/vector
        raise NotImplementedError, "changeMapType: Method not implemented"
            
    def getMapFilename(self, map_replacements=None):
        """
        Retrieve filename for the map. If this is the first time retrieving the
        map filename, or if the map is set to refresh itself every time it is
        retrieved, then generate it.

        @param ls The lifestage to base dynamic maps on. So that if the map is created
        by mapcalc, POP_MAP will be replaced with the latest map from that
        lifestage.
        """
        if self.filename is None or self.refresh:
            # If the map needs to be refreshed and has already been initiated
            # then destroy the old map...
            if self.refresh and self.ready:
                GRASSInterface.getG().destructMap(self.filename)
            
            if map_replacements is not None:
                self.filename, self.map_type = GRASSInterface.getG().initMap(self,  
                    map_replacements)
            else:
                self.filename, self.map_type = GRASSInterface.getG().initMap(self)
            self.ready = True
        return self.filename
    
    def clean_up(self):
        """
        Just removes map if it is temporary
        """
        if self.temporary and self.ready:
            GRASSInterface.getG().destructMap(self.filename)

class MapMissingException(Exception):
    def __init__(self,maps):
        self.missing_maps = maps

    
