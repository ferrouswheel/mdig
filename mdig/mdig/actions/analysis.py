import os
import sys

import mdig
from mdig import config
from mdig import grass
from mdig import utils
from mdig.actions.base import Action, InstanceAction

from optparse import OptionParser


def _update_probability_envelopes(mdig_model, instances, log, options):
    ls = [options.analysis_lifestage] if options.analysis_lifestage else None

    # If a combined analysis is being run (or a prob. envelope is being
    # created) then generate the combined maps.
    if not (options.combined_analysis or options.prob_envelope_only):
        return

    log.info("Updating probability envelopes")
    
    # force parameter for update_occupancy_envelope means that
    # probability envelopes will be made regardless of whether they
    # already exist.
    if options.analysis_step == "all":
        mdig_model.update_occupancy_envelope(
                ls,
                force=options.prob_envelope_only,
                instances=instances
                )
    elif options.analysis_step == "final":
        # -1 specifies the last time step
        mdig_model.update_occupancy_envelope(
                ls, -1, 
                force=options.prob_envelope_only,
                instances=instances
                )
    else:
        log.error("Unknown analysis step : %s" % options.analysis_step)
        sys.exit(mdig.mdig_exit_codes["cmdline_error"])

    mdig_model.save_model()


class AnalysisAction(InstanceAction):
    description = "Perform analysis on a model and create occupancy envelopes"

    def __init__(self):
        super(AnalysisAction, self).__init__()
        # Default is to run analysis on all timesteps with maps available.
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
                usage = "%prog analysis [options] model_name")
        self.add_options()

    def add_options(self):
        super(AnalysisAction, self).add_options()
        self.parser.add_option("-a","--analysis",
                help="Load analysis command from a file rather than " +
                    "prompting user",
                action="store",
                dest="analysis_cmd_file",
                type="string")
        self.parser.add_option("-s","--step",
                help="The interval at which to run analysis on ('all' or 'final')",
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
        super(AnalysisAction, self).act_on_options(options)
        c = config.get_config()
        c.analysis_add_to_xml = self.options.analysis_add_to_xml
        c.analysis_filename_base = self.options.analysis_filename_base
        c.analysis_print_time = self.options.analysis_print_time
        c.overwrite_flag = self.options.overwrite_flag

        # If only a probability envelope is to be created then don't prompt
        # for command
        if (not self.options.prob_envelope_only and 
                self.options.analysis_cmd_file is None):
            self.analysis_command = self._get_analysis_command(self.options.analysis_lifestage)

    def do_instances(self, mdig_model, instances):
        _update_probability_envelopes(mdig_model, instances, self.log, self.options)

        ls = self.options.analysis_lifestage

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
                    mdig_model.run_command_on_maps(
                            cmd[1],
                            ls,
                            prob=self.options.combined_analysis,
                            instances=instances
                            )
                else:
                    # -1 specifies the last time step
                    mdig_model.run_command_on_maps(
                            cmd[1],
                            ls,
                            times=[-1],
                            prob=self.options.combined_analysis,
                            instances=instances
                            )

    def _get_analysis_command(self, ls):
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
                
        return raw_input(prompt_str)


class StatsAction(InstanceAction):
    description = "Calculate univariate statistics for maps."

    def __init__(self):
        super(StatsAction, self).__init__()
        # Default is to run analysis on all timesteps with maps available.
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
                usage = "%prog stats [options] model_name")
        self.add_options()

    def add_options(self):
        super(StatsAction, self).add_options()
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
        self.parser.add_option("-p","--occupancy-only",
                help="Just create occupancy envelopes, don't run analysis",
                action="store_true",
                dest="prob_envelope_only")
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

    def act_on_options(self, options):
        super(StatsAction, self).act_on_options(options)
        c = config.get_config()
        c.analysis_add_to_xml = self.options.analysis_add_to_xml
        c.analysis_filename_base = self.options.analysis_filename_base
        c.overwrite_flag = self.options.overwrite_flag

    def do_instances(self, mdig_model, instances):
        _update_probability_envelopes(mdig_model, instances, self.log, self.options)
            
        ls = self.options.analysis_lifestage
        self.files_written = []
        
        self.log.info("Calculating area...")

        g=grass.get_g()
        if self.options.combined_analysis:
            if self.options.analysis_step == "all":
                for i in instances:
                    self.log.info("Calculating stats for instance %d" % i.get_index())
                    maps = i.get_occupancy_envelopes()[ls]
                    i.change_mapset()
                    stats=g.get_univariate_stats(maps)
                    fn = os.path.split(i.get_occ_envelope_img_filenames(ls=ls,
                            extension=False,gif=True)[:-5])
                    fn = os.path.join(fn[0],self.options.analysis_filename_base + fn[1])
                    self.write_stats_to_file(stats,fn)
                    self.files_written.append(fn)
            else:
                # just run on last map
                raise NotImplementedError("Only supports running all maps current")
        else:
            if self.options.analysis_step == "all":
                for i in instances:
                    i.change_mapset()
                    for r in i.replicates:
                        self.log.info("Calculating stats for instance %d, rep %d" % \
                                (i.get_index(), r.r_index))
                        maps = r.get_saved_maps(ls)
                        stats = g.get_univariate_stats(maps)
                        fn = os.path.split(r.get_base_filenames(ls, single_file=True))
                        fn = os.path.join(fn[0], self.options.analysis_filename_base + fn[1])
                        self.write_stats_to_file(stats, fn)
                        self.files_written.append(fn)
            else:
                # just run on last map
                raise NotImplementedError("Only supports running all maps current")

        if len(self.files_written) > 1:
            self.log.info("Output is in: %s .. etc" % str(self.files_written[0]))
        else:
            self.log.info("Output is in: %s" % str(self.files_written[0]))

    def write_stats_to_file(self, stats, fn):
        c = config.get_config()

        if os.path.isfile(fn):
            if c.overwrite_flag:
                os.remove(fn)
            else:
                raise Exception("File %s already exists, -o to overwrite" % fn)

        expected=['n', 'area', 'null_cells', 'cells', 'min', 'max', 'range', 'mean',
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
        


class ReduceAction(Action):
    description = "Take a series of CSV output files and calculate average and std."

    def __init__(self):
        # TODO: refactor this and RepositoryAction to share a non-model loading
        # parent
        super(ReduceAction, self).__init__()
        self.check_model = False
        self.preload = False
        self.init_repository = False
        self.init_grass = False
        # Default is to run analysis on all timesteps with maps available.
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
                usage = "%prog reduce [options] model_name")
        self.add_options()
        self.model_limit = None
        self.parser.remove_option('-k')
        self.parser.remove_option('-r')

    def add_options(self):
        super(ReduceAction, self).add_options()
        self.parser.add_option("-n","--no-header",
                help="Are the CSVs missing headers?",
                action="store_true",
                dest="no_header")
        self.parser.add_option("-c","--column",
                help="Use this column for the timeseries value we are reducing.",
                action="store",
                type="int",
                dest="column")
        self.parser.add_option("-m","--match",
                help="Match these columns in each file",
                action="append",
                default=[0],
                type="int",
                dest="match_columns")
        self.parser.add_option("-f","--out-file",
                help="File to put the results in",
                action="store",
                dest="outfile")

    def do_me(self, mdig_model):
        import csv
        from mdig.utils import mean_std_dev
        the_files = self.model_names # extra args are put in self.model_names
        row_keys={}
        headers = None
        for fn in the_files:
            with open(fn, 'r') as f:
                csv_reader = csv.reader(f, delimiter=',', quotechar='"', skipinitialspace=True)
                if not self.options.no_header:
                    headers = next(csv_reader, None)
                for row in csv_reader:
                    k = tuple([row[i] for i in self.options.match_columns])
                    row_keys.setdefault(k, [])
                    try:
                        row_keys[k].append(float(row[self.options.column]))
                    except ValueError:
                        row_keys[k].append(0.0)
                    except Exception, e:
                        print str(e)
                        print row
                        import pdb; pdb.set_trace()
        # Reduce them
        reduced = {}
        for k in row_keys:
            reduced[k] = mean_std_dev(row_keys[k])

        from operator import itemgetter
        with open(self.options.outfile, 'w') as f:
            out_file = csv.writer(f, delimiter=',', quotechar='"')
            if headers:
                header = [headers[i] for i in self.options.match_columns] + [
                        'mean %s' % headers[self.options.column],
                        'std %s' % headers[self.options.column],
                        ]
                out_file.writerow(header)
            for k, val in sorted(reduced.iteritems(), key=itemgetter(0)):
                out_file.writerow(list(k) + list(val))


class ROCAction(Action):
    description = "Create Receiver Operating Characteristic curves for " + \
        "occupancy envelopes and calculate AUC."

    def __init__(self):
        super(ROCAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
                usage = "%prog roc [options] <model_name1> <model_name2> ...")
        # Can theoretically run on any number of models
        self.model_limit = None
        self.preload = False
        self.add_options()
        
    def add_options(self):
        super(ROCAction, self).add_options()
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
        super(ROCAction, self).act_on_options(self, options)
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
                utils.make_path(options.output_dir)
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
        # TODO move this to roc module
        if "linux" not in sys.platform:
           print "ROC analysis not supported on platforms other than Linux"
           sys.exit(1)
        from mdig.roc import ROCAnalysis
        self.ROC = ROCAnalysis(self.model_names,self.options)
        self.ROC.run()
