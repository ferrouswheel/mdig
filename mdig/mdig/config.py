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
""" MDiGConfig class

MDiGConfig contains config information for the command line options used and
loads information from ~/.mdig/mdig.conf

Copyright 2006, Joel Pitt

"""

import os
import sys
import pdb
import logging

# ConfigObj from http://www.voidspace.org.uk/python/configobj.html
#sys.path.append(os.path.join(sys.path[0], 'support'))
# was in support dir, but now expected to be installed as part of
# python... (package python-configobj in Ubuntu)
from mdig.contrib.configobj import ConfigObj

import mdig

if sys.platform == "win32": #pragma: no cover
    # on a Windows port
    try:
        from win32com.shell import shellcon, shell
        home_dir = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0);
        # create mdig path if necessary
        home_dir = os.path.join(home_dir,"mdig");
        if not os.path.isdir(home_dir):
            os.mkdir(home_dir)
        
    except ImportError:
        raise ImportError, "The win32com module could not be found"
else:                                      # else on POSIX box
    home_dir = os.path.join(os.path.expanduser("~"), ".mdig")
    if not os.path.isdir(home_dir):
        os.mkdir(home_dir)
        
logging.getLogger("mdig.config").debug("MDIG config/working dir is " + home_dir)

mdig_config = None

def get_config():
    global mdig_config
    if mdig_config is None:
        mdig_config = MDiGConfig()
        logging.getLogger("mdig.config").debug("Created new MDiGConfig instance")
    return mdig_config

# Get Home dir regardless of OS and use sensible value within Windows
#def getHomeDir() :
    #if sys.platform != 'win32' :
        #return os.path.expanduser( '~' )

    #def valid(path) :
        #if path and os.path.isdir(path) :
            #return True
        #return False
    #def env(name) :
        #return os.environ.get( name, '' )

    #homeDir = env( 'USERPROFILE' )
    #if not valid(homeDir) :
        #homeDir = env( 'HOME' )
        #if not valid(homeDir) :
            #homeDir = '%s%s' % (env('HOMEDRIVE'),env('HOMEPATH'))
            #if not valid(homeDir) :
                #homeDir = env( 'SYSTEMDRIVE' )
                #if homeDir and (not homeDir.endswith('\\')) :
                    #homeDir += '\\'
                #if not valid(homeDir) :
                    #homeDir = 'C:\\'
    #return homeDir

def find_grass_base_dir():
    # TODO find from GRASS environment if it exists
    # find from guessing /usr/local/grass*
    import glob
    opts = []
    if sys.platform == "win32":
        if 'OSGEO4W_ROOT' in os.environ:
            opts = glob.glob(os.path.join(os.environ['OSGEO4W_ROOT'],'apps\\grass\\grass-*'))
    else:
        opts = glob.glob('/usr/local/grass-*')
    if len(opts) > 0: return opts[-1]
    else: return None

def find_grassdb_dir():
    # TODO find from GRASS environment if it exists
    # find from guessing /home/user/src/mdig/test
    my_path = os.path.normpath(os.path.join(home_dir, '..', 'src/mdig/test'))
    if os.path.isdir(my_path): return my_path
    if 'OSGEO4W_ROOT' in os.environ:
        my_path = os.path.normpath(os.path.join(os.environ['OSGEO4W_ROOT'], 'src/mdig/test'))
        if os.path.isdir(my_path): return my_path
    return None

def find_location_dir():
    # TODO find from GRASS environment if it exists
    # find from guessing /home/user/src/mdig/test/grass_location
    my_path = find_grassdb_dir() 
    if my_path:
        to_check = os.listdir(my_path)
        for d in to_check:
            # find a path with a PERMANENT sub dir
            d = os.path.join(my_path,d)
            if os.path.isdir(d) and \
                    os.path.isdir(os.path.join(d,'PERMANENT')):
                return os.path.basename(d)
    return None
 
