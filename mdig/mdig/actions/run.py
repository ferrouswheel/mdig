import sys
import os

from datetime import datetime, timedelta
from optparse import OptionParser

import mdig
import mdig.utils as utils
from mdig import config
from mdig.actions.base import InstanceAction

from mdig import displayer


class RunAction(InstanceAction):
    description = "Run a model"

    def __init__(self):
        super(RunAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
                usage = "%prog run [options] model_name" )
        self.add_options()

    def add_options(self):
        super(RunAction, self).add_options()
        self.parser.add_option("-t","--runtime",
                help="Maximum minutes to run simulations for.",
                action="store",
                dest="time",
                type="int")
        self.parser.add_option("-n","--no-null",
                help="Remove null bitmasks after creating maps",
                action="store_true",
                dest="remove_null")
        self.parser.add_option("-a","--all",
                help="Rerun instances, even those that are already complete",
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
                help="Do lifestage transitions by individual (Warning: very slow)",
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

    def act_on_options(self, options):
        super(RunAction, self).act_on_options(options)
        c = config.get_config()
        if options.output_dir is not None:
            if not os.path.isdir(options.output_dir):
                self.log.info("Directory %s doesn't exist, attemping to" +
                        " create\n",options.output_dir)
                c.output_dir = \
                    utils.make_path(options.output_dir)
            else:
                c.output_dir = options.output_dir
        c.overwrite_flag = self.options.overwrite_flag
        c.remove_null = self.options.remove_null

    def prerun_setup(self, mdig_model):
        if self.options.time is not None:
            self.start_time = datetime.now()
            self.end_time = self.start_time + timedelta(seconds=self.options.time * 60)
            self.log.debug("Start time %s", self.start_time.ctime())
            self.log.info("Will force stop at time %s", self.end_time.ctime())
        self.log.debug("Executing simulation")
        
        if self.options.show_monitor:
            mdig_model.add_listener(displayer.Displayer())

        if self.options.ls_trans_individual:
            self.log.debug("Calculating lifestage transitions by individual. This is slow.")
            for i in mdig_model.get_lifestage_transitions():
                i.by_individual = True

        if self.options.ls_trans_ignore_div_by_zero:
            self.log.debug("Will ignoring division by zero errors in lifestage transition.")
            for i in mdig_model.get_lifestage_transitions():
                i.t_matrix.ignore_div_by_zero = True

        if self.options.reps is not None:
            mdig_model.set_num_replicates(self.options.reps)

        if not self.options.rerun_instances and mdig_model.is_complete():
            self.log.error("Model is up to date (use -a to force reset and rerun instances)")
            sys.exit(mdig.mdig_exit_codes['up_to_date'])

    def do_me(self, mdig_model):
        self.prerun_setup(mdig_model)
        super(RunAction, self).do_me(mdig_model)

    def do_model(self, mdig_model):
        if self.options.rerun_instances:
            self.log.debug("Resetting model so all instances and replicates will be rerun")
            mdig_model.reset_instances()
        mdig_model.run()
        if mdig_model.total_time_taken:
            mdig_model.log_instance_times()
            print "Total time taken: %s" % mdig_model.total_time_taken
        else:
            print "Nothing to do."

    def do_instance(self, mdig_model, instance):
        if self.options.rerun_instances:
            self.log.debug("Resetting instance so all replicates will be rerun")
            instance.reset()
        instance.run()

