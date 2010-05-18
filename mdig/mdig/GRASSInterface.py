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

class MapNotFoundException (Exception):
    def __init__(self, _map_name=""):
        self.map_name = _map_name

    def __str__(self):
        return "MapNotFoundException (map_name=" + self.map_name + ")"

class SetRegionException (Exception): pass        
class CommandException (Exception): pass        
    
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

def get_g(create=True):
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

class EnvironmentException(EnvironmentError):
    pass

class GRASSInterface:

    grass_var_names = [ "GISRC", "GISBASE",
            "GISDBASE", "LOCATION_NAME", "MAPSET",
            "GRASS_GNUPLOT",
            "GRASS_WIDTH",
            "GRASS_HEIGHT",
            "GRASS_HTML_BROWSER",
            "GRASS_PAGER",
            "GRASS_WISH",
            "GRASS_PYTHON",
            "GRASS_MESSAGE_FORMAT",
            "GRASS_TRUECOLOR",
            "GRASS_TRANSPARENT",
            "GRASS_PNG_AUTO_WRITE" ]
    old_region="mdig_temp_region"
    
    def __init__(self):
        self.config = MDiGConfig.get_config()
        self.log = logging.getLogger("mdig.grass")
        self.stderr = ""
        self.stdout = ""
        self.displays = {}
        self.grass_vars = {}
        self.filename = None
        self.outputIsTemporary = False

        self.old_mapset = None
        self.old_location = None
        self.old_gisdbase = None

        self.blank_map = None
        
        if not self.check_environment():
            self.log.debug("GRASS environment not detected, attempting setup of GRASS from config file")
            self.init_environment()
        
        self.log.log(logging.INFO, "Saving GRASS region")
        result=self.run_command('g.region --o save='+self.old_region, ignoreOnFail=[1,127])
        if result != 0:
            output = subprocess.Popen("env", shell=True, stdout=subprocess.PIPE).communicate()[0]
            self.log.error("Couldn't backup region, is GRASS environment set up correctly?")
            self.log.error("GISDBASE='%s' LOCATION_NAME='%s' MAPSET='%s'" % \
                    (self.grass_vars['GISDBASE'],self.grass_vars['LOCATION_NAME'],self.grass_vars['MAPSET']))
            raise EnvironmentException()

        self.old_mapset = self.grass_vars['MAPSET']
        self.old_location = self.grass_vars['LOCATION_NAME']
        self.old_gisdbase = self.grass_vars['GISDBASE']
    
    def check_environment(self):
        okay=True
        first_run=True
        for var in self.grass_var_names:
            # If this is NOT the first time the grass environment was checked
            if var in self.grass_vars: first_run=False
                
            if os.environ.has_key(var):
                # if the env variable exists
                self.grass_vars[var]=os.environ[var]
            else:
                # else make it None
                self.grass_vars[var]=None
                okay=False
        
        if not okay:
            self.log.log(logging.INFO,"GRASS Environment incomplete: %s", self.grass_vars)
        elif first_run:
            self.log.log(logging.INFO,"GRASS Environment okay: %s", self.grass_vars)
            
        return okay

    def insert_environ_path(self, var, path):
        """ Insert a path at the start of a environment variable. If the
        variable doesn't exist, create it.
        """
        old_path = None
        if var in os.environ:
            old_path = os.environ[var]
        if old_path:
            path += ":" + old_path
        os.environ[var] = path

    def init_environment(self):
        for var in self.grass_vars:
            if self.config['GRASS'].has_key(var):
                if len(self.config['GRASS'][var]) == 0:
                    self.log.error("GRASS variable %s is empty, check your mdig.conf" % (var))
                    raise EnvironmentException()
                self.grass_vars[var]=self.config['GRASS'][var]
                os.environ[var]=self.config['GRASS'][var]
        
        if self.grass_vars["GISBASE"]:
            self.insert_environ_path("LD_LIBRARY_PATH",
                    os.path.join(self.grass_vars["GISBASE"],"lib"))
            os.environ["GRASS_LD_LIBRARY_PATH"]=os.environ["LD_LIBRARY_PATH"]

            self.insert_environ_path("PATH",
                    os.path.join(self.grass_vars["GISBASE"],"bin"))
            self.insert_environ_path("PATH",
                    os.path.join(self.grass_vars["GISBASE"],"scripts"))

            self.insert_environ_path("PYTHONPATH",
                    os.path.join(self.grass_vars["GISBASE"],"etc/python"))
        else: 
            raise EnvironmentException()

        #export GIS_LOCK=$$
        pid = str(os.getpid())
        os.environ["GIS_LOCK"]=pid
        #export GRASS_VERSION="7.0.svn"
        os.environ["GIS_VERSION"]="6.4.svn"
        #setup GISRC file
        tmp="/tmp/grass6-mdig-" + pid
        os.environ["GISRC"]=tmp + "/gisrc"
        os.mkdir(tmp)
        from MDiGConfig import home_dir
        shutil.copyfile(os.path.join(home_dir,"../.grassrc6"),os.environ["GISRC"])
        
        #TODO cleanup tmp dir
        
        if not self.check_paths():
            raise EnvironmentException()
        self.set_gis_env()
        self.log.debug("GRASS Environment is now: %s", self.grass_vars)

    def check_paths(self):
        """ Check paths that should exist with the current GRASS environment,
        things like the GISDBASE, the LOCATION and MAPSET among others."""
        # Check paths
        is_ok = True
        # check directories etc:
        if not os.path.isdir(self.grass_vars['GISDBASE']):
            self.log.error("GRASS DB dir doesn't exist: %s" % self.grass_vars['GISDBASE'])
            is_ok = False
        loc_path = os.path.join(self.grass_vars['GISDBASE'],self.grass_vars['LOCATION_NAME'])
        if is_ok and not os.path.isdir(loc_path):
            self.log.error("GRASS location dir doesn't exist: %s" % loc_path)
            is_ok = False
        mapset_path = os.path.join(loc_path,self.grass_vars['MAPSET'])
        if is_ok and not os.path.isdir(mapset_path):
            self.log.error("GRASS mapset dir doesn't exist: %s" % mapset_path)
            is_ok = False
        if not os.path.isdir(self.grass_vars['GISBASE']):
            self.log.error("GRASS software dir doesn't exist: %s" % self.grass_vars['GISBASE'])
            is_ok = False

        return is_ok

    def set_gis_env(self):
        """ Use g.gisenv to update gisrc file from environment variables """
        var_list = [ "GISDBASE", "LOCATION_NAME", "MAPSET" ]
        for v in var_list:
            output = subprocess.Popen("g.gisenv set=%s=%s" % (v,self.grass_vars[v]),
                    shell=True, stdout=subprocess.PIPE).communicate()[0]

    def get_gis_env(self):
        # sends command to GRASS session and returns result via stdout (piped)
        output = subprocess.Popen("g.gisenv -n", shell=True, stdout=subprocess.PIPE).communicate()[0]
        pre_range_data = StringIO.StringIO(output).readlines()
        ret = {}
        for line in pre_range_data:
            fields = line.strip().split('=')
            ret[fields[0]] = fields[1]
        return ret
    
    def clear_monitor(self):
        os.environ['GRASS_PNG_READ']="FALSE"

    def paint_map(self, map_name, layer=None):
        """ Draw map_name on to the currently active GRASS monitor """
        if layer != None:
            colors = { 0: [(0,255,0), (0,50,0)],
                 1: [(255,255,0), (50,50,0)],
                 2: [(255,0,0), (50,0,0)],
                 3: [(0,0,255), (0,0,50)]
            }
            if layer in colors:
                pcolor= subprocess.Popen('r.colors map=%s rules=-' % map_name, \
                        shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
                rule_string = "0%% %d:%d:%d\n" % colors[layer][1]
                rule_string += "100%% %d:%d:%d\n" % colors[layer][0]
                rule_string += 'end'
                output = pcolor.communicate(rule_string)[0]

        self.run_command('d.rast map=%s -x -o bg=white' % map_name, logging.DEBUG)
        os.environ['GRASS_PNG_READ']="TRUE"


    def normalise_map_colors(self, maps):
        min_val = None; max_val = None
        for m in maps:
            cmd = "r.info -r map=%s" % m
            p=Popen(cmd, shell=True, stdout=subprocess.PIPE)
            output=p.communicate()[0]
            res=re.findall("(\w+)=([\d.]+)\n",output)
            if len(res) == 0 or res[0][0] != 'min' or res[1][0] != 'max':
                self.log.error("Failed to get raster range for %s. Output was:\n%s" % (m,output))
                sys.exit(1)
            if not min_val or min_val > float(res[0][1]): min_val = float(res[0][1])
            if not max_val or max_val < float(res[1][1]): max_val = float(res[1][1])
        one_third = (min_val - max_val) / 3.0 + min_val
        two_third = 2 * (min_val - max_val) / 3.0 + min_val
        # create full-scale color table for first map
        pcolor= subprocess.Popen('r.colors map=%s rules=-' % maps[0], \
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        rule_string = "%f blue\n" % (min_val)
        rule_string += "%f cyan\n" % (one_third)
        rule_string += "%f yellow\n" % (two_third)
        rule_string += "%f red\n" % (max_val)
        output = pcolor.communicate(rule_string)[0]
        # apply first map's color table to all other maps
        for i in range(1,len(maps)):
            pcolor= subprocess.Popen('r.colors map=%s rast=%s' % (maps[i],maps[0]), \
                    shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        return (min_val, max_val)
        
    def paint_grid(self, res):
        self.run_command('d.grid -b size=%d' % res,logging.DEBUG )
        os.environ['GRASS_PNG_READ']="TRUE"
        
    def paint_year(self, year):
        self.run_command('echo \"Year %d\" | d.text color=black line=10' % year,logging.DEBUG );
        os.environ['GRASS_PNG_READ']="TRUE"
        
    def null_bitmask(self, filename, generate=True):
        if generate:
            # Should use the -n flag to only generate bitmasks if necessary,
            # however the -n flag is currently broken
            self.run_command('r.null map=%s' % filename, logging.DEBUG);
        else:
            self.run_command('r.null -r map=%s' % filename, logging.DEBUG);
    
    def set_output(self, filename=".png", width=480, height=480, display="default"):
        # close output before setting new one, even if it's the same
        # filename
        if self.filename:
            self.close_output()
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
            
        self.tempOutputFile = repr(os.getpid()) + "_" + repr(int(random.random()*1000)) + os.path.basename(self.filename)
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

        # update grass variables
        for i in self.grass_vars:
            if os.environ.has_key(i):
                self.grass_vars[i] = os.environ[i]

    def close_output(self):
        # copy self.tempOutputFile to pid_disp_filename.png (check
        # self.displays mapping between filename and temp display
        # filename) and to filename 
        
        # copy from tempfilanem to filename
        if self.filename and self.filename.find(".png") != -1 and not self.outputIsTemporary:
            c = MDiGConfig.get_config()
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
                d = (d[0], d[1], self.spawn_display(d[1]))
                self.displays[d_name] = d
            break

        # delete tempOutputFile
        os.remove(self.tempOutputFile)
        self.filename = None

    def spawn_display(self, fileToWatch):
        pid = Popen(["python",
            os.path.join(os.path.dirname(sys.argv[0]), "mdig", "ImageShow.py"), fileToWatch]).pid
        return pid

    def close_display(self, d_name=None):
        # kill display subprocess
        # ... display program automatically ends when file is no longer
        # available
        if d_name is None:
            d_keys = self.displays.keys()
            for i in d_keys:
                self.close_display(i)

        # delete self.displays[display][1]... i.e. tempfilename in
        # setOutput
        if d_name in self.displays:
            os.remove(self.displays[d_name][1])
            del self.displays[d_name]
            
    #def initMaps(self,map_nodes):
        #mapNames=[]
        #for m in map_nodes:
            #mapNames.append(self.init_map(m))
        #return mapNames
    
    def init_map(self,bmap,map_replacements={"POP_MAP": None, "START_MAP": None}):
        name=None
        map_type=None
        if bmap.xml_map_type == "sites":
            name=self.generate_map_name()
            self.create_coord_map(name,bmap.value)
            map_type="vector"
        elif bmap.xml_map_type == "name":
            name = bmap.value
            map_type = self.check_map(name)
        elif bmap.xml_map_type == "value":
            name=self.generate_map_name()
            self.mapcalc(name,bmap.value)
            map_type="raster"
        elif bmap.xml_map_type == "mapcalc":
            name=self.generate_map_name()
            mapcalc_expr = bmap.value
            for k in map_replacements:
                # Substitute k by the given map:
                if map_replacements[k] is None:
                    if mapcalc_expr.find(k) != -1:
                        self.log.error("No map passed to initMap to substitute " \
                                + k + " variable in mapcalc expression")
                    pdb.set_trace()
                else:
                    mapcalc_expr = mapcalc_expr.replace(k, map_replacements[k])
            self.mapcalc(name,mapcalc_expr)
            map_type="raster"
        else:
            self.log.error("Unknown GrassMap type for initialisation")
            pdb.set_trace()
        bmap.ready = True
        return name, map_type
    
    def destruct_map(self,fn,mapset):
        """ Remove a map
        should really only be called from GrassMap
        """
        self.remove_map(fn,mapset)

    def create_coord_map(self,name,value):
        #v.in.ascii
        #v.to.rast input=name output=name [use=string] [column=name] [layer=value] [value=value] [rows=value] [--overwrite]
        
        self.log.log(logging.INFO, "Creating map %s using coordinates %s", name,repr(value))
        
        vector_prefix = "v____"
        cmd = 'v.in.ascii output=' + vector_prefix + name + ' cat=3'
        if self.log.getEffectiveLevel() >= logging.DEBUG:
            # Hide the v.in.ascii output unless FINE debuggins is on
            p = Popen(cmd, shell=True, stdin=subprocess.PIPE, \
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            p = Popen(cmd, shell=True, stdin=subprocess.PIPE)
            
        sites_string=""
        for s in value:
            sites_string += ('%f|%f|%d\n' % s)
        p.communicate(sites_string)
        if p.returncode:
            # @todo throw exception
            pass

        self.run_command('v.to.rast input=%s%s output=%s use=cat --o' % \
                (vector_prefix, name, name))
        self.remove_map('v____' + name)
        
    def copy_map(self,src, dest,overwrite=False):
        if overwrite:
            self.remove_map(dest)
        self.run_command('g.copy rast=%s,%s' % (src, dest), logging.DEBUG)
    
    def get_current_resolution(self):
        if self.check_environment():
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

    def raster_value_freq(self,mapname):
        cmd = "r.stats --q -c input=%s" % mapname
        self.log.debug("Getting raster stats with command: %s" % cmd)
        p=Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output=p.communicate()[0]
        res=re.findall("(\d+) (\d+)\n",output)
        if len(res) == 0:
            self.log.error("Failed to get raster stats. Output was:\n%s" % output)
            sys.exit(1)
            
        return res
        
    def set_region(self,region):
        name = region.get_name()
        # Now set region
        if name is not None:
            self.log.debug("Setting region to %s", name)
            ret = self.run_command('g.region region=%s' % name)
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
                self.log.warning("Region %s didn't define extents" % region.id)

            res = region.getResolution()
            if res is not None:
                res_str = 'res=' + repr(res)
            else:
                self.log.warning("Region %s didn't define resolution" % region.id)
            
            self.log.debug("Setting region using extents %s and res %s",
                    repr(extent_string), repr(res))
            ret = self.run_command(command_string + extent_string + res_str)
        if ret is None:
            self.log.error("Error setting region %s" % region.id)
            raise SetRegionException()
        else:
            return True
                    
    def get_map_info(self,map_name):
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

    def remove_map(self,map_name,mapset=None):
        map_type = self.check_map(map_name)
        # If mapset is different from the current one, then we to temporarily
        # change because grass can only alter the current mapset.
        old_mapset = None
        if mapset and mapset != self.grass_vars['MAPSET']:
            old_mapset = self.grass_vars['MAPSET']
            g.change_mapset(mapset)
        if map_type: self.log.debug("Removing %s map %s", map_type, map_name)
        if map_type == 'raster':
            self.run_command('g.remove rast=%s' % map_name, logging.DEBUG);      
        elif map_type == 'vector':
            self.run_command('g.remove vect=%s' % map_name, logging.DEBUG);
        # change back to original mapset
        if old_mapset:
            self.change_mapset(old_mapset)
            
    def mapcalc(self,map_name,expression):
        map_name='"' + map_name + '"' 
        self.run_command("r.mapcalc '%s=%s'" % (map_name, expression));
    
    def make_mask(self,mask_name):
        if mask_name is None:
            self.run_command('r.mask -r');
        else:
            self.run_command('r.mask -o input=%s' % mask_name);
    
    def check_map(self,file_name,mapset=None):
        # Have to check all possible types of maps
        map_types=[ "cell", "fcell", "dcell", "vector" ]
        if mapset:
            self.change_mapset(mapset)
        
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

    def update_grass_vars(self):
        env = self.get_gis_env()
        to_update = ["GISDBASE","LOCATION_NAME","MAPSET"]
        self.grass_vars.update(env)

    def get_mapset(self):
        """
        Get current mapset
        """
        return self.grass_vars["MAPSET"]

    def check_mapset(self, mapset_name, location=None):
        """
        Check if mapset already exists
        """
        loc_str = ""
        if location:
            loc_str = " location=%s" % location
        output = subprocess.Popen("g.mapset -l "+loc_str, shell=True,
                stdout=subprocess.PIPE).communicate()[0]
        mapsets = output.split()
        if mapset_name in mapsets:
            return True
        return False

    def change_mapset(self, mapset_name = None, location = None, create=False):
        """
        Change to specified mapset. If create is True than create it if necessary       
        """
        if mapset_name is None:
            mapset_name = "PERMANENT"
        loc = ""
        if location is not None:
            loc = " location=" + location
        if self.get_mapset() != mapset_name: 
            if create:
                result = self.run_command("g.mapset -c mapset=%s%s" % (mapset_name,loc))
            else:
                self.grass_vars["LOCATION_NAME"] = location
                self.grass_vars["MAPSET"] = mapset_name
                self.set_gis_env()
                #result = self.run_command("g.mapset mapset=%s%s" % \
                #        (mapset_name,location), ignoreOnFail=[1])
        self.update_grass_vars()
        return True

    def create_mdig_subdir(self,mapset):
        env = self.get_gis_env()
        dest_dir = os.path.join(env["GISDBASE"],env["LOCATION_NAME"],mapset,"mdig")
        os.mkdir(dest_dir)
        return dest_dir

    def check_location(self, location):
        assert location
        env = self.get_gis_env()
        gisdb = env["GISDBASE"]
        if os.path.isdir(os.path.join(gisdb,location,"PERMANENT")):
            return True
        return False

    def get_mapset_full_path(self, mapset):
        dir = os.path.join(self.grass_vars["GISDBASE"],self.grass_vars["LOCATION_NAME"],mapset)
        return dir

    def remove_mapset(self, mapset_name, location=None, force=False):
        """
        Remove mapset, ask for user confirmation unless force is True.
        """
        if mapset_name == "PERMANENT":
            # Can't remove permanent mapset!
            return False
        # change mapset to PERMANENT before removing map
        if self.get_mapset() == mapset_name: 
            self.change_mapset()
        # get the path to the mapset for removal
        env = self.get_gis_env()
        gisdb = env["GISDBASE"]
        loc = env["LOCATION_NAME"]
        if location is not None: loc = location
        mapset_dir = os.path.join(gisdb,loc,mapset_name)
        ans = "N"
        if not force and os.path.isdir(mapset_dir):
            ans = raw_input("Remove mapset at %s? [y/N] " % mapset_dir)
            if ans.upper() == "Y": force = True
        if force:
            self.run_command("rm -rf %s" % mapset_dir)
            return True 
        return False

    def occupancy_envelope(self, maps_to_combine, filename):
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
                reclass_map = self.generate_map_name();
                # check the map name isn't already being used
                while reclass_map in reclass_to_occupancy_maps:
                    reclass_map = self.generate_map_name();
                self.run_command("echo \"* = 1\nend\" | r.reclass "
                        "input=%s output=%s" % (maps_to_combine[i],reclass_map))
                reclass_to_occupancy_maps.append(reclass_map)
            map_str = ','.join(reclass_to_occupancy_maps)
            index = index+max_maps
            num_maps = num_maps - max_maps
            temp_file = self.generate_map_name();
            self.run_command("r.series input=%s output=%s method=count" % (map_str,temp_file))
            # Now remove temporary reclass maps
            for r_map in reclass_to_occupancy_maps:
                self.remove_map(r_map)
            c_maps.append(temp_file)
        
        # combine maps if more than 100 are being used.
        if len(c_maps) > 1:
            map_str = ','.join(c_maps)
            prob_env = self.generate_map_name();
            self.run_command("r.series input=%s output=%s method=sum" % (map_str,prob_env))
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
            self.remove_map(c)
        self.remove_map(prob_env)
        
        # set color table for occupancy envelope
        self.run_command("r.colors map=%s color=gyr --quiet" % (filename))
        
        return filename
        
    
    def run_command(self, commandstring, log_level=logging.DEBUG, ignoreOnFail=[]):
        self.log.log(log_level, "exec: " + commandstring)
        ret = None
        
        lvl = 0
        if len(logging.getLogger("mdig").handlers) > 0:
            lvl = logging.getLogger("mdig").handlers[0].level
        if lvl >= logging.INFO:
            p = Popen(commandstring, shell=True, stdout=subprocess.PIPE, \
                    stderr=subprocess.PIPE)
        else:
            p = Popen(commandstring, shell=True, stdout=subprocess.PIPE)
        
        self.stdout, self.stderr = p.communicate()
        if len(self.stdout) > 0:
            self.log.debug("stdout: " + self.stdout)
        if self.stderr is not None and len(self.stderr) > 0:
            self.log.debug("stderr: " + self.stderr)
        ret = p.returncode

        # If the command returns an error code then print it,
        # cleanup, and then exit
        # @todo throw exception on error instead
        if (ret is not None) and ret != 0 and not (ret in ignoreOnFail):
            self.log.error('Exit status for "%s" was %d' % (commandstring,ret))
            exit_function = signal.getsignal(signal.SIGINT)
            exit_function(None, None)
        return ret

    def clean_up(self):
        self.log.log(logging.INFO,'Restoring region')
        
        self.grass_vars['MAPSET'] = self.old_mapset 
        self.grass_vars['LOCATION_NAME']= self.old_location
        self.grass_vars['GISDBASE']= self.old_gisdbase
        self.set_gis_env()
        self.run_command('g.region region='+self.old_region,ignoreOnFail=[256])
        if self.blank_map is not None:
            self.destruct_map(self.blank_map)
        self.close_display()

    def get_blank_map(self):
        blank_map_name = "_____mdig_blank_map"
        if self.blank_map is None:
            self.blank_map = blank_map_name
            self.run_command('r.mapcalc "' + blank_map_name + '=null()"')
        return self.blank_map

    def generate_map_name(self, base=""):
        random_name = None
        while random_name is None or self.check_map(random_name) is not None:
            random_name = repr(os.getpid()) + "_" + base + "_" + repr(int(random.random()*1000000))
        return random_name

    def get_range(self):
        """ provides region data to be passed to LifestageTransition
        (rowProcessing.process function from Steve Wangens popMod)
        @todo rename to get_region
        """
        # sends command to GRASS session and returns result via stdout (piped)
        output = subprocess.Popen("g.region -p", shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE).communicate()[0]
        # pipes input from r.info and formats it as a StringIO object
        # (additional functionality vs. string, like 'readlines')
        pre_rangeData = StringIO.StringIO(output)
        # creates a list (rangeData) where each entry is a different line of
        # the g.region output
        rangeData = pre_rangeData.readlines()
        return (rangeData)

    def get_index_raster(self,indexRaster):
        '''Imports the raster layers representing the index layer.'''
        cmd = "r.info -m %s --v" % (indexRaster)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        r.stdout, r.stderr = r.communicate()
        if r.stdout == '':
            self.log.error("That raster does not exist in the current mapset.")
            pdb.set_trace()
            #indexRaster = raw_input()
            #cmd = "r.info -m %s --v" %(indexRaster)
            #r = grass.pipe_command(cmd) 
            #r.stdout, r.stderr = r.communicate()
        self.log.debug('Index raster set to "' + str(indexRaster) + '"')
        return indexRaster

    def raster_to_ascii(self,rasterName, IO=1, null_as_zero=False):
        """ Creates a temporary file storing the raster data in ascii format
        (accessable for LifestageTransition processing), and if IO=1 also
        creates a temp file to write the new data to after being processed.
        Returns the names of the temporary files.

        @todo rename to exportRasterToASCII   
        """
        null_char = '*'
        if null_as_zero: null_char = '0'
        imp_cmd = "r.out.ascii -h input=%s output=- null=%s" % (rasterName,null_char)
        data = subprocess.Popen(imp_cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        tempDataFile, tempDataFileName = (tempfile.mkstemp(prefix = 'popMod_inRast_', \
                    suffix='.txt', text=True))
        tempDataFile = os.fdopen(tempDataFile, 'w')
        tempDataFile.write(data.communicate()[0])
        tempDataFile.close()
        if IO==1:
            tempOutDataFile, tempOutDataFileName = (tempfile.mkstemp(prefix='popMod_outRast_', \
                        suffix='.txt', text=True))
            os.close(tempOutDataFile)
            return tempDataFileName, tempOutDataFileName
        else:
            return tempDataFileName

    def index_to_ascii(self,indexRaster):
        """ @todo merge with the above code and generalise """
        # export index to temporary ascii map
        imp_cmd = "r.out.ascii -hi input=%s output=-" % (indexRaster)
        data = subprocess.Popen(imp_cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        tempDataFile, tempDataFileName = (tempfile.mkstemp(prefix='popMod_inIndex_', \
                    suffix='.txt', text=True))
        tempDataFile = os.fdopen(tempDataFile, 'w')
        tempDataFile.write(data.communicate()[0])
        tempDataFile.close()
        # create temporary output filename for ascii index map
        tempOutDataFile, tempOutDataFileName = (tempfile.mkstemp(prefix='popMod_outIndex_', \
                    suffix='.txt', text=True))
        os.close(tempOutDataFile)
        return tempDataFileName, tempOutDataFileName

    def import_ascii_to_raster(self, ascii_fn, raster_fn, nv = None):
        temp_to_rast_cmd = "r.in.ascii --o input=%s output=%s" % \
            (ascii_fn, raster_fn)
        if nv:
            temp_to_rast_cmd += " nv=%s" % str(nv)
        self.run_command(temp_to_rast_cmd)

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

