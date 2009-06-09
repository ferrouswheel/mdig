import sys
import os
import logging
import getopt
from optparse import OptionParser

import mdig
from mdig import MDiGConfig

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

    def get_description(self):
        pass

    def parse_options(self,argv):
        (self.options, args) = self.parser.parse_args(argv[1:])
    
        if len(args) >= 1:
            self.model_name = args[0]
            
        self.act_on_options(self.options)
        self.set_config()
        self.log.info("Model name is " + self.model_name)

    def do_me(self, mdig_model):
        pass

    def set_config(self):
        c = MDiGConfig.getConfig()
        c.overwrite_flag = self.overwrite_flag
        c.remove_null = self.remove_null

class RunAction(Action):

    def __init__(self):
        Action.__init__(self)
        self.time = None
        self.rerun_instances = False
        self.show_monitor = False

        self.parser = OptionParser(version=mdig.version_string,
                description = self.get_description(),
                usage = "%prog run [options] model_name" )
        self.add_options()

    def get_description(self):
        return "Run a model"

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

    def __init__(self):
        Action.__init__(self)
        # Default is to run analysis on all timesteps with maps available.
        self.parser = OptionParser(version=mdig.version_string,
                description = self.get_description(),
                usage = "%prog analysis [options] model_name")
        self.add_options()

    def get_description(self):
        return "Perform analysis on a model and create occupancy envelopes"

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
                choices=("all","final")
                )
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

    def set_config(self):
        Action.set_config(self)
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

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = self.get_description(),
                usage = "%prog add [model definition].xml")
        self.add_options()

    def add_options(self):
        pass

    def get_description(self):
        return "Add a model to the repository based on an xml definition."

    def do_me(self,mdig_model):
        import shutil
        log = logging.getLogger("mdig.action")
        if not os.path.isfile(mdig_model):
            log.error("Model file %s is not a file."%mdig_model)
            sys.exit(5)

        # create dir in repo
        # dirname is from model name
        repo_dir = MDiGConfig.getConfig()["repository"]["location"]
        dm = DispersalModel(mdig_model,setup=False)
        dest_dir = os.path.join(repo_dir,dm.get_name())
        if os.path.exists(dest_dir):
            log.error("A model with the same name as %s already exists. Use " +
                    "'remove' first." % mdig_model)
            sys.exit(5)
        MDiGConfig.getConfig().makepath(dest_dir)
        log.info("Created repo dir for model" %
                dm.get_name)

        # copy xml file to dir
        shutil.copyfile(mdig_model,os.path.join(dest_dir,"model.xml"))

        # set up model directory
        dm.set_base_dir() 
        # change to and create model mapset
        dm.init_mapset()
        GRASSInterface.getG().clean_up()
        
    
class AdminAction(Action):

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = self.get_description(),
                usage = "%prog admin [options] model_name")
        self.add_options()

    def get_description():
        pass

    def get_usage():
        usage_str = mdig.version_string

        usage_str += '''
"admin" action : Perform maintenance and administration tasks

Options:
-r \t remove null bitmasks
-g \t generate null bitmasks
-c \t check all maps are present
-m \t <mapset> move all maps to a new Grass mapset
--o\t overwrite maps
--v\t verbose
--q\t quiet mode'''
        return usage_str

    def parse_options(self, argv):
        try:
            opts, args = getopt.getopt(argv[1:], "horgm:Dv",
                    ["help","remove","generate","move-mapset=","o","v","q"])
        except getopt.GetoptError:
            print self.get_usage()
            sys.exit(mdig.mdig_exit_codes["cmdline_error"])
        
        if len(args) >= 1:
            self.model_name = args[0]
        
        for o,a in opts:
            if o in ("-h", "--help"):
                print self.get_usage()
                sys.exit(mdig.mdig_exit_codes["ok"])
            elif o in ("-r","--remove"):
                self.remove_null = True
            elif o in ("-g","--generate"):
                self.generate_null = True
            elif o in ("-c","--check-maps"):
                self.check_maps = True
            elif o in ("-m","--move-mapset"):
                self.move_mapset = a
            elif o in ("-o", "--o"):
                self.overwrite_flag = True
            elif o in ("-D", "--debug"):
                self.output_level="debug"
                logging.getLogger("mdig").setLevel(logging.DEBUG)
                logging.getLogger("mdig").debug("Debug messages enabled.")
            elif o in ("-v", "--verbose", "--v"):
                if not self.output_level == "debug":
                    self.output_level="verbose"
                    logging.getLogger("mdig").setLevel(logging.INFO)
                    logging.getLogger("mdig").debug("Verbose messages enabled.")
            elif o in ("--q"):
                self.output_level="quiet"
                logging.setLevel(logging.ERROR)

    def do_me(self,mdig_model):
        if self.move_mapset:
            mdig_model.move_mapset(move_mapset)
        if self.remove_null:
            mdig_model.null_bitmask( False )
        if self.generate_null:
            mdig_model.null_bitmask( True )
        if self.check_maps:
            mdig_model.checkInstances()

class WebAction(Action):

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
    "admin": AdminAction,
    "web": WebAction,
    "node": ClientAction
    }

