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
"""
MDiG - Modular Dispersal in GIS
Command line interface/launcher for MDiG.
"""

import sys
import logging
import signal

from datetime import datetime

import mdig
from mdig import actions
from mdig import config
from mdig import modelrepository

from mdig import grass
from mdig import model

def usage(db):
    usage_line = mdig.version_string + "\n"
    usage_line += "Usage: mdig.py <action> [options] [model_name|model.xml]"
    
    max_length = 0
    for a in actions.mdig_actions:
        max_length = max(len(a),max_length)
        
    actions_list = []
    for a in actions.mdig_actions:
        a_str = a + (" "*(max_length - len(a))) + " - " + \
            actions.mdig_actions[a].description
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
    print "MDiG repository @ " + db

def process_options(argv):
    global logger
    
    mdig_config = config.get_config()

    # Remove action keyword first
    action_keyword = None
    if len(argv) >= 1:
        action_keyword = argv[0]
    
    the_action = None
    if actions.mdig_actions.has_key( action_keyword ):
        # Initialise with the class corresponding to the action
        the_action = actions.mdig_actions[action_keyword]()
    if the_action is not None:
        the_action.parse_options(argv)
    else:
        if action_keyword != "--help" and \
            action_keyword != "-h" and \
            action_keyword != "help":
            print "Unknown action '%s'" % action_keyword
        usage(mdig_config["GRASS"]["GISDBASE"])
        sys.exit(mdig.mdig_exit_codes["ok"])
    return the_action

def do_migration(args):
    help_str = "Use 'mdig.py migrate old_repo_dir grassdb' to manually migrate a separate mdig/GISDBASE repository"
    help_str += "or 'mdig.py migrate repo_dir' to manually migrate an already merged repository"
    if len(args) == 1 and args[0] in ['-h','--help']:
        print help_str
        sys.exit(0)
    if len(args) == 0:
        config.MDiGConfig.migration_is_allowed = True
        mdig_config = config.get_config()
        if not mdig_config.migration_occurred:
            print "Nothing to migrate within mdig.conf"
            print help_str
    elif len(args) == 1:
        import mdig.migrate
        print "Migrating repository %s" % args[0]
        mdig.migrate.migrate_repository(args[0])
    elif len(args) == 2:
        import mdig.migrate
        print "Old repository: %s" % args[0]
        print "GRASSDB destination: %s" % args[1]
        mdig.migrate.migrate_old_repository(args[0],args[1])
    else:
        print "Syntax error, just use 'mdig.py migrate <grassdb>'; or"
        print "Use 'mdig.py migrate <grassdb>' to manually " + \
                "migrate a repository."
        print "Use 'mdig.py migrate <old_repo_dir> <grassdb>' to manually " + \
                "migrate an old style repository."
    sys.exit(0)

simulations = []  # list of DispersalModels
def main(argv):
    global simulations
    
    # Do a migration of model repository data
    if len(argv) > 0 and argv[0] == 'migrate':
        do_migration(argv[1:])

    # Otherwise start up normally
    # set up logger
    logger, loghandler = setup_logger()
    # get config
    mdig_config = config.get_config()
    # set ansi logging if enabled
    ansi_bool_string = mdig_config["LOGGING"]["ansi"]
    if ansi_bool_string == "true":
        set_log_formatter(loghandler, True)

    the_action = process_options(argv)
    # We can't rely on logging before this point as process_options
    # determines whether to enable debug level messages
    logging.getLogger("mdig.config").debug("Using MDIG config file " + mdig_config.cf_full_path)
    
    signal.signal(signal.SIGINT, exit_catcher)
    
    # Load model repository 
    if the_action.repository is not None:
        mdig_config["GRASS"]["GISDBASE"] = the_action.repository
    if the_action.location is not None:
        mdig_config["GRASS"]["LOCATION_NAME"] = the_action.location
    try:
        if the_action.init_repository:
            mdig.repository = modelrepository.ModelRepository()
            models = mdig.repository.get_models()
        if the_action.init_grass:
            # Check for grass environment and set up interface
            grass.get_g()
    except grass.EnvironmentException, e:
        logger.error("Failed to initialize due to environment error: %s" % str(e))
        logger.error("Perhaps check your config file? (%s)" % mdig_config.cf_full_path )
        sys.exit(1)
        
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
            exp = model.DispersalModel(model_xml_file, the_action)
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
    
    # clean up simulations and save changes
    for exp in simulations:
        exp.clean_up()
        exp.save_model()

    # clean up web server 
    from mdig.webui import shutdown_webapp
    shutdown_webapp()

    # clean up GRASS environment
    if grass.get_g(False) is not None:
        grass.get_g().clean_up()

    # save config changes
    config.get_config().write()

    from mdig.tempresource import trm
    trm.cleanup()

    logger.debug("Finished at %s" % repr(datetime.now().ctime()))

def setup_logger():
    logger = logging.getLogger("mdig")
    logger.setLevel(logging.DEBUG)

    # create handlers for each stream
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    set_log_formatter(ch,False)

    #add streamhandler to logger
    logger.addHandler(ch)
    
    return logger, ch

def set_log_formatter(stream_handler, color = False):
    if color:
        #create ANSI color formatter
        CSI = "\033["
        TIME = CSI + "0m" + CSI + "32m"
        RESET = CSI + "0m"
        NAME = CSI + "1m" + CSI + "32m"
        LEVEL = CSI + "0m" + CSI + "33m"

        formatter = logging.Formatter(
                TIME + "%(asctime)s" + RESET + NAME + " [%(module)s:%(lineno)d] "
                + RESET + LEVEL + "%(levelname)s" + RESET + ": %(message)s",
                datefmt='%Y%m%d %H:%M:%S')
    else:
        #create non ANSI formatter
        formatter = logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                datefmt='%Y%m%d %H:%M:%S')
    stream_handler.setFormatter(formatter)

# call graph
#import pycallgraph
#pycallgraph.settings['include_stdlib']=False
#pycallgraph.start_trace()
if __name__ == "__main__":
    main(sys.argv[1:])
    #pycallgraph.make_dot_graph('test.png')
