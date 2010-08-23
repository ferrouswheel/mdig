import sys
import os
import logging
import getopt
from optparse import OptionParser

import mdig
from mdig import config
from mdig import grass
from mdig import roc
#if sys.platform != "win32":
#    print sys.platform
#    from mdig import ROCanalysis
#    roc_on = True
#else:
#    roc_on = False
#    print "ROC analysis not supported on Windows"

from mdig import displayer
from mdig.model import DispersalModel

from mdig.instance import InvalidLifestageException, \
        InstanceIncompleteException, InvalidReplicateException, NoOccupancyEnvelopesException

from datetime import datetime, timedelta

class Action:

    def __init__(self):
        # The model name that the action is being performed on
        self.model_names = None
        # check that model definition is consistent and that all maps exist
        self.check_model = True
        # The model repository (== GRASS's GISDBASE)
        self.repository = None
        # The model location (== GRASS's LOCATION_NAME)
        self.location = None
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
        # Whether this action appears in the usage information
        self.hidden = False
        # Whether do_me expects a DispersalModel from self.model_name to be
        # loaded first
        self.preload = True
        # Whether to initialise the repository
        self.init_repository = True
        # Whether to initialise the GRASS interface
        self.init_grass = True
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
        self.parser.add_option("-r","--repository",
                help="Set model repository location (GISDBASE)",
                action="store",
                type="string",
                dest="repository",
                default=None)
        self.parser.add_option("-k","--location",
                help="Set model geo location (LOCATION_NAME)",
                action="store",
                type="string",
                dest="location",
                default=None)
    
    def act_on_options(self,options):
        if options.output_level == "debug":
            logging.getLogger("mdig").handlers[0].setLevel(logging.DEBUG)
            self.log.debug("Debug messages enabled.")
        elif options.output_level == "verbose":
            self.output_level = "verbose"
            logging.getLogger("mdig").handlers[0].setLevel(logging.INFO)
            self.log.info("Verbose messages enabled.")
        elif options.output_level == "quiet":
            self.output_level = "quiet"
            logging.getLogger("mdig").handlers[0].setLevel(logging.ERROR)
        # Make the verbosity level globally available through the config object
        config.get_config().output_level = self.output_level
        if options.repository is not None:
            self.repository = options.repository 
            self.log.debug("Repository location manually set to " + options.repository)
        if options.location is not None:
            self.location = options.location
            self.log.debug("GRASS geo location manually set to " + options.location)

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

class RepositoryAction(Action):
    description = "Set/modify the current MDiG repository and location"

    def __init__(self):
        Action.__init__(self)
        self.check_model = False
        self.preload = False
        self.init_repository = False
        self.init_grass = False
        self.parser = OptionParser(version=mdig.version_string,
                description = RepositoryAction.description,
                usage = "%prog repository [options] GISDBASE/LOCATION" )
        self.add_options()
        self.parser.remove_option('-k')
        self.parser.remove_option('-r')

    def parse_options(self,argv):
        (self.options, args) = self.parser.parse_args(argv[1:])
        if len(args) == 1:
            self.repo_dir = args[0]
            self.log.debug("Repo dir specified is " + self.repo_dir)
        else:
            c = config.get_config()
            print "Current repository: " + c['GRASS']['GISDBASE']
            sys.exit(0)

    def do_me(self, mdig_model):
        c = config.get_config()
        gisdbase, location = os.path.split(os.path.abspath(self.repo_dir))
        if not os.path.isdir(gisdbase):
            self.log.error("GISDBASE '%s' is not a directory", gisdbase)
            sys.exit(1)
        if not os.path.isdir(self.repo_dir):
            self.log.error("LOCATION '%s' is not a directory", location)
            sys.exit(1)
        if not os.path.isdir(os.path.join(self.repo_dir,'PERMANENT')):
            self.log.error("LOCATION '%s' doesn't have a PERMANENT mapset." + \
                    " Is this path a proper location within a GRASS database?", location)
            sys.exit(1)
        c['GRASS']['GISDBASE'] = gisdbase
        c['GRASS']['LOCATION_NAME'] = location
        c.write()

