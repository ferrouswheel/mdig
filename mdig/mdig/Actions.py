import sys
import os
import logging
import getopt
from optparse import OptionParser

import mdig
from mdig import MDiGConfig
from mdig import GRASSInterface
from mdig.DispersalModel import DispersalModel

from datetime import datetime, timedelta

class Action:

    def __init__(self):
        # The model name that the action is being performed on
        self.model_name = None
        # check that model definition is consistent and that all maps exist
        self.check_model = True
        # The model repository
        self.repository = None
        # The models directory is used for output if this isn't set
        self.output_dir = None
        # output_level is one of: quiet, normal, verbose, debug
        self.output_level = "normal"
        # whether to overwrite files that already exist
        self.overwrite_flag = False
        # remove null bitmasks (saves disk space but takes time)
        self.remove_null = False
        # Whether do_me expects a DispersalModel from self.model_name to be
        # loaded first
        self.preload = True
        self.log = logging.getLogger("mdig.action")

    def add_options(self):
        self.parser.add_option("-D","--debug",
                help="Debugging output",
                action="store_const",
                dest="output_level",
                const="debug")
        self.parser.add_option("-v","--verbose",
                help="Verbose output",
                action="store_const",
                dest="output_level",
                const="verbose")
        self.parser.add_option("-q","--quiet",
                help="Suppress output",
                action="store_const",
                dest="output_level",
                const="quiet")
    
    def act_on_options(self,options):
        if options.output_level == "debug":
            logging.getLogger("mdig").setLevel(logging.DEBUG)
            self.log.debug("Debug messages enabled.")
        elif options.output_level == "verbose":
            self.output_level = "verbose"
            logging.getLogger("mdig").setLevel(logging.INFO)
            self.log.info("Verbose messages enabled.")
        elif options.output_level == "quiet":
            self.output_level = "quiet"
            logging.getLogger("mdig").setLevel(logging.ERROR)
        c = MDiGConfig.getConfig()
        c.overwrite_flag = self.overwrite_flag
        c.remove_null = self.remove_null

    def get_description(self):
        pass

    def parse_options(self,argv):
        (self.options, args) = self.parser.parse_args(argv[1:])
    
        if len(args) >= 1:
            self.model_name = args[0]
            
        self.act_on_options(self.options)
        self.log.info("Model name is " + self.model_name)

    def do_me(self, mdig_model):
        pass

class RunAction(Action):
    description = "Run a model"

    def __init__(self):
        Action.__init__(self)
        self.time = None
        self.rerun_instances = False
        self.show_monitor = False

        self.parser = OptionParser(version=mdig.version_string,
                description = RunAction.description,
                usage = "%prog run [options] model_name" )
        self.add_options()

    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-t","--runtime",
                help="Maximum real-time to run simulations for.",
                action="store",
                dest="time",
                type="int")
        self.parser.add_option("-n","--no-null",
                help="Remove null bitmasks after creating maps",
                action="store_true",
                dest="remove_null")
        self.parser.add_option("-a","--all",
                help="Rerun all instances, not just those that are incomplete",
                action="store_true",
                dest="rerun_instances")
        self.parser.add_option("-f","--force",
                help="Skip the model check",
                action="store_false",
                dest="check_model")
        self.parser.add_option("-m","--monitor",
                help="Display grass monitor or a window to view simulation progress",
                action="store_true",
                dest="show_monitor")
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")
        self.parser.add_option("-d","--dir",
                help="Base directory to save output in (don't use repository)",
                action="store",
                dest="output_dir",
                type="string")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        if options.output_dir is not None:
            if not os.path.isdir(options.output_dir):
                self.log.info("Directory %s doesn't exist, attemping to" +
                        " create\n",options.output_dir)
                MDiGConfig.getConfig().output_dir = \
                    MDiGConfig.makepath(options.output_dir)
            else:
                MDiGConfig.getConfig().output_dir = options.output_dir

    def get_model(self):
        return model_name

    def do_me(self, mdig_model):
        if self.time is not None:
            self.start_time = datetime.now()
            self.end_time = self.start_time + timedelta(hours=time)
            self.log.debug("Start time %s", self.start_time.ctime())
            self.log.debug("Maximum end time %s", self.end_time.ctime())
        self.log.debug("Executing simulation")
        
        if self.show_monitor:
            mdig_model.add_listener(Displayer.Displayer())
        if self.rerun_instances:
            mdig_model.resetInstances()
        mdig_model.run()

