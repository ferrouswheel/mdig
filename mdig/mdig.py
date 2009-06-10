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
'''MDiG - Modular Dispersal in GIS

command line interface/launcher for MDiG, should be in GRASS environment before
running!

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

import getopt

def usage():
    usage_line = "Usage: mdig.py <action> [options] experiment.xml"
    
    actions_list = ""
    for a in Actions.mdig_actions:
        a_str = a + "\t- " + Actions.mdig_actions[a].description + "\n"
        actions_list += a_str

    print usage_line
    print "\n=== Actions ==="
    print actions_list
    print """Options:
-h (--help) \t Display action specific help

experiment.xml is the file containing the simulation details.
"""

def process_options(argv):
    global logger
    
    model_file = None
    mdig_config = MDiGConfig.getConfig()

    # Remove action keyword first
    action_keyword = None
    if len(argv) >= 1:
        action_keyword = argv[0]
    
    #TODO: add a HelpAction
    the_action = None
    if Actions.mdig_actions.has_key( action_keyword ):
        # Initialise with the class corresponding to the action
        the_action = Actions.mdig_actions[action_keyword]()
    if the_action is not None:
        the_action.parse_options(argv)
        # TODO: extract the logic within process_options and
        # put it here...
    else:
        if action_keyword != "--help" and \
            action_keyword != "-h":
            print "Unknown action %s" % mdig_config.action_keyword
        usage()
        sys.exit(mdig.mdig_exit_codes["ok"])
    return the_action

simulations = []
repository = None
def main(argv):
    global simulations
    global repository
    logger = setupLogger()
    
    mdig_config = MDiGConfig.getConfig()
    repository = ModelRepository.ModelRepository()
    the_action = process_options(argv)
    
    signal.signal(signal.SIGINT, exit_catcher)
    
    # Check for grass environment and set up interface
    grass_interface = GRASSInterface.getG()
    
    #Load model repository 
    if the_action.repository is not None:
        repository = ModelRepository.ModelRepository(the_action.repository)
    models = repository.get_models()
        
    if the_action.preload == True:
        #Load model definition
        if the_action.model_name is not None:
            if the_action.model_name not in models:
                logger.error ( "Model doesn't exist in repository" )
            model_xml_file = models[the_action.model_name]
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
    if GRASSInterface.getG(False) is not None:
        GRASSInterface.getG().clean_up()

    MDiGConfig.getConfig().write()
        
    logger.info("Finished at %s" % repr(datetime.now().ctime()))

def setupLogger():
    logger = logging.getLogger("mdig")
    logger.setLevel(logging.INFO)
    #create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    #create formatter
    formatter = logging.Formatter("%(msecs)d - %(name)s - %(levelname)s - %(message)s")
    #add formatter to ch
    ch.setFormatter(formatter)
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

    
