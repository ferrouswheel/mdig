#!/usr/bin/env python2.4
""" 

Copyright 2006, Joel Pitt

"""

import logging
import os
import re

import MDiGConfig
import OutputFormats
import GRASSInterface

class Analysis:
	
	def __init__(self, node):
		self.log = logging.getLogger("mdig.analysis")
		self.xml_node = node

	def getCommand(self):
		if "name" in self.xml_node.attrib.keys():
			return self.xml_node.attrib["name"]
		else:
			self.log.error('Analysis has no "name" attribute')

	def getParams(self):
		# recursively called when if(Not)PopulationBased nodes are encountered
		nodes = self.xml_node.xpath("param|flag")
		
		params={}
		for node in nodes:
			if node.tag == "flag":
				a="FLAG"
				params[node.attrib["name"]]=(a)
			else:
				for v in node:
					a=None
					if v.tag == "value":
						a=string.strip(v.text)
					elif v.tag == "currentMap":
						pass
					elif v.tag == "previousMap":
						if "offset" in v.attrib.keys():
							a = v.attrib["offset"]
					elif v.tag == "initialMap":
						pass
				params[node.attrib["name"]]=(v.tag,a)
		return params

	def preRun(self,rep):
		if self.isRedirectedStdOut() and self.isAppend():
			fn = self._makeFilename(rep)
			try:
				os.remove(fn)
			except (IOError, OSError):
				pass

	def run(self,in_name,out_name,rep,is_popn):
		p=self.getParams()
		
		ls_id = self.getLifestageID()
		
		for p_name,val_tuple in p.items():
			value = val_tuple[0]
			if len(val_tuple) > 1:
				a = val_tuple[1]
			else:
				a = None
				
			if value == "currentMap":
				p[p_name]=in_name
			elif value == "previousMap":
				if a is not None:
					p[p_name]=rep.getPreviousMap(ls_id,a)
				else:
					p[p_name]=rep.getPreviousMap(ls_id)
				# None is returned when a previous map of offset a
				# doesn't exist
				if p[p_name] == None:
					return
			elif value == "initialMap":
				p[p_name]=rep.getInitialMap(ls_id)
		cmd=self.createCommandString(p)
		
		fn = ""
		base_cmd = ""
		if self.isRedirectedStdOut():
			fn = self._makeFilename(rep)
			base_cmd = cmd.strip()
			
			res=re.search("(input=\w+)",base_cmd)
			if res is not None:
				base_cmd = base_cmd.replace(res.groups()[0], "")

		if self.isInterval():
			fh = open(fn, 'a')
			fh.write('%d ' % rep.current_t)
			fh.close()
		
		# create the filename
		if self.isAppend():
			cmd += " >> "
		else:
			cmd += " > "
			
		GRASSInterface.getG().runCommand(cmd + fn)
			
		if self.isRedirectedStdOut():
			rep.addAnalysisResult(ls_id,(base_cmd,fn))

	def getLifestageID(self):
		name = self.xml_node.xpath("parent::analyses/parent::lifestage/@name")
		return name[0]

	def _makeFilename(self,rep):
		mdig_config = MDiGConfig.getConfig()
		
		nodes = self.xml_node.xpath("output/file")
		if len(nodes) == 0:
			self.log.error("File to output analysis to is not defined")
			sys.exit(3)
		node = nodes[0]
		# text in file element is the prefix to the generated name
		prefix = ""
		if node.text is not None:
			prefix=node.text.strip()
		# Find out if we generate anything to add to prefix
		is_generate = True
		if "generate" in node.attrib.keys():
			if node.attrib["generate"].lower() == "false":
				is_generate = False
		# Get extension if specified
		ext = ""
		if "ext" in node.attrib.keys():
			ext = node.attrib["ext"]
		# check whether we are appending to the same file
		is_append = self.isAppend()
		
		
		if mdig_config.base_dir is None:
			generated = mdig_config.analysis_dir
		else:
			generated = os.path.join(mdig_config.base_dir, mdig_config.analysis_dir)
		generated = os.path.join(generated, prefix)
		generated += OutputFormats.createFilename(rep)
		if not is_append:
			generated += "_t_" + repr(rep.current_t)
		if len(ext) > 0:
			generated += ext
		
		return generated

	def isAppend(self):
		nodes = self.xml_node.xpath("output/file")
		if len(nodes) == 1:
			node = nodes[0]
			if "append" in node.attrib.keys():
				if node.attrib["append"].lower() == "false":
					return False
		return True
			
	def isInterval(self):
		nodes = self.xml_node.xpath("output/file/@date")
		if len(nodes) == 1:
			node = nodes[0]
			if node.lower() == "false":
				return False
			else:
				return True
		return self.isAppend()
	

	def isRedirectedStdOut(self):
		nodes = self.xml_node.xpath("output/file")
		if len(nodes) == 1:
			return True
		else:
			return False
	
	def createCommandString(self,params):
		cmd=self.getCommand() + ' '
		for p_name,value  in params.items():
			if value == "FLAG":
				cmd += "-" + p_name + " "
			else:
				cmd += p_name + "=" + str(value) + " "
		return cmd