class AnalysisAction(Action):
    description = "Perform analysis on a model and create occupancy envelopes"

    def __init__(self):
        Action.__init__(self)
        # Default is to run analysis on all timesteps with maps available.
        self.parser = OptionParser(version=mdig.version_string,
                description = AnalysisAction.description,
                usage = "%prog analysis [options] model_name")
        self.add_options()

    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-a","--analysis",
                help="Load analysis command from a file rather than " +
                    "prompting user",
                action="store",
                dest="analysis_cmd_file",
                type="string")
        self.parser.add_option("-s","--step",
                help="The interval at which to run analysis on ('all' or " +
                    "'final')",
                action="store",
                dest="analysis_step",
                type="choice",
                choices=("all","final"),
                default="all")
        self.parser.add_option("-l","--lifestage",
                help="Lifestage to analyse (lifestage name or default='all')",
                action="store",
                dest="analysis_lifestage",
                type="string")
        self.parser.add_option("-c","--occupancy",
                help="Run analysis on occupancy maps instead of replicate " +
                "maps. Will generate them if necessary.",
                action="store_true",
                dest="combined_analysis")
        self.parser.add_option("-p","--occupancy-only",
                help="Just create occupancy envelopes, don't run analysis",
                action="store_true",
                dest="prob_envelope_only")
        self.parser.add_option("-f","--out-file",
                help="Specify output filename (will be prepended with rep number" +
                "and variable info for the model instance)",
                action="store",
                dest="analysis_filename_base",
                type="string")
        self.parser.add_option("-t","--add-time",
                help="Prefix output file appends with the simulation time.",
                action="store_true",
                dest="analysis_print_time")
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")
        self.parser.add_option("-x","--no-xml",
                help="Do not record analysis in xml file (don't manage " +
                "output with MDiG)",
                action="store_false",
                dest="analysis_add_to_xml")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        MDiGConfig.getConfig().analysis_add_to_xml = \
            self.options.analysis_add_to_xml
        MDiGConfig.getConfig().analysis_filename_base = \
            self.options.analysis_filename_base
        MDiGConfig.getConfig().analysis_print_time = \
            self.options.analysis_print_time

    def do_me(self,mdig_model):
        ls = self.options.analysis_lifestage
        
        # If only a probability envelope is to be created then don't prompt
        # for command
        if not self.options.prob_envelope_only and \
                self.options.analysis_cmd_file is None:
            print '''
            ====================================
            Analysis: You can use %0 to represent the current map being looked
            at, %1 to look at the previous saved map, etc. %t for time, %f for
            output file (specified with -f option or generated by MDiG)
            '''
            prompt_str = "Please enter the analysis command to run for " + \
                          "analysis of %s map(s)" % self.options.analysis_step
            if ls is None:
                prompt_str += ", all lifestages:\n"
            else:
                prompt_str += ", lifestage [%s]:\n" % ls
                    
            self.analysis_command = raw_input(prompt_str)
        
        # If a combined analysis is being run (or a prob. envelope is being
        # created) then generate the combined maps.
        if self.options.combined_analysis or self.options.prob_envelope_only:
            self.log.info("Updating probability envelopes")
            
            # force parameter for update_occupancy_envelope means that
            # probability envelopes will be made regardless of whether they
            # already exist.
            if self.options.analysis_step == "all":
                mdig_model.update_occupancy_envelope( ls,
                        force=self.options.prob_envelope_only)
            elif self.options.analysis_step == "final":
                # -1 specifies the last time step
                mdig_model.update_occupancy_envelope(ls, -1, 
                        force=self.options.prob_envelope_only)
            else:
                self.log.error("Unknown analysis step : %s" %
                        self.options.analysis_step)
                sys.exit(3)
            
        if not self.options.prob_envelope_only:
            print "Running analysis command"
            
            commands_to_run = []
            
            if self.options.analysis_cmd_file is not None:
                # get commands from files
                self.log.warning("Reading analysis commands from files is" + \
                       " not implemented yet.")
                pass
            else:
                # add user prompted command line to the array
                commands_to_run.append(("user",self.analysis_command))
            
            for cmd in commands_to_run:
                
                if self.options.analysis_step == "all":
                    mdig_model.run_command_on_maps(cmd[1], ls,
                            prob=self.options.combined_analysis)
                else:
                    # -1 specifies the last time step
                    mdig_model.run_command_on_maps(cmd[1], ls, [-1],
                            prob=self.options.combined_analysis)