class RunAction(Action):
    description = "Run a model"

    def __init__(self):
        Action.__init__(self)
        self.time = None

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
        # Whether lifestage transitions are done by individual, or
        # as a single matrix. Latter is faster but results in fractional
        # population
        self.parser.add_option("-i","--by-individual",
                help="Do lifestage transitions by individual (SLOW)",
                action="store_true",
                dest="ls_trans_individual")
        self.parser.add_option("-z","--ignore-div-by-zero",
                help="Ignore div by zero when carrying out lifestage transitions",
                action="store_true",
                dest="ls_trans_ignore_div_by_zero")
        self.parser.add_option("-d","--dir",
                help="Base directory to save output in (don't use repository)",
                action="store",
                dest="output_dir",
                type="string")
        self.parser.add_option("-s","--reps",
                help="Manually set the number of reps to run (overwrite count specifed in model)",
                action="store",
                dest="reps",
                type="int")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        c = config.get_config()
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
        
        if self.options.show_monitor:
            mdig_model.add_listener(displayer.Displayer())

        if self.options.ls_trans_individual:
            self.log.debug("Calculating lifestage transitions by individual. This is SLOW.")
            for i in mdig_model.get_lifestage_transitions():
                i.by_individual = True
        if self.options.ls_trans_ignore_div_by_zero:
            self.log.debug("Will ignoring division by zero errors in lifestage transition.")
            for i in mdig_model.get_lifestage_transitions():
                i.t_matrix.ignore_div_by_zero = True
        if self.options.reps is not None:
            mdig_model.set_num_replicates(self.options.reps)
        if self.options.rerun_instances:
            self.log.debug("Resetting model so all replicates will be rerun")
            mdig_model.reset_instances()
        elif mdig_model.is_complete():
            self.log.error("Model is up to date (use -a to force reset and rerun instances)")
            sys.exit(mdig.mdig_exit_codes['up_to_date'])
        mdig_model.run()
        time_taken = mdig_model.end_time - mdig_model.start_time
        mdig_model.log_instance_times()
        print "Total time taken: %s" % time_taken

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
        c = config.get_config()
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
            analysis: You can use %0 to represent the current map being looked
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
            self.log.info("Running analysis command")
            
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

