import sys
import os
import logging
import getopt
from optparse import OptionParser

import mdig
from mdig import MDiGConfig
from mdig import GRASSInterface
from mdig import ROCAnalysis
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
        # maximum number of models that command expects
        self.model_limit = 1
        # whether to overwrite files that already exist
        # Moved to config
        #self.overwrite_flag = False
        # remove null bitmasks (saves disk space but takes time)
        # Moved to config
        #self.remove_null = False
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

    def get_description(self):
        pass

    def parse_options(self,argv):
        (self.options, args) = self.parser.parse_args(argv[1:])
        if self.model_limit is not None and self.model_limit < len(args):
            self.log.error("Too many model names: " + repr(args))
            self.log.error("Expected maximum of " + repr(self.model_limit))
            sys.exit(mdig.mdig_exit_codes["cmdline_error"])
        if len(args) >= 1:
            self.model_names = args
            if len(args) == 1:
                self.log.debug("Model name is " + self.model_names[0])
            else:
                self.log.debug("Model names are " + repr(self.model_names))
        self.act_on_options(self.options)

    def do_me(self, mdig_model):
        pass

class RunAction(Action):
    description = "Run a model"

    def __init__(self):
        Action.__init__(self)
        self.time = None
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
        c = MDiGConfig.getConfig()
        if options.output_dir is not None:
            if not os.path.isdir(options.output_dir):
                self.log.info("Directory %s doesn't exist, attemping to" +
                        " create\n",options.output_dir)
                c.output_dir = \
                    MDiGConfig.makepath(options.output_dir)
            else:
                c.output_dir = options.output_dir
        c.overwrite_flag = self.options.overwrite_flag
        c.remove_null = self.options.remove_null

    def get_model(self):
        return self.model_names[0]

    def do_me(self, mdig_model):
        if self.time is not None:
            self.start_time = datetime.now()
            self.end_time = self.start_time + timedelta(hours=time)
            self.log.debug("Start time %s", self.start_time.ctime())
            self.log.debug("Maximum end time %s", self.end_time.ctime())
        self.log.debug("Executing simulation")
        
        if self.show_monitor:
            mdig_model.add_listener(Displayer.Displayer())
        if self.options.rerun_instances:
            self.log.debug("Resetting model so all replicates will be rerun")
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
                help="Specify output filename (will be prepended with rep " +
                    "number and variable info for the model instance)",
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
        c = MDiGConfig.getConfig()
        c.analysis_add_to_xml = self.options.analysis_add_to_xml
        c.analysis_filename_base = self.options.analysis_filename_base
        c.analysis_print_time = self.options.analysis_print_time
        c.overwrite_flag = self.options.overwrite_flag

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
                sys.exit(mdig.mdig_exit_codes["cmdline_error"])
            
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
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        MDiGConfig.getConfig().overwrite_flag = self.options.overwrite_flag

    def do_me(self,mdig_model):
        import shutil
        log = logging.getLogger("mdig.action")
        if not os.path.isfile(self.model_names[0]):
            log.error("Model file %s is not a file."%self.model_names[0])
            sys.exit(5)

        # create dir in repo
        # dirname is from model name
        repo_dir = MDiGConfig.getConfig()["repository"]["location"]
        dm = DispersalModel(self.model_names[0],setup=False)
        dest_dir = os.path.join(repo_dir,dm.get_name())
        if os.path.exists(dest_dir):
            if self.options.overwrite_flag:
                log.error("A model with the same name as %s already exists. Use " % self.model_names[0] +
                        "'remove' first.")
                sys.exit(mdig.mdig_exit_codes["exists"])
            else:
                log.warning("A model with the same name as %s already exists." +
                        " Overwriting...")
                shutil.rmtree(dest_dir)
        MDiGConfig.makepath(dest_dir)
        log.info("Created repo dir for model " + dm.get_name())

        # copy lifestage transition model file if it exists
        if dm.get_popmod_file() is not None:
            src_file = dm.get_popmod_file()
            # check if this exists, directly and then relative to model file
            if not os.path.exists(src_file):
                src_file = os.path.join(os.path.dirname(self.model_names[0]), src_file)
                if not os.path.exists(src_file):
                    log.error("Can't find internally specified popmod lifestage transition file!")
                    sys.exit(mdig.mdig_exit_codes["missing_popmod"])
            
            shutil.copyfile(src_file,os.path.join(dest_dir,"lifestage_transition.xml"))
            dm.set_popmod_file("lifestage_transition.xml")

        # write dispersal model to new dir 
        #shutil.copyfile(self.model_names[0],os.path.join(dest_dir,"model.xml"))
        dm.save_model(os.path.join(dest_dir,"model.xml"))

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

