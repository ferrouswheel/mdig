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

    def get_command(self):
        """ Get the name of the command this analysis runs

        @return: Command name
        """

        if "name" in self.xml_node.attrib.keys():
            return self.xml_node.attrib["name"]
        else:
            self.log.error('Analysis has no "name" attribute')
        return None

    def get_params(self):
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

    def pre_run(self,rep):
        """ Set up environment so analysis can run without trouble

        Removes the analysis output file if it already exists, but only if it is
        set up to append to the output file. Otherwise the files are overwritten
        anyway (assuming --o is set).

        @todo: Check overwrite flag before overwrite. Throw AnalysisFileExists,
        inherit from FileExists exception.
        """
        if self.is_redirected_stdout() and self.is_append():
            fn = self._make_filename(rep)
            try:
                os.remove(fn)
            except (IOError, OSError):
                pass

    def _fill_in_map_parameters(self,rep,p):
        ls_id = self.get_lifestage_id()
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
                # TODO currently get_previous_maps is broken
                if a is not None:
                    p[p_name]=rep.get_previous_map(ls_id,a)
                else:
                    p[p_name]=rep.get_previous_map(ls_id)
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

        @todo: remove in_name as the output and use get_previous_map once it's
        implemented in replicate.
        """

        #rawCommand = self.get_command()
        cmd = ""
        #if rawCommand in Analysis.inbuiltCommands:
        #    cmd = Analysis.inbuiltCommands[rawCommand].create_cmd_string(in_name,rep)
        #else
        p=self._fill_in_map_parameters(rep,self.get_params())
        # put all the parameters and command into a command string
        cmd=self.create_cmd_string(p)
        
        fn = ""
        # base_cmd has the input map parameter removed for recording
        # in xml.
        base_cmd = ""
        if self.is_redirected_stdout():
            fn = self._make_filename(rep)
            # if generating a file for each time step then check file
            # doesn't exist
            if not self.is_append() and os.exists(fn):
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
        if self.is_interval():
            fh = open(fn, 'a')
            fh.write('%d ' % rep.current_t)
            fh.close()
        
        # add the output filename to the command
        if self.is_append():
            cmd += " >> "
        else:
            cmd += " > "
            
        # run command!
        GRASSInterface.get_g().run_command(cmd + fn)
            
        # if a file was generated then add this to the replicate
        ls_id = self.get_lifestage_id()
        if self.is_redirected_stdout():
            class mock_ac:
                def __init__(self,base_cmd,fn):
                    self.cmd_string = base_cmd
                    self.output_fn = fn
            rep.add_analysis_result(ls_id,mock_ac(base_cmd,fn))

    def get_lifestage_id(self):
        name = self.xml_node.xpath("parent::analyses/parent::lifestage/@name")
        return name[0]

    def _make_filename(self,rep):
        mdig_config = MDiGConfig.get_config()
        
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
        is_append = self.is_append()
        
        if rep.instance.experiment.base_dir is None:
            generated = mdig_config.analysis_dir
        else:
            generated = os.path.join(
                    rep.instance.experiment.base_dir,
                    mdig_config.analysis_dir)
        generated = os.path.join(generated, prefix)
        generated += OutputFormats.createFilename(rep)
        if not is_append:
            generated += "_t_" + repr(rep.current_t)
        if len(ext) > 0:
            generated += ext
        
        return generated

    def is_append(self):
        nodes = self.xml_node.xpath("output/file")
        if len(nodes) == 1:
            node = nodes[0]
            if "append" in node.attrib.keys():
                if node.attrib["append"].lower() == "false":
                    return False
        return True
            
    def is_interval(self):
        nodes = self.xml_node.xpath("output/file/@date")
        if len(nodes) == 1:
            node = nodes[0]
            if node.lower() == "false":
                return False
            else:
                return True
        return self.is_append()
    

    def is_redirected_stdout(self):
        nodes = self.xml_node.xpath("output/file")
        if len(nodes) == 1:
            return True
        else:
            return False
    
    def create_cmd_string(self,params):
        cmd=self.get_command() + ' '
        for p_name,value  in params.items():
            if value == "FLAG":
                cmd += "-" + p_name + " "
            else:
                cmd += p_name + "=" + str(value) + " "
        cmd.strip()
        return cmd

class AnalysisOutputFileExists (Exception):
    pass