class StatsAction(Action):
    description = "Calculate univariate statistics for maps."

    def __init__(self):
        Action.__init__(self)
        # Default is to run analysis on all timesteps with maps available.
        self.parser = OptionParser(version=mdig.version_string,
                description = StatsAction.description,
                usage = "%prog stats [options] model_name")
        self.add_options()

    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-l","--lifestage",
                help="Lifestage to analyse (lifestage name or default='all')",
                action="store",
                dest="analysis_lifestage",
                default="all",
                type="string")
        self.parser.add_option("-c","--occupancy",
                help="Run analysis on occupancy maps instead of replicate " +
                "maps. Will generate them if necessary.",
                action="store_true",
                dest="combined_analysis")
        self.parser.add_option("-f","--out-file",
                help="Specify output filename (will be appended with rep " +
                    "number and the model instance)",
                action="store",
                dest="analysis_filename_base",
                type="string",
                default="stats_")
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")
        self.parser.add_option("-s","--step",
                help="The interval at which to run analysis on ('all' or " +
                    "'final')",
                action="store",
                dest="analysis_step",
                type="choice",
                choices=("all","final"),
                default="all")
        self.parser.add_option("-x","--no-xml",
                help="Do not record analysis in xml file (don't manage " +
                "output with MDiG)",
                action="store_false",
                dest="analysis_add_to_xml")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        c = config.get_config()
        c.analysis_add_to_xml = self.options.analysis_add_to_xml
        c.analysis_filename_base = self.options.analysis_filename_base
        c.overwrite_flag = self.options.overwrite_flag

    def do_me(self,mdig_model):
        ls = self.options.analysis_lifestage
        
        # If a combined analysis is being run (or a prob. envelope is being
        # created) then generate the combined maps.
        if self.options.combined_analysis:
            self.log.info("Updating probability envelopes")
            
            # force parameter for update_occupancy_envelope means that
            # probability envelopes will be made regardless of whether they
            # already exist.
            if self.options.analysis_step == "all":
                mdig_model.update_occupancy_envelope([ls])
            elif self.options.analysis_step == "final":
                # -1 specifies the last time step
                mdig_model.update_occupancy_envelope([ls], -1)
            else:
                self.log.error("Unknown analysis step : %s" %
                        self.options.analysis_step)
                sys.exit(mdig.mdig_exit_codes["cmdline_error"])
            mdig_model.save_model()
            
        self.log.info("Calculating area...")
        
        g=grass.get_g()
        if self.options.combined_analysis:
            if self.options.analysis_step == "all":
                for i in mdig_model.get_instances():
                    self.log.info("Calculating stats for instance %d" % i.get_index())
                    maps = i.get_occupancy_envelopes()[ls]
                    i.change_mapset()
                    stats=g.get_univariate_stats(maps)
                    fn = os.path.split(i.get_occ_envelope_img_filenames(ls=ls,
                            extension=False,gif=True))[:-5]
                    fn = os.path.join(fn[0],self.options.analysis_filename_base + fn[1])
                    self.write_stats_to_file(stats,fn)
            else:
                # just run on last map
                raise NotImplementedError("only supports running all maps current")
        else:
            if self.options.analysis_step == "all":
                for i in mdig_model.get_instances():
                    i.change_mapset()
                    for r in i.replicates:
                        self.log.info("Calculating stats for instance %d, rep %d" % \
                                (i.get_index(), r.r_index))
                        maps = r.get_saved_maps(ls)
                        stats = g.get_univariate_stats(maps)
                        fn = os.path.split(r.get_img_filenames(ls=ls, extension=False,
                                gif=True))[:-5]
                        fn = os.path.join(fn[0],self.options.analysis_filename_base + fn[1])
                        self.write_stats_to_file(stats,fn)
            else:
                # just run on last map
                raise NotImplementedError("only supports running all maps current")

        self.log.info("Output is in: %s" % \
                os.path.join(mdig_model.base_dir,"output"))

    def write_stats_to_file(self,stats,fn):
        c = config.get_config()
        if os.path.isfile(fn):
            if c.overwrite_flag:
                os.remove(fn)
            else:
                raise Exception("File %s already exists, -o to overwrite" % fn)
        expected=['n','null_cells','cells','min','max','range','mean', \
                 'mean_of_abs', 'stddev', 'variance', 'coeff_var', 'sum']
        f = open(fn,'w')
        f.write('time,' + ','.join(expected))
        f.write('\r\n')
        times = stats.keys()
        times.sort()
        for t in times:
            f.write(str(t))
            for stat_name in expected:
                if stat_name in stats[t]:
                    f.write(',%f' % stats[t][stat_name])
                else:
                    # value missing
                    f.write(',')
            f.write('\r\n')
        f.close()

class ResetAction(Action):
    description = "Reset the model. Delete all prior instances/replicates."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = ResetAction.description,
                usage = "%prog reset <path/model.xml>")
        self.add_options()

    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-f","--force",
                help="Don't prompt first",
                action="store_true",
                dest="force")
        self.parser.add_option("-s","--soft",
                help="Do a soft reset, just forget replicates and reuse mapsets.",
                action="store_true",
                dest="soft")

    def act_on_options(self,options):
        Action.act_on_options(self,options)

    def do_me(self,mdig_model):
        if not self.options.force:
            ans = raw_input('This will delete all simulation output, are you sure? ')
            if ans.lower() not in ['y', 'yes']:
                print "Abort"
                return
        if self.options.soft:
            mdig_model.reset_instances()
        else:
            mdig_model.hard_reset()
        mdig_model.save_model()
        print "Model %s reset." % mdig_model.get_name()
        