class MDiGConfig(ConfigObj):
    
    # These options are required and the user will be prompted for them
    required = {
        'GRASS': {
            "GISBASE": find_grass_base_dir,
            "GISDBASE": find_grassdb_dir,
            "LOCATION_NAME": find_location_dir,
        }
    }
    defaults = {
        'GRASS': {
            "GISBASE":'/usr/local/grass-6.4.0RC6',
            "GRASS_GNUPLOT":'gnuplot -persist',
            "GRASS_WIDTH":'640',
            "GRASS_HEIGHT":'480',
            "GRASS_HTML_BROWSER":'firefox',
            "GRASS_PAGER":'cat',
            "GRASS_WISH":'wish',
            "GRASS_PYTHON":'python',
            "GRASS_MESSAGE_FORMAT":'silent',
            "GRASS_TRUECOLOR":'TRUE',
            "GRASS_TRANSPARENT":'TRUE',
            "GRASS_PNG_AUTO_WRITE":'TRUE',
            "GISDBASE": '/home/user/src/mdig/test',
            "LOCATION_NAME": 'grass_location',
            "MAPSET":'PERMANENT'
        },
        'LOGGING': {
            "ansi" :"true"
        },
        'WEB': {
            "host" :"localhost",
            "port" :1444,
            "map_pack_storage" : 1024 # In megabytes
        },
        'OUTPUT': {
            'background_map': 'nz_DEM',
            'output_width': 480,
            'output_height': 640
        }
    }

    # using configobj interface:
    # use has_key("test") to see if config key exists
    # write to write to a file.

    config_file = "mdig.conf"
    config_path = None
    
    show_monitor = False
    overwrite_flag = False
    DEBUG = 0
    
    ## These are the default directories
    # subdir for analysis results
    analysis_dir = "analysis"
    # subdir for exported maps
    maps_dir = "maps"
    # subdir for other output (PNG, movies, none stored analysis)
    output_dir = "output"

    ## These are specific options for how MDiG should run,
    ## and should be specified on the command line. Their
    ## defaults are stored here though, and can be changed
    ## through the config file.
    analysis_filename_base = None
    analysis_print_time = False
    analysis_add_to_xml = True
    
    time = None
    
    model_file = None
    action_keyword = None

    # Admin tools
    remove_null = False
    generate_null = False
    check_maps = False
    move_mapset = None
    ##

    rerun_instances = False
    check_model = True

    # permit migration of model data
    migration_is_allowed = False
    # To keep track of whether a migration actually occurred
    migration_occurred=False
    
    def __init__(self):
        if os.path.isfile(self.config_file):
            self.config_path="./"
        else:
            self.config_path=home_dir
        self.cf_full_path = os.path.join(self.config_path,self.config_file)
        self.prompt_user = False
        if not os.path.isfile(self.cf_full_path): self.prompt_user = True
        # Initialise parent, and create the config file if it doesn't exist
        ConfigObj.__init__(self,self.cf_full_path, create_empty=True)
        self.updates()
        self.add_missing_defaults()
        self.setup()

    def setup(self):
        # setup msys directory if necessary
        if sys.platform == 'win32' and self.has_key("MSYS_BIN"):
            os.environ["PATH"] += ";" + self["MSYS_BIN"]
        self.output_level = 'normal'

    def updates(self):
        """ This function does a variety of things to try to gracefully
        update config files.
        """
        import mdig
        version_change = False
        if "version" not in self:
            # before we started tracking the config file version
            if "ansi" in self:
                self['LOGGING']["ansi"] = self["ansi"]
                del self['ansi']
            if self.has_key("repository"):
                # repository was an old way of storing models and output, now we keep them as
                # part of GRASS mapsets. This copies to the grassdb
                if self.migration_is_allowed: 
                    if len(self["GRASS"]["GISDBASE"]) == 0:
                        sys.stderr.write('No GIS database directory specified, please '+\
                            ' edit %s and update the GRASS->GISDBASE value\n' % self.cf_full_path)
                        sys.exit(mdig.mdig_exit_codes['grass_setup'])
                    import mdig.migrate
                    ret = mdig.migrate.migrate_old_repository(self["repository"]["location"],self["GRASS"]["GISDBASE"])
                    if not ret:
                        sys.exit(mdig.mdig_exit_codes['migrate'])
                    del self["repository"]
                    self.migration_occurred = True
                else:
                    sys.stderr.write("Deprecated MDiG repository detected, please run 'mdig.py migrate'\n")
                    sys.exit(mdig.mdig_exit_codes['migrate'])
            # we only have to give a version here to allow other migration paths
            # to also run...
            self['version']='0'
            version_change=True
        if version_change:
            self['version']=mdig.version
            self.write()

    def add_missing_defaults(self):
        if self.prompt_user:
            print \
"""Can't find an MDiG config file. MDiG will assume this is the first
time you've run MDiG and we'll now run you through the required
values. Push any key to continue, or CTRL-C to abort. """
            raw_input()
        for section in MDiGConfig.defaults:
            # create section if missing
            if not self.has_key(section):
                self[section] = {}
            if self.prompt_user:
                print "Setting up config file section [%s]" % section
            for k in MDiGConfig.defaults[section]:
                if not self[section].has_key(k):
                    # If config file doesn't exist...
                    # we should prompt for some values
                    required = section in MDiGConfig.required \
                            and k in MDiGConfig.required[section]
                    if required:
                        self[section][k] = self.prompt_for_config(section,k,self.prompt_user)
                    else:
                        self[section][k] = MDiGConfig.defaults[section][k]
        if sys.platform == 'win32':
            # Windows doesn't support ansi color codes
            self['LOGGING']['ansi'] = "false"
        self.write()

    def prompt_for_config(self,section,k,fresh):
        guess = None
        if section in MDiGConfig.required \
                and k in MDiGConfig.required[section]:
            guess = MDiGConfig.required[section][k]
        if guess: guess = guess() # guess should be a callable
        if not fresh:
            print "While setting up config, required parameter %s:%s was missing" % (section,k)
        is_done = False
        while not is_done:
            if guess:
                val = raw_input("Enter value for config parameter %s [%s]: " % (k,guess))
            else:
                val = raw_input("Enter value for config parameter %s: " % (k))
            if len(val) == 0:
                if guess:
                    val = guess
                    is_done = True
                else:
                    print "Please enter a value, no default available!"
            else:
                is_done = True
        return val
    
def makepath(path):
    """ creates missing directories for the given path and
        returns a normalized absolute version of the path.

    - if the given path already exists in the filesystem
      the filesystem is not modified.

    - otherwise makepath creates directories along the given path
      using the dirname() of the path. You may append
      a '/' to the path if you want it to be a directory path.

    from holger@trillke.net 2002/03/18
    """
    from os import makedirs
    from os.path import normpath,dirname,exists,abspath

    dpath = normpath(path)
    if not exists(dpath): makedirs(dpath)
    return normpath(abspath(path))