class InfoAction(Action):
    description = "Display information about a model in the MDiG repository."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = InfoAction.description,
                usage = "%prog info")
        self.check_model = False
        self.add_options()

    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-c","--complete",
                help="check if model is complete and all maps exist",
                action="store_true",
                dest="complete_flag")

    def act_on_options(self,options):
        Action.act_on_options(self,options)

    def do_me(self,mdig_model):
        print repr(mdig_model)
        if self.options.complete_flag:
            mstr=[]
            mstr.append( "Complete: " )
            if self.is_complete(): mstr[-1] += "Yes"
            else: mstr[-1] += "No"
        sys.exit(0)

class ExportAction(Action):
    description = "Export images and movies of simulation."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = ExportAction.description,
                usage = "%prog export [options] model_name")
        self.add_options()
        
    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")
        #self.parser.add_option("-m","--mpeg",
        #        help="Output mpeg compressed movie",
        #        action="store_true",
        #        dest="output_mpeg")
        self.parser.add_option("-g","--gif",
                help="Output animated gif",
                action="store_true",
                dest="output_gif")
        self.parser.add_option("-i","--image",
                help="Output a series of images, one for each population distribution map",
                action="store_true",
                dest="output_image")
        self.parser.add_option("-r","--rep",
                help="Output maps for rep instead of for occupancy envelope",
                action="append",
                type="int",
                dest="reps")
        self.parser.add_option("-l","--lifestage",
                help="Lifestage to analyse (lifestage name or default='all')",
                action="store",
                dest="output_lifestage",
                type="string")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        MDiGConfig.getConfig().overwrite_flag = self.options.overwrite_flag
        if self.options.output_lifestage is None:
            self.options.output_lifestage = "all"
    
    def do_me(self,mdig_model):
        for i in mdig_model.get_instances():
            self.do_instance(i,mdig_model.get_name())

    def do_instance(self,i,model_name):
        # TODO: only overwrite files if -o flag is set
        import OutputFormats
        if not self.options.output_gif and \
            not self.options.output_image:
            self.log.warning("No type for output was specified...")
            sys.exit(0)
        ls = self.options.output_lifestage
        all_maps = []
        if not i.is_complete():
            self.log.error("Instance " + repr(i) + " not complete")
            sys.exit(mdig.mdig_exit_codes["instance_incomplete"])
        base_fn = os.path.join(i.experiment.base_dir,"output")
        if len(self.options.reps) > 0:
            # Run on replicates
            rs = i.replicates
            for r_index in self.options.reps:
                if r_index < 0 or r_index > len(rs):
                    self.log.error("Invalid replicate index." +
                            " Have you 'run' the model first?")
                    sys.exit(mdig.mdig_exit_codes["invalid_replicate_index"])
                r = rs[r_index]
                rep_fn = os.path.join(base_fn, OutputFormats.createFilename(r))
                map_list = []
                for t in r.get_saved_maps(ls):
                    m = r.get_saved_maps(ls)[t]
                    map_list.append(self.create_frame(m,rep_fn + "_" + repr(t),model_name,
                                t, ls))
                self.create_gif(map_list,rep_fn)
                all_maps.extend(map_list)
        else:
            # Run on occupancy envelopes
            base_fn = os.path.join(base_fn,
                    OutputFormats.createFilename(i))
            env = i.get_occupancy_envelopes()
            if env is None:
                self.log.error("No occupancy envelopes available.")
                sys.exit(mdig.mdig_exit_codes["missing_envelopes"])
            map_list = []
            for t in env[ls]:
                m = env[ls][t]
                map_list.append(self.create_frame(m,base_fn + "_" + repr(t),model_name,
                        t, ls))
            self.create_gif(map_list,base_fn)
            all_maps.extend(map_list)
        # If the user just wanted an animated gif, then clean up the images
        if not self.options.output_image:
            for m in all_maps:
                os.remove(m)

    def create_gif(self,maps,fn):
        gif_fn = None
        if self.options.output_gif:
            from subprocess import Popen, PIPE
            gif_fn = fn + "_anim.gif"
            output = Popen("convert -delay 100 " + " ".join(maps)
                + " " + gif_fn, shell=True, stdout=PIPE).communicate()[0]
            if len(output) > 0:
                self.log.info("Convert output:" + output)
        return gif_fn

    def create_frame(self, map_name, output_name, model_name, year, ls):
        g = GRASSInterface.getG()
        g.runCommand("d.mon png1", ignoreOnFail=[1])
        g.runCommand("d.erase")
        #####g.runCommand("d.vect nzcoast_low type=area fcolor=black")
        g.runCommand("r.colors map=" + map_name + " color=byr")
        g.runCommand("d.rast " + map_name + " -o")
        g.runCommand("d.barscale tcolor=0:0:0 bcolor=none at=2,18 -l -t")
        g.runCommand("d.legend " + map_name + " at=5,50,85,90")
        g.runCommand("d.text at=2,90 size=3 text=" + model_name)
        #d.text text="Land-cover model" at=2,87 size=3
        g.runCommand("d.text text=" + year + " at=2,93")
        g.runCommand("d.out.png output=" + output_name + " res=2")
        return output_name + ".png"
    