class AddAction(Action):
    description = "Add a model to the repository based on an xml definition."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = AddAction.description,
                usage = "%prog add <path/model.xml>")
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
        config.get_config().overwrite_flag = self.options.overwrite_flag

    def do_me(self,mdig_model):
        for m in self.model_names:
            mdig.repository.add_model(m)
        grass.get_g().clean_up()
        
class RemoveAction(Action):
    description = "Remove a model from the repository and delete mapset."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = RemoveAction.description,
                usage = "%prog remove <model name>")
        self.add_options()
        self.preload = False

    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-f","--force",
                help="Force removal, don't check with user",
                action="store_true",
                dest="force_flag")

    def act_on_options(self,options):
        Action.act_on_options(self,options)

    def do_me(self,mdig_model):
        for m in self.model_names:
            mdig.repository.remove_model(m,force=self.options.force_flag)
        
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
        Action.add_options(self)

    def parse_options(self,argv):
        (self.options, args) = self.parser.parse_args(argv[1:])
        Action.act_on_options(self,self.options)

    def do_me(self,mdig_model):
        from textwrap import TextWrapper
        import re
        indent_amount = 30
        models = mdig.repository.get_models()
        title_str = "Models in MDiG GRASS db @ " + mdig.repository.db
        print "-"*len(title_str)
        print title_str
        print "model_name [location]"
        print "    description"
        print "-"*len(title_str)
        ms=models.keys()[:]
        ms.sort()
        for m in ms:
            try:
                dm = DispersalModel(models[m],setup=False)
                tw = TextWrapper(expand_tabs = False, replace_whitespace = True )
                tw.initial_indent = " "*4
                tw.subsequent_indent = " "*4
                desc = dm.get_description()
                desc = re.sub("[\\s\\t]+"," ",desc)
                desc = tw.fill(desc)
                loc = dm.get_location()
                if not loc:
                    loc = dm.infer_location()
                if not loc:
                    loc = "unknown"
                print "%s [%s]:\n%s" % (m,loc,desc)
            except mdig.model.ValidationError, e:
                pass
        sys.exit(0)

class InfoAction(Action):
    description = "Display information about a model in the MDiG repository."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = InfoAction.description,
                usage = "%prog info <model_name>")
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
        print str(mdig_model)
        if self.options.complete_flag:
            mstr=[]
            mstr.append( "Complete: " )
            if mdig_model.is_complete(): mstr[-1] += "Yes"
            else: mstr[-1] += "No"
            print mstr
        sys.exit(0)

