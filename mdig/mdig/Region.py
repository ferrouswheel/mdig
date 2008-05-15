#!/usr/bin/env python2.4
""" 

Copyright 2006, Joel Pitt

"""

import logging
from GrassMap import GrassMap

class Region:
	
	def __init__(self, node):
		self.log = logging.getLogger("mdig.region")
		self.xml_node = node
	
	def getName(self):
		if "name" in self.xml_node.attrib.keys():
			return self.xml_node.attrib["name"]
		else:
			return None
		
	def setName(self, new_name):
		self.xml_node.attrib["name"] = new_name
	
	def getResolution(self):
		res_node = self.xml_node.xpath('resolution')
		if len(res_node) == 1:
			return float(res_node[0].text)
		else:
			return 1
			
	def setResolution(self, res):
		res_node = self.xml_node.xpath('resolution')
		if len(res_node) == 0:
			res_node = lxml.etree.SubElement(self.xml_node,'resolution')
		else:
			res_node = res_node[0]
		res_node.text = repr(res)
		
	def getExtents(self):
		ext_node = self.xml_node.xpath('extents')
		if len(ext_node) == 1:
			extents = {}
			extents = ext_node[0].attrib
			return extents
		else:
			self.log.debug("Region has no unique extent node")
			return None
		
	def setExtents(self, ext):
		ext_node = self.xml_node.xpath('extents')
		if len(ext_node) == 1:
			extents = {}
			extents = ext_node[0].attrib
			return float(res.node.text)
		else:
			return None
		
	def getBackgroundMap(self):
		bmap = None
		bmap_node = self.xml_node.xpath('background')
		if len(bmap_node) > 0:
			bmap=GrassMap(bmap_node[0])
		
		return bmap
	
	def setBackgroundMap(self):
		#TODO Region:setBackgroundMap
		pass
	
	def updateXML(self):
		pass