class ROCAction(Action):
    description = "Create Receiver Operating Characteristic curves for " + \
        "occupancy envelopes and calculate AUC."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = ROCAction.description,
                usage = "%prog roc [options] model_name1 model_name2 ...")
        # Can theoretically run on any number of models
        self.model_limit = None
        self.preload = False
        self.add_options()
        
    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")
        self.parser.add_option("-b","--bootstraps",
                help="Number of resamplings to use for creating statistics",
                action="store",
                dest="bootstraps")
        self.parser.add_option("-V","--vuc",
                help="Calculate Volume Under the Curve",
                action="store_true",
                dest="calc_vuc")
        self.parser.add_option("-a","--auc",
                help="Calculate Area Under the Curve",
                action="store_true",
                dest="calc_auc")
        self.parser.add_option("--graph-auc",
                help="Graph the change in AUC over time",
                action="store_true",
                dest="graph_auc")
        self.parser.add_option("--graph-roc",
                help="Graph yearly ROC curves (creates one for each year and replicate)",
                action="store_true",
                dest="graph_roc")
        self.parser.add_option("-x","--start",
                help="Start time to calculate ROC/AUC for",
                action="store",
                type="int",
                dest="start_time")
        self.parser.add_option("-y","--end",
                help="End time to calculate ROC/AUC for",
                action="store",
                type="int",
                dest="end_time")
        self.parser.add_option("-s","--sites",
                help="The vector that will contain the sites to compare " +
                    "performance with (required).",
                action="store",
                dest="sites_vector",
                type="string")
        self.parser.add_option("-m","--mask",
                help="The raster map used as the limit for where random " +
                "absences can go and used for the total area to compare to.",
                action="store",
                dest="area_mask",
                type="string")
        self.parser.add_option("-l","--lifestage",
                help="Lifestage to analyse (lifestage name or default='all')",
                action="store",
                dest="lifestage",
                type="string")
        self.parser.add_option("-d","--dir",
                help="Base directory to save output in (don't use repository)",
                action="store",
                dest="output_dir",
                type="string")
        self.parser.add_option("-t","--tags",
                help="List of comma separated tags for labelling each model within graph legends",
                action="store",
                dest="model_tags",
                type="string")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        MDiGConfig.getConfig().overwrite_flag = self.options.overwrite_flag
        if self.options.lifestage is None:
            self.options.lifestage = "all"
        if self.options.sites_vector is None:
            self.log.error("No sites vector provided.")
            sys.exit(mdig.mdig_exit_codes["cmdline_error"])
        if self.options.area_mask is None:
            self.log.error("No area mask specified.")
            sys.exit(mdig.mdig_exit_codes["cmdline_error"])
        if self.options.output_dir is not None:
            if not os.path.isdir(options.output_dir):
                self.log.info("Directory %s doesn't exist, attemping to" +
                        " create\n",options.output_dir)
                MDiGConfig.makepath(options.output_dir)
        else:
            self.options.output_dir = "."
        if self.options.model_tags is not None:
            tags = self.options.model_tags.split(",")
            if len(tags) != len(self.model_names):
                self.log.error("Number of tags given not the same as number "+\
                        " of models.")
                sys.exit(mdig.mdig_exit_codes["cmdline_error"])
            self.options.model_tags = tags
    
    def do_me(self,mdig_model):
        self.ROC = ROCAnalysis.ROCAnalysis(self.model_names,self.options)
        self.ROC.run()


class AdminAction(Action):
    description = "Perform miscellaneous administative tasks"

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = AdminAction.description,
                usage = "%prog admin [options] model_name")
        self.add_options()

    def add_options(self):
        Action.add_options(self)
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
    "export": ExportAction,
    "web": WebAction,
    "node": ClientAction,
    "info": InfoAction,
    "roc": ROCAction
    }

