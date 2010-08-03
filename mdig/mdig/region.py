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
import lxml
from grassmap import GrassMap

class Region:
    
    def __init__(self, node):
        self.log = logging.getLogger("mdig.region")
        self.xml_node = node
        self.id = self.xml_node.attrib["id"]
    
    def get_name(self):
        if "name" in self.xml_node.attrib.keys():
            return self.xml_node.attrib["name"]
        else:
            return None
        
    def set_name(self, new_name):
        self.xml_node.attrib["name"] = new_name
    
    def get_resolution(self):
        res_node = self.xml_node.xpath('resolution')
        if len(res_node) == 1:
            return float(res_node[0].text)
        else:
            if self.get_name() is not None: return None
            else: return 1
            
    def set_resolution(self, res):
        res_node = self.xml_node.xpath('resolution')
        if len(res_node) == 0:
            res_node = lxml.etree.SubElement(self.xml_node,'resolution')
        else:
            res_node = res_node[0]
        res_node.text = repr(float(res))
        
    def get_extents(self):
        ext_node = self.xml_node.xpath('extents')
        if len(ext_node) == 1:
            extents = dict(ext_node[0].attrib)
            for i in extents: extents[i] = float(extents[i])
            return extents
        else:
            self.log.debug("Region has no unique extent node")
            return None
        
    def set_extents(self, ext):
        ext_node = self.xml_node.xpath('extents')
        if len(ext_node) == 0:
            ext_node = lxml.etree.SubElement(self.xml_node,'extents')
        else:
            ext_node = ext_node[0]
        for i in ext:
            if i not in ['n','s','e','w']:
                raise KeyError('extent keys must be one of n,s,e,w')
        for i in ext:
            ext_node.attrib[i] = str(ext[i])
        
    # This is now stored in mdig.conf and is up to user to specify
    #def getBackgroundMap(self):
    #    bmap = None
    #    bmap_node = self.xml_node.xpath('background')
    #    if len(bmap_node) > 0:
    #        bmap=GrassMap(bmap_node[0][0])
    #    return bmap
    
    def update_xml(self):
        pass