class ExportAction(Action):
    description = "Export images and movies of simulation."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = ExportAction.description,
                usage = "%prog export [options] <model_name>")
        self.add_options()
        self.listeners = []
        self.float64 = False
        
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
        self.parser.add_option("-m","--mappack",
                help="Output a zip file with exported maps",
                action="store_true",
                dest="output_map_pack")
        self.parser.add_option("-p","--rep",
                help="Output maps for rep instead of for occupancy envelope",
                action="append",
                type="int",
                dest="reps")
        self.parser.add_option("-l","--lifestage",
                help="Lifestage to analyse (lifestage name or default='all')",
                action="store",
                dest="output_lifestage",
                type="string")
        self.parser.add_option("-j","--instance",
                help="Export only instances specified (export all by default)",
                action="append",
                type="int",
                dest="instances")
        self.parser.add_option("-b","--background",
                help="Rast map to overlay pop. distributions on.",
                action="store",
                dest="background",
                type="string")
        self.parser.add_option("-x","--width",
                help="Set width of output image.",
                action="store",
                type="int",
                dest="width")
        self.parser.add_option("-y","--height",
                help="Set height of output image.",
                action="store",
                type="int",
                dest="height")
        self.parser.add_option("-d","--dir",
                help="Output dir to export to (default is model_mapset/mdig/output)",
                action="store",
                dest="outdir",
                type="string")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        c = config.get_config()
        c.overwrite_flag = self.options.overwrite_flag
        if self.options.output_lifestage is None:
            self.options.output_lifestage = "all"
        if self.options.width is None:
            self.options.width = c["OUTPUT"]["output_width"]
        if self.options.height is None:
            self.options.height = c["OUTPUT"]["output_height"]
        if self.options.background is None:
            self.options.background = c["OUTPUT"]["background_map"]
        if self.options.outdir is not None:
            if not os.path.isdir(self.options.outdir):
                sys.exit("No such output dir: %s" % self.options.outdir)
    
    def do_me(self,mdig_model):
        output_images = self.options.output_gif or self.options.output_image 
        if not (output_images or self.options.output_map_pack):
            self.log.error("No type for output was specified...")
            sys.exit("No type for output was specified...")
        # Get the instance objects that we are exporting
        if self.options.instances is None:
            # either all instances
            instances = mdig_model.get_instances()
        else:
            # or we convert instance indices to instance objects
            instances = []
            all_instances = mdig_model.get_instances()
            for i in self.options.instances:
                try:
                    instances.append(all_instances[i])
                except IndexError,e:
                    self.log.error("Bad instance index specified")
                    sys.exit("Bad instance index specified")
                except TypeError,e:
                    self.log.error("Bad instance index specified")
                    sys.exit("Bad instance index specified")

        show_output = config.get_config().output_level == "normal"
        for i in instances:
            try:
                if show_output:
                    if self.options.output_map_pack:
                        print "Creating map pack for instance %d" % i.get_index()
                    elif output_images:
                        print "Creating images for instance %d" % i.get_index()
                self.do_instance(i)
            except InvalidLifestageException, e:
                sys.exit(mdig.mdig_exit_codes["invalid_lifestage"])
            except InstanceIncompleteException, e:
                sys.exit(mdig.mdig_exit_codes["instance_incomplete"])
            except InvalidReplicateException, e:
                sys.exit(mdig.mdig_exit_codes["invalid_replicate_index"])
            except NoOccupancyEnvelopesException, e:
                sys.exit(mdig.mdig_exit_codes["missing_envelopes"])
            except Exception, e:
                import traceback
                print str(e)
                traceback.print_exc()
                sys.exit(mdig.mdig_exit_codes["unknown"])

    def check_lifestage(self,i,ls):
        if ls not in i.experiment.get_lifestage_ids():
            self.log.error("No such lifestage called %s in model." % str(ls))
            raise InvalidLifestageException()

    def check_background_map(self):
        g = grass.get_g()
        if self.options.background and not g.check_map(self.options.background):
            self.log.error("Couldn't find background map %s" % self.options.background)
            self.options.background = None
            #raise grass.MapNotFoundException(self.options.background)

    def do_rep(self,i,r):
        ls = self.options.output_lifestage
        map_list = []
        saved_maps = r.get_saved_maps(ls)
        model_name = i.experiment.get_name()

        # Normalise the color scale so that the lgend and range doesn't
        # keep changing for map to map
        self.log.info("Normalising colours")
        the_range = grass.get_g().normalise_map_colors(saved_maps.values())

        times = saved_maps.keys()
        times.sort(key=lambda x: float(x))
        output_images = self.options.output_gif or self.options.output_image 
        output_maps = self.options.output_map_pack
        if output_maps:
            rep_filenames = r.get_img_filenames(ls, extension=False,
                dir=self.options.outdir) 
        elif output_images:
            rep_filenames = r.get_img_filenames(ls, dir=self.options.outdir) 
        for t in times:
            m = saved_maps[t]
            if output_images:
                map_list.append(self.create_frame(m,rep_filenames[t],model_name, t, ls, the_range))
                self.update_listeners(None, r, ls, t)
            elif output_maps:
                map_list.append(self.export_map(m,rep_filenames[t]))
                self.update_listeners_map_pack(None, r, ls, t)
        if self.options.output_gif:
            self.create_gif(map_list,r.get_img_filenames(ls,gif=True,dir=self.options.outdir))
        elif output_maps:
            zip_fn = r.get_img_filenames(ls, extension=False, gif=True,dir=self.options.outdir)[:-5]
            self.zip_maps(map_list, zip_fn)
        return map_list

    def do_instance(self,i):
        # TODO: only overwrite files if -o flag is set
        import outputformats
        model_name = i.experiment.get_name()
        ls = self.options.output_lifestage
        self.check_lifestage(i, ls)
        all_maps = []
        # check that background map exists
        output_images = self.options.output_gif or self.options.output_image 
        output_maps = self.options.output_map_pack
        if output_images: self.check_background_map()
        if self.options.reps:
            if len(self.options.reps) > 1 and output_maps:
                    self.log.info("Exporting maps of reps: %s" % str(self.options.reps))
            # Run on replicates
            rs = i.replicates
            i.set_region()
            if len(rs) == 0:
                self.log.error("No replicates for instance %d. Have you run the model first?" \
                                % i.experiment.get_instances().index(i))
                raise InvalidReplicateException("No replicates available")
            for r_index in self.options.reps:
                if output_images:
                    self.log.info("Creating images for maps of rep %d" % r_index)
                elif output_maps:
                    self.log.info("Exporting maps of rep %d" % r_index)
                if r_index < 0 or r_index >= len(rs):
                    self.log.error("Invalid replicate index." +
                            " Have you 'run' the model first or are you "
                            "specifying an invalid replicate index?")
                    if len(rs) > 0:
                        self.log.error("Valid replicate range is 0-%d." % (len(rs)-1))
                    raise InvalidReplicateException(r_index)
                r = rs[r_index]
                all_maps.extend(self.do_rep(i,r))
        else:
            if not i.is_complete():
                self.log.error("Instance " + repr(i) + " not complete")
                raise InstanceIncompleteException()
            i.change_mapset()
            # Run on occupancy envelopes
            if output_maps:
                self.log.info("Exporting occupancy envelope maps")
            elif output_images:
                self.log.info("Creating images for occupancy envelopes")
            self.log.debug("Fetching occupancy envelopes")
            env = i.get_occupancy_envelopes()
            if env is None:
                self.log.info("Couldn't find occupancy envelopes, so trying to generate...")
                i.update_occupancy_envelope()
                env = i.get_occupancy_envelopes()
                if env is None:
                    err_str = "Error creating occupancy envelopes."
                    self.log.error(err_str)
                    raise NoOccupancyEnvelopesException(err_str)
            map_list = []
            times = env[ls].keys()
            times.sort(key=lambda x: float(x))
            if output_maps:
                img_filenames = i.get_occ_envelope_img_filenames(ls, extension=False,dir=self.options.outdir) 
            elif output_images:
                img_filenames = i.get_occ_envelope_img_filenames(ls,dir=self.options.outdir) 
            for t in times:
                m = env[ls][t]
                if output_maps:
                    map_list.append(self.export_map(m,img_filenames[t],envelope=True))
                    self.update_listeners_map_pack(i, None, ls, t)
                elif output_images:
                    map_list.append(self.create_frame(m,img_filenames[t],model_name, t, ls))
                    if self.options.output_image:
                        self.log.info("Saved png to " + img_filenames[t])
                    self.update_listeners(i, None, ls, t)
            if self.options.output_gif:
                self.create_gif(map_list,i.get_occ_envelope_img_filenames(ls,gif=True,dir=self.options.outdir) )
            elif output_maps:
                zip_fn = i.get_occ_envelope_img_filenames(ls, extension=False, gif=True,dir=self.options.outdir)[:-5]
                self.zip_maps(map_list, zip_fn)
            all_maps.extend(map_list)
        # If the user wanted an animated gif, then clean up the images
        # Also clean up exported ASCII maps outside of zip file
        if not self.options.output_image or output_maps:
            for m in all_maps:
                os.remove(m)

    def export_map(self,map,out_fn,envelope=False):
        old_region = "ExportActionBackupRegion"
        g = grass.get_g()
        g.run_command('g.region --o save='+old_region)
        g.set_region(raster=map) 
        cmd = 'r.out.gdal input=%s output=%s.tif format=GTiff type=%s createopt="COMPRESS=PACKBITS,INTERLEAVE=PIXEL"'
        if envelope:
            if self.float64:
                cmd = cmd % (map, out_fn, 'Float64')
            else:
                cmd = cmd % (map, out_fn, 'Float32')
        else:
            cmd = cmd % (map, out_fn, 'UInt16')

        try:
            g.run_command(cmd)
            out_fn += ".tif"
        except grass.GRASSCommandException, e:
            # This swaps to 64 bit floats if GRASS complains about
            # losing precision on export
            if "Precision loss" in e.stderr:
                self.float64 = True
                out_fn = self.export_map(map,out_fn,envelope)
            else: raise e
        finally:
            g.set_region(old_region) 
        return out_fn

    def zip_maps(self,maps,zip_fn):
        import zipfile
        import os.path
        zip_fn += ".zip"
        if os.path.isfile(zip_fn) and not self.options.overwrite_flag:
            raise OSError("Zip file %s exists, use -o flag to overwrite" % zip_fn)
        try: 
            z = zipfile.ZipFile(zip_fn,mode='w',compression=zipfile.ZIP_DEFLATED)
        except RuntimeError:
            self.log.warning("No zlib available for compressing zip, " + \
                    "defaulting to plain storage")
            z = zipfile.ZipFile(zip_fn,mode='w')
        for m in maps: z.write(m, os.path.basename(m))
        z.close()
        self.log.info("Maps were stored in zip file %s" % zip_fn)

    def update_listeners(self,instance,replicate,ls,t):
        if instance:
            for l in self.listeners:
                if "export_image_complete" in dir(l):
                    l.export_image_complete(instance, None, ls,t)
        elif replicate:
            for l in self.listeners:
                if "export_image_complete" in dir(l):
                    l.export_image_complete(None, replicate, ls,t)

    def update_listeners_map_pack(self,instance,replicate,ls,t):
        if instance:
            for l in self.listeners:
                if "export_map_pack_complete" in dir(l):
                    l.export_map_pack_complete(instance, None, ls,t)
        elif replicate:
            for l in self.listeners:
                if "export_map_pack_complete" in dir(l):
                    l.export_map_pack_complete(None, replicate, ls,t)

    def create_gif(self,maps,fn):
        from subprocess import Popen, PIPE
        gif_fn = fn
        if os.path.isfile(gif_fn) and not self.overwrite_flag:
            raise OSError("Gif file %s exists, use -o flag to overwrite" % zip_fn)
        self.log.info("Creating animated gif with ImageMagick's convert utility.")
        output = Popen("convert -delay 100 " + " ".join(maps)
            + " " + gif_fn, shell=True, stdout=PIPE).communicate()[0]
        if len(output) > 0: self.log.debug("Convert output:" + output)
        self.log.info("Saved animated gif to " + gif_fn)
        return gif_fn

    def create_frame(self, map_name, output_name, model_name, year, ls, the_range = None):
        import os
        g = grass.get_g()
        if os.path.isfile(output_name) and not self.overwrite_flag:
            raise OSError("Gif file %s exists, use -o flag to overwrite" % zip_fn)
        g.set_output(filename = output_name, \
                width=self.options.width, height=self.options.height, display=None)
        g.run_command("d.erase")
        os.environ['GRASS_PNG_READ']="TRUE"
        if self.options.background:
            bg = self.options.background.split('@')
            if len(bg) > 1: map_ok = g.check_map(bg[0], bg[1])
            else: map_ok = g.check_map(bg)
            g.run_command("r.colors color=grey map=" + self.options.background)
            g.run_command("d.rast " + self.options.background)
        # This is code for setting the color table of each map manually
        # hasn't been easily integrated into interface, but easy for hacking
        # custom map output
        custom_color = False
        if custom_color:
            from subprocess import Popen, PIPE
            pcolor= Popen('r.colors map=%s rules=-' % map_name, \
                    shell=True, stdout=PIPE, stdin=PIPE)
            rule_string = "0%% %d:%d:%d\n" % (255,255,0)
            rule_string += "100%% %d:%d:%d\n" %  (255,255,0)
            rule_string += 'end'
            output = pcolor.communicate(rule_string)[0]
        ###
        # Draw the map
        g.run_command("d.rast " + map_name + " -o")
        # Draw the scale
        g.run_command("d.barscale tcolor=0:0:0 bcolor=none at=2,18 -l -t")
        # Code to enable/disable the legend
        do_legend = True
        if do_legend:
            if the_range:
                g.run_command("d.legend -s " + map_name + " range=%f,%f at=5,50,85,90" % the_range)
            else:
                g.run_command("d.legend -s " + map_name + " at=5,50,85,90")
        ###
        # Show the model name and year
        g.run_command("d.text at=2,90 size=3 text=" + model_name)
        g.run_command("d.text text=" + year + " at=2,93")
        # Save frame
        g.close_output()
        return output_name
    
