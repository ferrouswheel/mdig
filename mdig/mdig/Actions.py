import sys
import os
import logging
import getopt

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

    def get_usage(self):
        pass

    def parse_options(self,argv):
        pass

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
        
    def get_usage(self):
        usage_str = mdig.version_string
        
        usage_str += '''
"run" action : Runs an MDiG model

Options:
-h \t help
-t \t maximum real-time to run simulation for
-n \t remove null bitmasks after each simulation
-a \t run all instances, not just incomplete instances
-f \t force - skips the the model check.
-m \t display GRASS monitor
-d \t base directory to save output in
-D \t debug (strongly verbose)
--o\t overwrite maps
--v\t verbose
--q\t quiet mode '''
        return usage_str

    def get_model(self):
        return model_name

    def parse_options(self,argv):
        try:
            opts, args = getopt.getopt(argv[1:], "ht:nafmod:Dv",
                [ "help","time","no-null","all","force","monitor",
                  "overwrite","dir=","debug","verbose","o","v","q" ])
        except getopt.GetoptError:
            print self.get_usage()
            sys.exit(mdig.mdig_exit_codes["cmdline_error"])
    
        if len(args) >= 1:
            self.model_name = args[0]
            
        for o, a in opts:
            if o in ("-h", "--help"):
                print self.get_usage()
                sys.exit(mdig.mdig_exit_codes["ok"])
            elif o in ("-t", "--time"):
                self.time = int(a)
            elif o in ("-n", "--no-null"):
                self.remove_null = True
            elif o in ("-a", "--all"):
                self.rerun_instances = True
            elif o in ("-f", "--force"):
                self.check_model = False
            elif o in ("-m", "--monitor"):
                self.show_monitor = True
            elif o in ("-o", "--overwrite","--o"):
                self.overwrite_flag=1
            elif o in ("-d", "--dir"):
                self.output_dir=a
                if not os.path.isdir(a):
                    self.log.info("Directory %s doesn't exist, attemping to" +
                            " create\n",a)
                    self.analysis_dir = MDiGConfig.makepath(a)
            elif o in ("-D", "--debug"):
                self.output_level="debug"
                logging.getLogger("mdig").setLevel(logging.DEBUG)
                self.log.debug("Debug messages enabled.")
            elif o in ("-v", "--verbose", "--v"):
                if not self.output_level == "debug":
                    self.output_level = "verbose"
                    logging.getLogger("mdig").setLevel(logging.INFO)
                    self.log.info("Verbose messages enabled.")
            elif o in ("--q"):
                self.output_level = "quiet"
                logging.getLogger("mdig").setLevel(logging.ERROR)
        self.set_config()
        self.log.info("Model name is " + self.model_name)

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
        self.analysis_step = "all"
        self.analysis_cmd_file = None
        self.combined_analysis = False
        self.prob_envelope_only = False
        self.analysis_lifestage = None
        self.analysis_filename = None
        self.analysis_print_time = False
        self.analysis_add_to_xml = True
    
    def get_usage(self):
        usage_str = mdig.version_string
        
        usage_str += '''
"analysis" action : Perform a variety of analyses on an already
                    completed MDiG simulation
                    
Options:
-h \t help
-a \t <file> analysis commands specified in file
-s \t <step> step at which to run analyses on ("all" or "final")
-l \t <lifestage> lifestage to analyse ("all" or name of lifestage)
-c \t run a combined analysis. Combine all replications into one 
   \t occupancy map and then analyse. 
-p \t force creation of occupancy envelope across replicates, don't
   \t run analysis.
-f \t <file> specify output filename (will be prepended with replicate
   \t number and variable info)
-t \t prefix file entries with time
-x \t do not record analysis in xml file
-D \t debug (strongly verbose) 
--o\t overwrite maps
--v\t verbose
--q\t quiet mode'''
        return usage_str

    def parse_options(self,argv):
        try:
            opts, args = getopt.getopt(argv[1:], "hsa:f:txopcl:Dv",
                    ["help","analysis-file=","step=","file=","time","no-xml",\
                     "overwrite","combined-analysis","probability-envelope", \
                     "lifestage=","debug","verbose","o","v","q"])
        except getopt.GetoptError:
            print self.get_usage()
            sys.exit(mdig.mdig_exit_codes["cmdline_error"])
        
        if len(args) >= 1:
            self.model_name = args[0]
        
        for o,a in opts:
            if o in ("-h", "--help"):
                print self.get_usage()
                sys.exit(mdig.mdig_exit_codes["ok"])
            elif o in ("-s","--step"):
                if a[0] in ("final","all"): 
                    self.analysis_step = a
                else:
                    self.log.error("Analysis parameter must be 'final' or 'all'")
                    sys.exit(1)
            elif o in ("-a", "--analysis-file"):
                self.analysis_cmd_file = a
            elif o in ("-c", "--combined-analysis"):
                self.combined_analysis = True
            elif o in ("-p", "--probability-envelope"):
                self.prob_envelope_only = True
            elif o in ("-l", "--lifestage"):
                self.analysis_lifestage = a
            elif o in ("-f", "--file"):
                self.analysis_filename = a
            elif o in ("-t", "--time"):
                self.analysis_print_time = True
            elif o in ("-x", "--no-xml"):
                self.analysis_add_to_xml = False
            elif o in ("-o", "--o"):
                self.overwrite_flag = True
            elif o in ("-D", "--debug"):
                self.output_level="debug"
                logging.getLogger("mdig").setLevel(logging.DEBUG)
                self.log.debug("Debug messages enabled.")
            elif o in ("-v", "--verbose", "--v"):
                if not self.output_level == "debug":
                    self.output_level="verbose"
                    logging.getLogger("mdig").setLevel(logging.INFO)
                    self.log.info("Verbose messages enabled.")
            elif o in ("--q"):
                self.output_level="quiet"
                logging.getLogger("mdig").setLevel(logging.ERROR)
        self.set_config()

    def set_config(self):
        Action.set_config(self)
        MDiGConfig.getConfig().analysis_add_to_xml = self.analysis_add_to_xml

    def do_me(self,mdig_model):
        ls = self.analysis_lifestage
        
        # If only a probability envelope is to be created then don't prompt
        # for command
        if not self.prob_envelope_only and self.analysis_cmd_file is None:
            print '''
            ====================================
            Analysis: You can use %0 to represent the current map being looked
            at, %1 to look at the previous saved map, etc. %t for time, %f for
            output file (specified with -f option or generated by MDiG)
            '''
            prompt_str = "Please enter the analysis command to run for " + \
                          "analysis of %s map(s)" % self.analysis_step
            if ls is None:
                prompt_str += ", all lifestages:\n"
            else:
                prompt_str += ", lifestage [%s]:\n" % ls
                    
            self.analysis_command = raw_input(prompt_str)
        
        # If a combined analysis is being run (or a prob. envelope is being
        # created) then generate the combined maps.
        if self.combined_analysis or self.prob_envelope_only:
            self.log.info("Updating probability envelopes")
            
            # force parameter for update_occupancy_envelope means that
            # probability envelopes will be made regardless of whether they
            # already exist.
            if self.analysis_step == "all":
                mdig_model.update_occupancy_envelope( ls,
                        force=self.prob_envelope_only)
            elif self.analysis_step == "final":
                # -1 specifies the last time step
                mdig_model.update_occupancy_envelope(ls, -1, 
                        force=self.prob_envelope_only)
            else:
                self.log.error("Unknown analysis step : %s" %
                        self.analysis_step)
                sys.exit(3)
            
        if not self.prob_envelope_only:
            print "Running analysis command"
            
            commands_to_run = []
            
            if self.analysis_cmd_file is not None:
                # get commands from files
                self.log.warning("Reading analysis commands from files is" + \
                       " not implemented yet.")
                pass
            else:
                # add user prompted command line to the array
                commands_to_run.append(("user",self.analysis_command))
            
            for cmd in commands_to_run:
                
                if self.analysis_step == "all":
                    mdig_model.run_command_on_maps(cmd[1], ls,
                            prob=self.combined_analysis)
                else:
                    # -1 specifies the last time step
                    mdig_model.run_command_on_maps(cmd[1], ls, [-1],
                            prob=self.combined_analysis)
    
class AdminAction(Action):

    def __init__(self):
        Action.__init__(self)

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
    "admin": AdminAction,
    "web": WebAction,
    "node": ClientAction
    }

