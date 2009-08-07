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

import sys
import os
import shutil
import logging
import random
import re
import signal
import pdb
import subprocess
from subprocess import Popen
import StringIO
import tempfile

class MapNotFoundException (Exception): pass        
class SetRegionException (Exception): pass        
    
import DispersalModel
import MDiGConfig

grass_i = None

# NO LONGER NEEDED, handled internally by Python
# For portability of popen:
#if sys.platform == "win32":                # on a Windows port
#   try:
#       import win32pipe
#       popen = win32pipe.popen
#   except ImportError:
#       raise ImportError, "The win32pipe module could not be found"
#else:                                      # else on POSIX box
#import os
popen = os.popen

##### removeNullOutput shouldn't be needed now we use subprocess module
# null_output is where the output of commands go when they are not wanted.
#if sys.platform == "win32":                # on a Windows port
#    null_output = "mdig-null"
#    def removeNullOutput():
#        os.remove(null_output)
#else:
#    null_output = "/dev/null"
#    def removeNullOutput():
#        pass

def getG(create=True):
    global grass_i
    if grass_i is None:
        if create:
            grass_i = GRASSInterface()
            logging.getLogger("mdig.grass").debug("Creating new GRASSInterface instance")
        else:
            logging.getLogger("mdig.grass").debug("No GRASSInterface and not creating new one")
    return grass_i

class InitMapException(Exception):
    pass

