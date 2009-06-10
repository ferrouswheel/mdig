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

if sys.platform == "win32":                # on a Windows port
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

def getConfig():
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
    
    def __init__(self):
        if os.path.isfile(self.config_file):
            self.config_path="./"
        else:
            self.config_path=home_dir
        # Initialise parent, and create the config file if it doesn't exist
        ConfigObj.__init__(self,"/".join([self.config_path,self.config_file]), \
                create_empty=True)
        # setup msys directory if necessary
        if sys.platform == 'win32' and self.has_key("MSYS_BIN"):
            os.environ["PATH"] += ";" + self["MSYS_BIN"]
        if self.has_key("repository") is False:
            repo_dir = os.path.join(home_dir,"mdig_repos")
            logging.getLogger("mdig").warning("No repository location defined. "
                    + "Using " + repo_dir + " but "
                    + "you'll probably want to change this.")
            self["repository"] = {
                "location" : repo_dir }
            if not os.path.exists(repo_dir):
                os.makedirs(repo_dir)
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
