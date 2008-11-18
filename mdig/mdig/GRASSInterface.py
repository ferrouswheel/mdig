#!/usr/bin/env python2.4

import sys
import os
import shutil
import logging
import random
import re
import signal
import pdb
import subprocess

import XMLModel
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

# null_output is where the output of commands go when they are not wanted.
if sys.platform == "win32":                # on a Windows port
    null_output = "mdig-null"
    def removeNullOutput():
        os.remove(null_output)
else:
    null_output = "/dev/null"
    def removeNullOutput():
        pass

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
        
        if not self.checkEnvironment():
            self.log.debug("Attempting setup of GRASS from config file")
            self._set_vars()
        
        if self.checkEnvironment():
            self.log.log(logging.INFO, "Saving GRASS region")
            self.runCommand('g.region --o save='+self.old_region)
    
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
        
    def nullBitmask(self, filename, generate=True):
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
            if c.base_dir:
                dest_dir = os.path.join(c.base_dir, c.output_dir)
            else:
                dest_dir = c.output_dir
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
        pid = subprocess.Popen(["python",
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
            name=generateMapName()
            self.createCoordMap(name,bmap.value)
            map_type="vector"
        elif bmap.xml_map_type == "name":
            name = bmap.value
            map_type = self.checkMap(name)
        elif bmap.xml_map_type == "value":
            name=generateMapName()
            self.mapcalc(name,bmap.value)
            map_type="raster"
        elif bmap.xml_map_type == "mapcalc":
            name=generateMapName()
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
        
        cmd = 'v.in.ascii output=v' + name + ' cat=3'
        if self.log.getEffectiveLevel() >= logging.DEBUG:
            cmd += ' > ' + null_output
            
        sites_pipe = os.popen(cmd, 'w')
        for s in value:
            sites_pipe.write('%f|%f|%d\n' % s)
        sites_pipe.close()

        removeNullOutput()
        
        self.runCommand('v.to.rast input=v%s output=%s use=cat --o' % (name, name))
        
        self.removeMap('v' + name)
        
        #res = self.getCurrentResolution()
        #x1=x + 0.5 + (res / 2.0)
        #x2=x + 0.5 - (res / 2.0)
        #y1=y + 0.5 + (res / 2.0)
        #y2=y + 0.5 - (res / 2.0)
        
        #self.runCommand('r.mapcalc \"%s=if(x()<%f && x()>%f && y()<%f && y()>%f, 1, null())\" 2> /dev/null' % (name, x1, x2, y1, y2), logging.DEBUG);
    
    def copyMap(self,src, dest,overwrite=False):
        if overwrite:
            self.removeMap(dest)
        self.runCommand('g.copy rast=%s,%s' % (src, dest), logging.DEBUG)
    
    def getCurrentResolution(self):
        if self.checkEnvironment():
            p=os.popen("g.region -p", 'r')
            output = p.read()
            res=re.search("nsres:\s+(\d+)\newres:\s+(\d+)",output)
            if res is None:
                self.log.error("Failed to get resolution, perhaps this is a latlong location? Output was:\n%s" % output)
                sys.exit(1)
            
            return (float(res.groups()[0]) + float(res.groups()[1])) / 2
        else:
            self.log.warning("Using default resolution (1)")
            return 1

    def rasterValueFreq(self,mapname):
        p=os.popen("r.stats -c input=%s" % mapname, 'r')
        output = p.read()
        p.close()
        res=re.findall("(\d+) (\d+)\n",output)
        if len(res) == 0:
            self.log.error("Failed to get raster stats. Output was:\n%s" % output)
            sys.exit(1)
            
        return res
        
    def setRegion(self,region):
        name = region.getName()
        if name is not None:
            self.log.debug("Setting region to %s", name)
            if self.runCommand('g.region region=%s' % name,
                    ignoreOnFail=[256]) == 1:
                self.log.error("Region doesn't exist")
                sys.exit(1)
            
        else:
            extents = region.getExtents()
            command_string = 'g.region '
            extent_string = ''
            
            for key in extents.keys():
                
                if key == "north":
                    extent_string += 'n=' + str(extents[key] + ' ')
                elif key == "south":
                    extent_string += 's=' + str(extents[key] + ' ')
                elif key == "east":
                    extent_string += 'e=' + str(extents[key] + ' ')
                elif key == "west":
                    extent_string += 'w=' + str(extents[key] + ' ')
                    
            res = region.getResolution()
            
            self.log.debug("Setting region using extents %s and res %f", extent_string, res)
            if self.runCommand(command_string + extent_string + 'res='
                    + repr(res),ignoreOnFail=[256]) == 1:
                self.log.error("Region couldn't be set")
                sys.exit(1)
                    
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

    def checkMapset(self, mapset_name):
        """
        Check if mapset already exists
        """
        p=os.popen("g.mapsets -l", 'r')
        output = p.read()
        mapsets = output.split()
        if mapset_name in mapsets:
            return True
        return False

    def changeMapset(self, mapset_name, create=False):
        """
        Change to specified mapset. If create is True than create it if necessary       
        """

        #p=os.popen("g.mapsets -p", 'r')
        #output = p.read()
        #mapset_search_path = output.split()
        
        self.runCommand("g.mapset -c mapset=%s" % mapset_name)
        
        #self.runCommand("g.mapsets mapset=%s" % ",".join(mapset_search_path))

        return True

    def occupancyEnvelope(self, maps_to_combine, filename):
        """ Generates an occupancy envelope

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
            map_str = ','.join(maps_to_combine[index:index+max_maps])
            index = index+max_maps
            num_maps = num_maps - max_maps
            temp_file = generateMapName();
            self.runCommand("r.series input=%s output=%s method=count" % (map_str,temp_file))
            c_maps.append(temp_file)
        
        # combine maps if more than 100 are being used.
        if len(c_maps) > 1:
            map_str = ','.join(c_maps)
            prob_env = generateMapName();
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
        
    
    def runCommand(self, commandstring, log_level=logging.DEBUG,
            stalls=False, ignoreOnFail=[] ):
        self.log.log(log_level, "exec: " + commandstring)
        
        lvl = self.log.getEffectiveLevel()
        if lvl >= logging.INFO:
            commandstring += " 2> " + null_output
        ret = 0
        
        # Spawn allows ctrl-c to be easily caught, but can't suppress output...
        #args = ["bash", "-c", '"'+ commandstring + '"']
        #os.spawnvp(os.P_WAIT, args[0], args)
        
        # Some commands don't play nice with os.popen, so we revert to os.system
        # os.system makes the command intercept interrupts, so we prefer not
        # to use it during the simulation. 
        if stalls:
            ret = os.system(commandstring)
            if ret == 0:
                ret = None # For consistancy with return of popen
        else:
            cmd_stdout = os.popen(commandstring,"r")
            self.stdout = cmd_stdout.read()
            ret = cmd_stdout.close()
            self.log.log(logging.DEBUG, self.stdout)

        # If the command returns an error code then print it, cleanup, and then exit
        if (ret is not None) and not (ret in ignoreOnFail):
            self.log.log(logging.ERROR, 'Exit status for "%s" was %d' % (commandstring,ret))
            pdb.set_trace()
            exit_function = signal.getsignal(signal.SIGINT)
            exit_function(None, None)
        
        if lvl >= logging.INFO:
            removeNullOutput()
        
            
        return ret

    def cleanUp(self):
        self.log.log(logging.INFO,'Restoring region')
        
        self.runCommand('g.region region='+self.old_region,ignoreOnFail=[256])
        self.closeDisplay()

        
#   def exists(self,mapname):
        
class MapNotFoundException (Exception): pass        
    
def generateMapName(base=""):
    #TODO check that map doesn't exist
    return repr(os.getpid()) + "_" + base + "_" + repr(int(random.random()*1000000))
