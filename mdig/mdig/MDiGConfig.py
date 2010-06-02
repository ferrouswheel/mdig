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
from configobj import ConfigObj

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
 
class MDiGConfig(ConfigObj):
    
    defaults = {
        'GRASS': {
            "GISBASE":'/usr/local/grass-6.4.svn',
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
            "GISDBASE":'',
            "LOCATION_NAME":'',
            "MAPSET":'PERMANENT'
        },
        'LOGGING': {
            "ansi" :"false"
        },
        'WEB': {
            "host" :"localhost",
            "port" :1444
        },
        'OUTPUT': {
            'background_map': "nz_DEM_jacques",
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
        # Initialise parent, and create the config file if it doesn't exist
        ConfigObj.__init__(self,self.cf_full_path, create_empty=True)
        self.updates()
        self.add_missing_defaults()
        self.setup()

    def setup(self):
        # setup msys directory if necessary
        if sys.platform == 'win32' and self.has_key("MSYS_BIN"):
            os.environ["PATH"] += ";" + self["MSYS_BIN"]

    def updates(self):
        """ This function does a variety of things to try to gracefully
        update config files.
        """
        import mdig
        if "version" not in self:
            # before we started tracking the config file version
            if "ansi" in self:
                self['LOGGING']["ansi"] = self["ansi"]
                del self['ansi']
            if self.has_key("repository"):
                # repository was an old way of storing models and output, now we keep them as
                # part of GRASS mapsets. This copies to the grassdb
                migration_is_allowed = True
                if self.migration_is_allowed: 
                    if len(self["GRASS"]["GISDBASE"]) == 0:
                        sys.stderr.write('No GIS database directory specified, please '+\
                            ' edit %s and update the GRASS->GISDBASE value\n' % self.cf_full_path)
                        sys.exit(mdig.mdig_exit_codes['grass_setup'])
                    import mdig.migrate
                    mdig.migrate.migrate_repository(self["repository"]["location"],self["GRASS"]["GISDBASE"])
                    del self["repository"]
                    self.migration_occurred = True
                else:
                    sys.stderr.write("Deprecated MDiG repository detected, please run 'mdig.py migrate'\n")
                    sys.exit(mdig.mdig_exit_codes['migrate'])
            self['version']=mdig.version
            self.write()

    def add_missing_defaults(self):
        for section in MDiGConfig.defaults:
            if not self.has_key(section):
                self[section] = MDiGConfig.defaults[section]
            else:
                for k in MDiGConfig.defaults[section]:
                    if not self[section].has_key(k):
                        self[section][k] = MDiGConfig.defaults[section][k]
        self.write()

    
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