class GRASSInterface:

    grass_vars = { "GISRC": None, "GISBASE": None }
    in_grass_vars = { "GISDBASE": None, "LOCATION_NAME": None, "MAPSET": None }
    old_region="mdig_temp_region"
    
    def __init__(self):
        self.config = MDiGConfig.getConfig()
        self.log = logging.getLogger("mdig.grass")
        self.stderr = ""
        self.stdout = ""
        self.displays = {}
        self.filename = None
        self.outputIsTemporary = False
        self.old_mapset = None
        self.blank_map = None
        
        if not self.checkEnvironment():
            self.log.debug("Attempting setup of GRASS from config file")
            self._set_vars()
        
        if self.checkEnvironment():
            self.log.log(logging.INFO, "Saving GRASS region")
            self.runCommand('g.region --o save='+self.old_region)
            self.old_mapset = self.getMapset()
    
    def checkEnvironment(self):
        okay=True
        first_run=True
        for var in self.grass_vars.keys():
            
            # If this is NOT the first time the grass environment was checked
            if self.grass_vars[var] is not None:
                first_run=False
                
            if os.environ.has_key(var):
                self.grass_vars[var]=os.environ[var]
            else:
                self.log.log(logging.DEBUG, "Environment variable %s not found", var)
                okay=False
        
        if not okay:
            self.log.log(logging.INFO,"GRASS Environment incomplete: %s", self.grass_vars)
        elif first_run:
            self.log.log(logging.INFO,"GRASS Environment okay: %s", self.grass_vars)
            
        return okay
    
    def _set_vars(self):
        
        for var in self.grass_vars:
            if self.config.has_key(var):
                self.grass_vars[var]=self.config[var]
                os.environ[var]=self.config[var]
        
        os.environ["GIS_LOCK"]=str(os.getpid())
        if self.grass_vars["GISBASE"]:
            os.environ["LD_LIBRARY_PATH"]="/".join([self.grass_vars["GISBASE"], "/lib:$LD_LIBRARY_PATH"])
        self.log.debug("GRASS Environment is now: %s", self.grass_vars)

    def clearMonitor(self):
        os.environ['GRASS_PNG_READ']="FALSE"

    def paintMap(self, map_name):
        self.runCommand('d.rast map=%s -x -o bg=white' % map_name, logging.DEBUG)
        os.environ['GRASS_PNG_READ']="TRUE"
        
    def paintGrid(self, res):
        self.runCommand('d.grid -b size=%d' % res,logging.DEBUG )
        os.environ['GRASS_PNG_READ']="TRUE"
        
    def paintYear(self, year):
        self.runCommand('echo \"Year %d\" | d.text color=black line=10' % year,logging.DEBUG );
        os.environ['GRASS_PNG_READ']="TRUE"
        
    def null_bitmask(self, filename, generate=True):
        if generate:
            # Should use the -n flag to only generate bitmasks if necessary,
            # however the -n flag is currently broken
            self.runCommand('r.null map=%s' % filename, logging.DEBUG);
        else:
            self.runCommand('r.null -r map=%s' % filename, logging.DEBUG);
    
    def setOutput(self, filename=".png", width=480, height=480, display="default"):
        # close output before setting new one, even if it's the same
        # filename
        if self.filename:
            self.closeOutput()
        self.filename = filename
        if self.filename == ".png":
            self.filename = repr(int(random.random()*1000)) + "_temp.png"
            self.outputIsTemporary = True

        # display must always check the same file
        # use a temporary png filename while constructing png
        # (self.tempOutputFile)
        # also use a temporary filename for the file the display process
        # monitors (pid_disp_filename.png)
        # then, only copy self.tempOutputFile to pid_disp_filename.png and to .png
        # once closeOutput is called.

        if display and display not in self.displays:
            tempfilename = repr(os.getpid()) + "_disp_" + self.filename
            self.displays[display] = (self.filename, tempfilename, None)
            # start display process only when closeOutput is called
        elif display:
            # update the mapping from
            # filename to tempfilename
            oldd = self.displays[display]
            self.displays[display] = (self.filename, oldd[1], oldd[2])
            
        self.tempOutputFile = repr(os.getpid()) + "_" + repr(int(random.random()*1000)) + self.filename
        # TODO make getRandFilename function (or check python lib) that
        # checks for existing files.

        # set variables
        os.environ['GRASS_RENDER_IMMEDIATE']='TRUE'
        os.environ['GRASS_TRUECOLOR']='TRUE'
        os.environ['GRASS_PNGFILE']='TRUE'
        os.environ['GRASS_WIDTH']=repr(width)
        os.environ['GRASS_HEIGHT']=repr(height)
        os.environ['GRASS_PNGFILE']=self.tempOutputFile
        os.environ['GRASS_PNG_READ']="FALSE"

    def closeOutput(self):
        # copy self.tempOutputFile to pid_disp_filename.png (check
        # self.displays mapping between filename and temp display
        # filename) and to filename 
        
        # copy from tempfilanem to filename
        if self.filename and self.filename.find(".png") != -1 and not self.outputIsTemporary:
            c = MDiGConfig.getConfig()
            # TODO: make a temp directory in the home dir for these sorts of things
            if MDiGConfig.home_dir:
                dest_dir = os.path.join(MDiGConfig.home_dir)
            else:
                dest_dir = "." #c.output_dir
            shutil.copy(self.tempOutputFile, os.path.join(dest_dir,self.filename))

        for d_name in self.displays:
            d = self.displays[d_name]

            if d[0] == self.filename:
                # copy temp to display temp
                shutil.copy(self.tempOutputFile, d[1])
            
            # create display process if necessary
            if d[2] is None:
                d = (d[0], d[1], self.spawnDisplay(d[1]))
                self.displays[d_name] = d
            break

        # delete tempOutputFile
        os.remove(self.tempOutputFile)
        self.filename = None

    def spawnDisplay(self, fileToWatch):
        pid = Popen(["python",
            os.path.join(os.path.dirname(sys.argv[0]), "mdig", "ImageShow.py"), fileToWatch]).pid
        return pid

    def closeDisplay(self, d_name=None):
        # kill display subprocess
        # ... display program automatically ends when file is no longer
        # available
        if d_name is None:
            d_keys = self.displays.keys()
            for i in d_keys:
                self.closeDisplay(i)

        # delete self.displays[display][1]... i.e. tempfilename in
        # setOutput
        if d_name in self.displays:
            os.remove(self.displays[d_name][1])
            del self.displays[d_name]
            
    #def initMaps(self,map_nodes):
        #mapNames=[]
        #for m in map_nodes:
            #mapNames.append(self.initMap(m))
        #return mapNames
    
    def initMap(self,bmap):
        name=None
        map_type=None
        bmap.xml_map_type
        if bmap.xml_map_type == "sites":
            name=self.generateMapName()
            self.createCoordMap(name,bmap.value)
            map_type="vector"
        elif bmap.xml_map_type == "name":
            name = bmap.value
            map_type = self.checkMap(name)
        elif bmap.xml_map_type == "value":
            name=self.generateMapName()
            self.mapcalc(name,bmap.value)
            map_type="raster"
        elif bmap.xml_map_type == "mapcalc":
            name=self.generateMapName()
            self.mapcalc(name,bmap.value)
            map_type="raster"
        bmap.ready = True
        return name, map_type
    
    def destructMap(self,fn):
        """ Remove a map
        should only be called from GrassMap
        """
        #if grassmap.temporary and grassmap.ready:
        self.removeMap(fn) # grassmap.getMapFilename())
            
    def createCoordMap(self,name,value):
        #v.in.ascii
        #v.to.rast input=name output=name [use=string] [column=name] [layer=value] [value=value] [rows=value] [--overwrite]
        
        self.log.log(logging.INFO, "Creating map %s using coordinates %s", name,repr(value))
        
        vector_prefix = "v____"
        cmd = 'v.in.ascii output=' + vector_prefix + name + ' cat=3'
        if self.log.getEffectiveLevel() >= logging.DEBUG:
            p = Popen(cmd, shell=True, stdin=subprocess.PIPE, \
                    stdout=subprocess.PIPE)
        else:
            p = Popen(cmd, shell=True, stdin=subprocess.PIPE)
            
        sites_string=""
        for s in value:
            sites_string += ('%f|%f|%d\n' % s)
        p.communicate(sites_string)
        if p.returncode:
            # @todo throw exception
            pass

        self.runCommand('v.to.rast input=%s%s output=%s use=cat --o' % \
                (vector_prefix, name, name))
        self.removeMap('v____' + name)
        
    def copyMap(self,src, dest,overwrite=False):
        if overwrite:
            self.removeMap(dest)
        self.runCommand('g.copy rast=%s,%s' % (src, dest), logging.DEBUG)
    
    def getCurrentResolution(self):
        if self.checkEnvironment():
            output=Popen("g.region -p", shell=True, stdout=subprocess.PIPE).communicate()[0]
            res=re.search("nsres:\s+(\d+)\newres:\s+(\d+)",output)
            if res is None:
                # @todo replace with exception
                self.log.error("Failed to get resolution, perhaps this is a latlong location? Output was:\n%s" % output)
                sys.exit(1)
            
            # @todo return tuple of (nsres, ewres)
            return (float(res.groups()[0]) + float(res.groups()[1])) / 2
        else:
            self.log.warning("Using default resolution (1)")
            return 1

    def rasterValueFreq(self,mapname):
        p=Popen("r.stats -c input=%s" % mapname, shell=True, stdout=subprocess.PIPE)
        output=p.communicate()[0]
        res=re.findall("(\d+) (\d+)\n",output)
        if len(res) == 0:
            self.log.error("Failed to get raster stats. Output was:\n%s" % output)
            sys.exit(1)
            
        return res
        
    def setRegion(self,region):
        name = region.get_name()
        if name is not None:
            self.log.debug("Setting region to %s", name)
            ret = self.runCommand('g.region region=%s' % name)
        else:
            extents = region.getExtents()
            command_string = 'g.region '
            extent_string = ''
            res_str = ''
            
            if extents is not None:
                for key in extents.keys():
                    if key == "north":
                        extent_string += 'n=' + str(extents[key] + ' ')
                    elif key == "south":
                        extent_string += 's=' + str(extents[key] + ' ')
                    elif key == "east":
                        extent_string += 'e=' + str(extents[key] + ' ')
                    elif key == "west":
                        extent_string += 'w=' + str(extents[key] + ' ')
            else:
                self.log.warning("Region didn't define extents")

            res = region.getResolution()
            if res is not None:
                res_str = 'res=' + repr(res)
            else:
                self.log.warning("Region didn't define resolution")
            
            self.log.debug("Setting region using extents %s and res %f",
                    repr(extent_string), repr(res))
            ret = self.runCommand(command_string + extent_string + res_str)
        if ret is None:
            self.log.error("Error setting region")
            raise SetRegionException()
        else:
            return True
                    
    def getMapInfo(self,map_name):
        # Have to check all possible types of maps
        map_types=[ "cell", "fcell", "dcell", "vector", "windows" ]
        
        for t in map_types:
            p=os.popen("g.findfile element=%s file=%s" % (t,map_name), 'r')
            info = dict([tuple(x.split('=')) for x in p.readlines()])
            for i in info.keys():
                info[i]=info[i].strip("'\n")
            
            if len(info["name"]) > 0:
                if t in ["cell","fcell","dcell"]:
                    # Return raster sub types simply as "raster"
                    t = "raster"
                info["type"] = t
                return info

        self.log.error("Can't find map/region called %s" % map_name)
        raise MapNotFoundException()
    
    def no_mapset_component(self,x):
        # Function to check mapset isn't in map name
        if x.find("@") == -1:
            return True
        else:
            return False

    def removeMap(self,map_name):
        map_type = self.checkMap(map_name)
        #if map_type is None:
        #   self.log.debug('Trying to remove non existant map')
        #   if MDiGConfig.getConfig().DEBUG:
        #       pdb.set_trace()

        if map_type: self.log.debug("Removing %s map %s", map_type, map_name)
        if map_type == 'raster':
            self.runCommand('g.remove rast=%s' % map_name, logging.DEBUG);      
        elif map_type == 'vector':
            self.runCommand('g.remove vect=%s' % map_name, logging.DEBUG);
        
            
    def mapcalc(self,map_name,expression):
        map_name='\\"' + map_name + '\\"' 
        self.runCommand('r.mapcalc "%s=%s"' % (map_name, expression));
    
    def makeMask(self,mask_name):
        if mask_name is None:
            self.runCommand('r.mask -r none');
        else:
            self.runCommand('r.mask -o INPUT=%s' % mask_name);
    
    def checkMap(self,file_name):
        # Have to check all possible types of maps
        map_types=[ "cell", "fcell", "dcell", "vector" ]
        
        for t in map_types:
            #print "checking for existing map " + file_name + " of type " + t
            p=os.popen("g.findfile element=%s file=%s" % (t,file_name), 'r')
            output = p.read()
            res=re.search("name='.+'",output)
            #pdb.set_trace()
            if res is not None:
                if t in ["cell","fcell","dcell"]:
                    # Return raster sub types simply as "raster"
                    t = "raster"
                return t
        return None

    def getMapset(self):
        """
        Get current mapset
        """
        output = subprocess.Popen("g.mapsets -p", shell=True,
                stdout=subprocess.PIPE).communicate()[0]
        mapsets = output.split()
        return mapsets[0]

    def checkMapset(self, mapset_name):
        """
        Check if mapset already exists
        """
        output = subprocess.Popen("g.mapsets -l", shell=True,
                stdout=subprocess.PIPE).communicate()[0]
        mapsets = output.split()
        if mapset_name in mapsets:
            return True
        return False

    def changeMapset(self, mapset_name, create=False):
        """
        Change to specified mapset. If create is True than create it if necessary       
        """
        if self.getMapset() != mapset_name: 
            self.runCommand("g.mapset -c mapset=%s" % mapset_name)
        
        return True

    def occupancyEnvelope(self, maps_to_combine, filename):
        """ Generates an occupancy envelope from boolean,
            population, or age of population maps.

            @param maps_to_combine is a list of maps to merge to generate the
            occupancy envelope.
            @param filename is the output map.

            @todo create equivalent for average populations/age
        """
        
        if len(maps_to_combine) > 10000:
            self.log.warning("Probability envelope not designed for more than 10000 maps")
        elif len(maps_to_combine) == 0: 
            self.log.error("No maps provided for combining into probability envelope")
            return None
        
        # Only do 100 maps at a time, since GRASS can only open so many files.
        max_maps = 100
        num_maps = len(maps_to_combine)
        index = 0
        c_maps = []
        prob_env = None
        while num_maps > 0:
            # We have to replace population number or population age with
            # a one, since we are interested in the percentage of occupancy.
            reclass_to_occupancy_maps = []
            for i in range(index,index+max_maps):
                reclass_map = self.generateMapName();
                # check the map name isn't already being used
                while reclass_map in reclass_to_occupancy_maps:
                    reclass_map = self.generateMapName();
                self.runCommand("echo \"* = 1\nend\" | r.reclass "
                        "input=%s output=%s" % (maps_to_combine[i],reclass_map))
                reclass_to_occupancy_maps.append(reclass_map)
            map_str = ','.join(reclass_to_occupancy_maps)
            index = index+max_maps
            num_maps = num_maps - max_maps
            temp_file = self.generateMapName();
            self.runCommand("r.series input=%s output=%s method=count" % (map_str,temp_file))
            # Now remove temporary reclass maps
            for r_map in reclass_to_occupancy_maps:
                self.removeMap(r_map)
            c_maps.append(temp_file)
        
        # combine maps if more than 100 are being used.
        if len(c_maps) > 1:
            map_str = ','.join(c_maps)
            prob_env = self.generateMapName();
            self.runCommand("r.series input=%s output=%s method=sum" % (map_str,prob_env))
        else:
            prob_env = c_maps[0]
            # clear c_maps so we don't try to delete c_map[0] later
            c_maps = [] 
        
        # divide maps by total count and replace 0 with null()
        # must use float in division so mapcalc knows that output map is
        # FCELL/DCELL
        self.mapcalc(filename, "if(%s==0.0,null(),%s/%f)"  % (prob_env,prob_env,float(len(maps_to_combine))))
        
        # remove temporary maps
        for c in c_maps:
            self.removeMap(c)
        self.removeMap(prob_env)
        
        # set color table for occupancy envelope
        self.runCommand("r.colors map=%s color=gyr --quiet" % (filename))
        
        return filename
        
    
    def runCommand(self, commandstring, log_level=logging.DEBUG, ignoreOnFail=[]):
        self.log.log(log_level, "exec: " + commandstring)
        ret = None
        
        lvl = self.log.getEffectiveLevel()
        if lvl >= logging.INFO:
            p = Popen(commandstring, shell=True, stdout=subprocess.PIPE, \
                    stderr=subprocess.PIPE)
        else:
            p = Popen(commandstring, shell=True, stdout=subprocess.PIPE)
        
        self.stdout = p.communicate()[0]
        if len(self.stdout) > 0:
            self.log.debug("stdout: " + self.stdout)
        ret = p.returncode

        # If the command returns an error code then print it,
        # cleanup, and then exit
        # @todo throw exception on error instead
        if (ret is not None) and ret != 0 and not (ret in ignoreOnFail):
            self.log.log(logging.ERROR, 'Exit status for "%s" was %d' % (commandstring,ret))
            pdb.set_trace()
            exit_function = signal.getsignal(signal.SIGINT)
            exit_function(None, None)
        
        return ret

    def clean_up(self):
        self.log.log(logging.INFO,'Restoring region')
        
        self.changeMapset(self.old_mapset)
        self.runCommand('g.region region='+self.old_region,ignoreOnFail=[256])
        if self.blank_map is not None:
            self.destructMap(self.blank_map)
        self.closeDisplay()

    def get_blank_map(self):
        blank_map_name = "_____mdig_blank_map"
        if self.blank_map is None:
            self.blank_map = blank_map_name
            self.runCommand('r.mapcalc "' + blank_map_name + '=null()"')
        return self.blank_map

    def generateMapName(self, base=""):
        random_name = None
        while random_name is None or self.checkMap(random_name) is not None:
            random_name = repr(os.getpid()) + "_" + base + "_" + repr(int(random.random()*1000000))
        return random_name

    def getRange(self):
        """ provides region data to be passed to LifestageTransition
        (rowProcessing.process function from Steve Wangens popMod)
        @todo rename to get_region
        """
        # sends command to GRASS session and returns result via stdout (piped)
        output = subprocess.Popen("g.region -p", stdout=subprocess.PIPE).communicate()[0]
        # pipes input from r.info and formats it as a StringIO object
        # (additional functionality vs. string, like 'readlines')
        pre_rangeData = StringIO.StringIO(output)
        # creates a list (rangeData) where each entry is a different line of
        # the g.region output
        rangeData = pre_rangeData.readlines()
        return (rangeData)

    def getIndexRaster(self,indexRaster):
        '''Imports the raster layers representing the index layer.'''
        cmd = "r.info -m %s --v" % (indexRaster)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        r.stdout, r.stderr = r.communicate()
        if r.stdout == '':
            self.log.error("That raster does not exist in the current mapset.")
            pdb.set_trace()
            #indexRaster = raw_input()
            #cmd = "r.info -m %s --v" %(indexRaster)
            #r = grass.pipe_command(cmd) 
            #r.stdout, r.stderr = r.communicate()
        self.log.info("Index raster set to " + str(indexRaster))
        return indexRaster

    def getRasterList(popRasterList):
        '''Manually enter the raster layers representing the population stages
           and return a list of the corresponding names.'''
    # This method seems to be obsolete because it doesn't do anything?
    ##    popRasterList = []
    ##    rastNo = 1
    ##    while 1:
    ##        print "Enter the name of the raster for population stage %i. 
    # Enter 'done' if complete, or 'list' to list available rasters in the 
    # current mapset." %(rastNo)
    ##        raster = raw_input()
    ##        if raster == "done":
    ##            break
    ##        if raster =="list":
    ##            r = grass.pipe_command("g.list type=rast")
    ##            print r.communicate()[0]
    #    for i in popRasterList:
    #        cmd = "r.info -m %s --v" %(i)
    #        r = grass.pipe_command(cmd) 
    #        r.stdout, r.stderr = r.communicate()
    ##            if r.stdout != '':
    ##                if raster in popRasterList:
    ##                    print "That raster has already been specified for a 
    #different stage.  Please specify a different raster for this stage."
    ##                else:
    ##                    popRasterList.append(raster)
    ##                    rastNo = rastNo+1
    ##            else:
    ##                print "That raster does not exist in the current mapset
    #- please try again"
    #    print "Population rasters set to "+ str(popRasterList)
        return popRasterList

    def rasterToAscii(rasterName, IO=1):
        """ Creates a temporary file storing the raster data in ascii format
        (accessable for LifestageTransition processing), and if IO=1 also
        creates a temp file to write the new data to after being processed.
        Returns the names of the temporary files.

        @todo rename to exportRasterToASCII   
        """
        imp_cmd = "r.out.ascii -hi input=%s output=-" % (rasterName)
        data = subprocess.Popen(imp_cmd,stdout.PIPE)
        tempDataFileName = (tempfile.mkstemp(prefix = 'popMod_inRast_', \
                    suffix='.txt', text=True))
        tempDataFile = open(tempDataFileName[1], 'w')
        tempDataFile.write(data.communicate()[0])
        tempDataFile.close()
        if IO==1:
            tempOutDataFileName = (tempfile.mkstemp(prefix='popMod_outRast_', \
                        suffix='.txt', text=True))
            return tempDataFileName, tempOutDataFileName
        else:
            return tempDataFileName

    def indexToAscii(indexRaster):
        """ @todo merge with the above code and generalise """
        # export index to temporary ascii map
        imp_cmd = "r.out.ascii -hi input=%s output=-" % (indexRaster)
        data = subprocess.Popen(imp_cmd,stdout.PIPE)
        tempDataFileName = (tempfile.mkstemp(prefix='popMod_inIndex_', \
                    suffix='.txt', text=True))
        tempDataFile = open(tempDataFileName[1], 'w')
        tempDataFile.write(data.communicate()[0])
        tempDataFile.close()
        # create temporary output filename for ascii index map
        tempOutDataFileName = (tempfile.mkstemp(prefix='popMod_outIndex_', \
                    suffix='.txt', text=True))
        return tempDataFileName, tempOutDataFileName

    def count_sites(self, vmap):
        """ Counts the number of points within a vector map """
        # use v.info -t and parse result
        p1 = Popen(["v.info", "-t", vmap], stdout=subprocess.PIPE)
        p2 = Popen(["grep", "nodes"], stdin=p1.stdout, stdout=subprocess.PIPE)
        p3 = Popen(["awk", "-F=","{print $2}"], stdin=p2.stdout, \
                stdout=subprocess.PIPE)
        output = p3.communicate()[0]
        return int(output)

    def count_cells(self, rmap):
        """ Count the number cells occupied in a raster map """
        p1 = Popen(r"r.univar" + " -g " + rmap, shell=True, stdout=subprocess.PIPE)
        p2 = Popen(r"sed -n '1p;1q'", shell=True, stdin=p1.stdout,
                stdout=subprocess.PIPE)
        p3 = Popen(r"awk -F = '{print $2}'", shell=True, stdin=p2.stdout, \
                stdout=subprocess.PIPE)
        output = p3.communicate()[0]
        return int(output)
        
#   def exists(self,mapname):