class ROCAction(Action):
    description = "Create Receiver Operating Characteristic curves for " + \
        "occupancy envelopes and calculate AUC."

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = ROCAction.description,
                usage = "%prog roc [options] <model_name1> <model_name2> ...")
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
        config.get_config().overwrite_flag = self.options.overwrite_flag
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
        self.ROC = ROCanalysis.ROCanalysis(self.model_names,self.options)
        self.ROC.run()


class AdminAction(Action):
    description = "Perform miscellaneous administative tasks"

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = AdminAction.description,
                usage = "%prog admin [options] <model_name>")
        self.add_options()

    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")
        self.parser.add_option("-n","--remove-null",
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
        self.parser.add_option("-l","--list-instances",
                help="List all the instances, their index, and status",
                action="store_true",
                dest="list_instances")
        self.parser.add_option("-t","--toggle-instance",
                help="Change the whether instances are enabled or not",
                action="store",
                dest="toggle_instances")

    def do_me(self,mdig_model):
        if self.options.move_mapset:
            mdig_model.move_mapset(move_mapset)
        if self.options.remove_null:
            mdig_model.null_bitmask( False )
        if self.options.generate_null:
            mdig_model.null_bitmask( True )
        if self.options.check_maps:
            if mdig_model.check_model():
                print "Model looks okay!"
        if self.options.list_instances:
            instances = mdig_model.get_instances()
            counter = 0
            for i in instances:
                print( "%d: %s" % (counter, i.long_str() ))
                counter += 1
        if self.options.toggle_instances is not None:
            instances = mdig_model.get_instances()
            for i in self.options.toggle_instances.split(","):
                i = int(i)
                instances[i].enabled = not instances[i].enabled
                print( "%d: %s" % (i, str(instances[i]) ))
                instances[i].update_xml()
            #mdig_model.save_model()

class WebAction(Action):
    description = "Run a webserver that allows interaction with MDiG"

    def __init__(self):
        Action.__init__(self)
        self.parser = OptionParser(version=mdig.version_string,
                description = WebAction.description,
                usage = "%prog web [options] <model_name>")
        self.preload = False
        self.add_options()
        
    def add_options(self):
        Action.add_options(self)

    def do_me(self,mdig_model):
        # initialise web system - needs to create new mapset
        from webui import start_web_service
        # start web monitoring loop
        start_web_service()
    
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
    "stats": StatsAction,
    "add": AddAction,
    "list": ListAction,
    "admin": AdminAction,
    "export": ExportAction,
    "web": WebAction,
    "node": ClientAction,
    "info": InfoAction,
    "reset": ResetAction,
    "remove": RemoveAction,
    "repository": RepositoryAction
    }
mdig_actions["roc"] = ROCAction

