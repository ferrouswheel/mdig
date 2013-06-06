import sys
import logging

import mdig
from mdig import config


class Action(object):

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
                help="Override GRASS database dir (GISDBASE)",
                action="store",
                type="string",
                dest="repository",
                default=None)
        self.parser.add_option("-k","--location",
                help="Override GRASS location (LOCATION_NAME)",
                action="store",
                type="string",
                dest="location",
                default=None)
    
    def act_on_options(self, options):
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

    def parse_options(self, argv):
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
        return NotImplemented


class InstanceAction(Action):

    def add_options(self):
        super(InstanceAction, self).add_options()
        self.parser.add_option("-j","--instance",
                help="Select particular instances",
                action="append",
                dest="instances",
                type="int")

    def get_instances(self, model):
        """ Process options and use model to return a list of instances to act on. """
        if self.options.instances:
            return [x for x in model.get_instances()
                            if x.get_index() in self.options.instances]
        else:
            return [x for x in model.get_instances() if x.enabled]

    def do_me(self, mdig_model):
        instances = self.get_instances(mdig_model)

        if instances:
            self.do_instances(mdig_model, instances)

        if self.options.instances:
            for instance in instances:
                self.do_instance(mdig_model, instance)
        else:
            self.do_model(mdig_model)

    def do_instances(self, mdig_model, instances):
        """ This is run in all cases """ 
        pass

    def do_model(self, mdig_model):
        """ This is run after do_instances if no specific instances are selected """ 
        pass

    def do_instance(self, mdig_model, instance):
        """ This is run after do_instances if specific instances are selected """ 
        pass

