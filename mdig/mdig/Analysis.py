#!/usr/bin/env python2.4
""" 
Copyright (C) 2008 Joel Pitt, Fruition Technology

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import os
import re

import MDiGConfig
import OutputFormats
import GRASSInterface

class Analysis:
    """ Represents an analysis that is run across replicate maps.

    @todo: Allow class to create new analyses.
    @todo: Create AnalysisResult class.
    @todo: Split and subclass Analysis into ReplicateAnalysis, and
    EnvelopeAnalysis, UnifyReplicateAnalysis.
    @todo: Alter xml to allow for commands and in-built analysis.
    """
    
    def __init__(self, node):
        # logger
        self.log = logging.getLogger("mdig.analysis")
        # associated node in xml model tree
        self.xml_node = node

    def getCommand(self):
        """ Get the name of the command this analysis runs

        @return: Command name
        """

        if "name" in self.xml_node.attrib.keys():
            return self.xml_node.attrib["name"]
        else:
            self.log.error('Analysis has no "name" attribute')
        return None

    def getParams(self):
        """ Get parameters for analysis command.

        @return: dictionary with parameter name keys and parameter values.
        """
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
        """ Set up environment so analysis can run without trouble

        Removes the analysis output file if it already exists, but only if it is
        set up to append to the output file. Otherwise the files are overwritten
        anyway (assuming --o is set).

        @todo: Check overwrite flag before overwrite. Throw AnalysisFileExists,
        inherit from FileExists exception.
        """
        if self.isRedirectedStdOut() and self.isAppend():
            fn = self._makeFilename(rep)
            try:
                os.remove(fn)
            except (IOError, OSError):
                pass

    def _fillInMapParameters(self,p):
        ls_id = self.getLifestageID()
        # fill in map parameters
        for p_name,val_tuple in p.items():
            value = val_tuple[0]
            if len(val_tuple) > 1:
                a = val_tuple[1]
            else:
                a = None
                
            if value == "currentMap":
                p[p_name]=in_name
            elif value == "previousMap":
                # TODO currently getPreviousMaps is broken
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
        return p

    def run(self,in_name,rep):
        """ Run the analysis on a replicate.

        @param in_name: The name of the current map.
        @param rep: The replicate to run on.

        @todo: remove in_name as the output and use getPreviousMap once it's
        implemented in replicate.
        """

        #rawCommand = self.getCommand()
        cmd = ""
        #if rawCommand in Analysis.inbuiltCommands:
        #    cmd = Analysis.inbuiltCommands[rawCommand].createCommandString(in_name,rep)
        #else
        p=fillInMapParameters(self.getParams())
        # put all the parameters and command into a command string
        cmd=self.createCommandString(p)
        
        fn = ""
        # base_cmd has the input map parameter removed for recording
        # in xml.
        base_cmd = ""
        if self.isRedirectedStdOut():
            fn = self._makeFilename(rep)
            # if generating a file for each time step then check file
            # doesn't exist
            if not self.isAppend() and os.exists(fn):
                if not MDiGConfig().overwrite_flag:
                    raise AnalysisOutputFileExists()
                else:
                    os.remove(fn)

            # remove input map parameter from base_cmd
            res=re.search("(input=\w+)",base_cmd)
            if res is not None:
                base_cmd = base_cmd.replace(res.groups()[0], "")

        # if the analysis requires the timestep to be written/appended
        # to the output file then do so
        if self.isInterval():
            fh = open(fn, 'a')
            fh.write('%d ' % rep.current_t)
            fh.close()
        
        # add the output filename to the command
        if self.isAppend():
            cmd += " >> "
        else:
            cmd += " > "
            
        # run command!
        GRASSInterface.getG().runCommand(cmd + fn)
            
        # if a file was generated then add this to the replicate
        ls_id = self.getLifestageID()
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
        cmd.strip()
        return cmd

class AnalysisOutputFileExists (Exception):
    pass

