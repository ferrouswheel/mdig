#!/usr/bin/env python
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
''' MDiG - Modular Dispersal in GIS

Command line interface/launcher for MDiG.

The user should be in GRASS environment before running. Some commands might
work outside of the GRASS env. but no guarantees.

'''

import sys
import os
import pdb
import logging
import random
import signal

from datetime import datetime, timedelta

import mdig
from mdig import Actions
from mdig import MDiGConfig
from mdig import ModelRepository

from mdig import GRASSInterface
from mdig import DispersalModel
from mdig import Displayer

def usage():
    usage_line = "Usage: mdig.py <action> [options] [model_name|model.xml]"
    
    max_length = 0
    for a in Actions.mdig_actions:
        max_length = max(len(a),max_length)
        
    actions_list = []
    for a in Actions.mdig_actions:
        a_str = a + (" "*(max_length - len(a))) + " - " + \
            Actions.mdig_actions[a].description
        actions_list.append(a_str)
    actions_list.sort()

    print usage_line
    print "\n=== Actions ==="
    print "\n".join(actions_list)
    print """Options:
-h (--help) \t Display action specific help

model_name is the name of a model within the repository.
model.xml is the file containing the simulation details.
"""
    print "MDiG using GRASS repository @ " + mdig.repository.db

def process_options(argv):
    global logger
    
    model_file = None
    mdig_config = MDiGConfig.get_config()

    # Remove action keyword first
    action_keyword = None
    if len(argv) >= 1:
        action_keyword = argv[0]
    
    the_action = None
    if Actions.mdig_actions.has_key( action_keyword ):
        # Initialise with the class corresponding to the action
        the_action = Actions.mdig_actions[action_keyword]()
    if the_action is not None:
        the_action.parse_options(argv)
    else:
        if action_keyword != "--help" and \
            action_keyword != "-h" and \
            action_keyword != "help":
            print "Unknown action %s" % mdig_config.action_keyword
        usage()
        sys.exit(mdig.mdig_exit_codes["ok"])
    return the_action

simulations = []  # list of DispersalModels
def main(argv):
    global simulations
    
    # Do a migration of model repository data
    if argv[0] == 'migrate':
        MDiGConfig.MDiGConfig.migration_is_allowed = True
        mdig_config = MDiGConfig.get_config()
        if not mdig_config.migrated:
            print "Nothing to migrate."
        sys.exit(0)
    # Otherwise start up normally
    mdig_config = MDiGConfig.get_config()
    logger = setupLogger(mdig_config["LOGGING"]["ansi"])
    mdig.repository = ModelRepository.ModelRepository()
    the_action = process_options(argv)
    
    signal.signal(signal.SIGINT, exit_catcher)
    
    # Check for grass environment and set up interface
    grass_interface = GRASSInterface.get_g()
    
    # Load model repository 
    if the_action.repository is not None:
        mdig.repository = ModelRepository.ModelRepository(the_action.repository)
    models = mdig.repository.get_models()
        
    if the_action.preload == True:
        # Load model definition
        if the_action.model_names is not None:
            # check that there is only one model for preload
            assert(len(the_action.model_names) == 1)
            m_name = the_action.model_names[0]
            if m_name not in models:
                logger.error("Model " + m_name + " doesn't exist in repository")
                sys.exit(mdig.mdig_exit_codes["model_not_found"])
            model_xml_file = models[m_name]
            exp = DispersalModel.DispersalModel(model_xml_file, the_action)
            simulations.append(exp)
        else:
            logger.error ("No model file specified")
            sys.exit(mdig.mdig_exit_codes["model_not_found"])
        if the_action is not None:
            the_action.do_me(exp)
    else:
        the_action.do_me(None)
    
    exit_cleanup()
    logger.debug("Exiting")

def exit_catcher(sig, stack):
    if sig == signal.SIGINT:
        print("Caught interrupt signal")
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    exit_cleanup()
    #signal.default_int_handler(sig,stack)
    sys.exit(sig)

def exit_cleanup():
    global simulations
    logger = logging.getLogger("mdig")
    
    logger.debug("Cleaning up")
    
    for exp in simulations:
        exp.clean_up()
        exp.save_model()
    if GRASSInterface.get_g(False) is not None:
        GRASSInterface.get_g().clean_up()

    MDiGConfig.get_config().write()
        
    logger.info("Finished at %s" % repr(datetime.now().ctime()))

def setupLogger(color = "false"):
    logger = logging.getLogger("mdig")
    logger.setLevel(logging.DEBUG)

    #create ANSI color formatter
    CSI = "\033["
    TIME = CSI + "0m" + CSI + "32m"
    RESET = CSI + "0m"
    NAME = CSI + "1m" + CSI + "32m"
    LEVEL = CSI + "0m" + CSI + "33m"

    color_formatter = logging.Formatter(
        TIME + "%(asctime)s" + RESET + NAME + " [%(name)s] " + RESET +
        LEVEL + "%(levelname)s" + RESET + ": %(message)s", \
        datefmt='%Y%m%d %H:%M:%S')

    #create non ANSI formatter
    ascii_formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt='%Y%m%d %H:%M:%S')

    # create handlers for each stream
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    #add formatter to ch
    if color == "true":
        ch.setFormatter(color_formatter)
    else:
        ch.setFormatter(ascii_formatter)
    #add ch to logger
    logger.addHandler(ch)
    
    return logger

# call graph
#import pycallgraph
#pycallgraph.settings['include_stdlib']=False
#pycallgraph.start_trace()
if __name__ == "__main__":
    main(sys.argv[1:])
    #pycallgraph.make_dot_graph('test.png')

    