class AddAction(Action):
    description = "Add a model to the repository based on an xml definition."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = AddAction.description,
                usage = "%prog add [model definition].xml")
        self.add_options()
        self.preload = False

    def add_options(self):
        Action.add_options(self)

    def do_me(self,mdig_model):
        import shutil
        log = logging.getLogger("mdig.action")
        if not os.path.isfile(self.model_name):
            log.error("Model file %s is not a file."%self.model_name)
            sys.exit(5)

        # create dir in repo
        # dirname is from model name
        repo_dir = MDiGConfig.getConfig()["repository"]["location"]
        dm = DispersalModel(self.model_name,setup=False)
        dest_dir = os.path.join(repo_dir,dm.get_name())
        if os.path.exists(dest_dir):
            log.error("A model with the same name as %s already exists. Use " % self.model_name +
                    "'remove' first.")
            sys.exit(5)
        MDiGConfig.makepath(dest_dir)
        log.info("Created repo dir for model " + dm.get_name())

        # copy xml file to dir
        shutil.copyfile(self.model_name,os.path.join(dest_dir,"model.xml"))

        # set up model directory
        dm.set_base_dir() 
        # change to and create model mapset
        dm.init_mapset()
        GRASSInterface.getG().clean_up()
        
class ListAction(Action):
    description = "List the models currently in MDiG repository."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = ListAction.description,
                usage = "%prog list")
        self.add_options()
        self.preload = False

    def add_options(self):
        pass

    def parse_options(self,options):
        pass

    def do_me(self,mdig_model):
        from textwrap import TextWrapper
        import re
        indent_amount = 30
        models = mdig.repository.get_models()
        print "Models in the MDiG repository"
        print "-----------------------------"
        ms=models.keys()[:]
        ms.sort()
        for m in ms:
            dm = DispersalModel(models[m],setup=False)
            tw = TextWrapper(expand_tabs = False, replace_whitespace = True )
            tw.initial_indent = " "*4
            tw.subsequent_indent = " "*4
            desc = dm.get_description()
            desc = re.sub("[\\s\\t]+"," ",desc)
            desc = tw.fill(desc)
            print "" + m + ":\n" + desc
        sys.exit(0)
    
class AdminAction(Action):
    description = "Perform miscellaneous administative tasks"

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = AdminAction.description,
                usage = "%prog admin [options] model_name")
        self.add_options()

    def add_options(self):
        Admin.add_options(self)
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")
        self.parser.add_option("-r","--remove-null",
                help="Remove null bitmasks from raster maps",
                action="store_true",
                dest="remove_null")
        self.parser.add_option("-g","--generate",
                help="Generate null bitmasks for raster maps",
                action="store_true",
                dest="generate_null")
        self.parser.add_option("-c","--check-maps",
                help="Check all maps for the model are present",
                action="store_true",
                dest="check_maps")
        self.parser.add_option("-m","--move-mapset",
                help="Check all maps for the model are present",
                action="store",
                type="string",
                dest="move_mapset")

    def do_me(self,mdig_model):
        if self.options.move_mapset:
            mdig_model.move_mapset(move_mapset)
        if self.remove_null:
            mdig_model.null_bitmask( False )
        if self.generate_null:
            mdig_model.null_bitmask( True )
        if self.check_maps:
            mdig_model.checkInstances()

class WebAction(Action):
    description = "Run a webserver that allows interaction with MDiG"

    def __init__(self):
        Action.__init__(self)
        
    def get_usage(self):
        usage_str = mdig.version_string
    
        usage_str += '''
        "web" action : Run a webserver that allows interaction with MDig
        
        NOT IMPLEMENTED
        '''
        return usage_str

    def parse_options(self, argv):
        print self.get_usage()
        sys.exit(mdig.mdig_exit_codes["not_implemented"])
    
class ClientAction(Action):
    description = "Runs MDiG as a node in a distributed instance of MDiG"

    def __init__(self):
        Action.__init__(self)

    def get_usage(self):
        usage_str = mdig.version_string
    
        usage_str += '''
        "client" action : Runs MDiG as a node in a distributed instance of MDiG
        
        NOT IMPLEMENTED
        '''
        return usage_str
            
    def parse_options(self, argv):
        print self.get_usage()
        sys.exit(mdig.mdig_exit_codes["not_implemented"])
    
mdig_actions = {
    "run": RunAction,
    "analysis": AnalysisAction,
    "add": AddAction,
    "list": ListAction,
    "admin": AdminAction,
    "web": WebAction,
    "node": ClientAction
    }

