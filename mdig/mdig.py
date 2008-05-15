#!/usr/bin/env python
'''
MDiG - Modular Dispersal in GIS

Usage: mdig.py <action> [options] experiment.xml

Actions:
run		- finish uncompleted simulations (or with a flag, redo all simulations)
analysis	- analyse simulations
admin	- maintenance tools
node*	- set up mdig instance as a parallel computing node
gui*	- run graphical user interface
*(Not yet Implemented)

Options:
-h (--help) \t Display action specific help

experiment.xml is the file containing the simulation details.
'''

_version_string = "mdig 0.1 - trowel" 

import sys
import os
import pdb
import logging
import random
import signal

from datetime import datetime, timedelta

from mdig import XMLModel
from mdig import Model

from mdig import MDiGConfig
from mdig import Displayer
from mdig import GRASSInterface

import getopt

exp = None
logger = None

def usage():
	
	print __doc__
	
def run_usage():
	
	print _version_string
	
	print "Run options"
	
	print '''
	-h help
	-t maximum real-time to run simulation for
	-n remove null bitmasks after each simulation
	-a run all instances, not just incomplete instances
	-f force - skips the the model check.
	-m display GRASS monitor
	-o overwrite maps
	-d base directory to save output in
	-v verbose
	-D debug (strongly verbose)
	'''
	
def analysis_usage():
	
	print _version_string
	
	print "Analysis options"
	
	print '''
	-h help
	-a <file> analysis commands specified in file
	-s <step> step at which to run analyses on ("all" or "final")
	-l <lifestage> lifestage to analyse ("all" or name of lifestage)
	-c run a combined analysis. Combine all replications into one probability map and then analyse. 
	-p force creation of mean population/probability envelope across replicates, don't run analysis
	-f <file> specify output filename (will be prepended with replicate number and variable info)
	-t prefix file entries with time
	-x do not record analysis in xml file
	-o overwrite files/maps
	-v verbose
	-D debug (strongly verbose)	
	'''
	
def admin_usage():
	print _version_string

	print "Admin/Maintenance options"

	print '''
	-r remove null bitmasks
	-g generate null bitmasks
	-c check all maps are present
	-m <mapset> move all maps to a new Grass mapset
	'''
	
def gui_usage():
	
	print _version_string
	
	print "GUI options"
	
	print "None currently..."
	
def client_usage():
	
	print _version_string
	
	print "Client options"
	
	print "Not Yet Implemented"

def process_options(argv):
	
	global logger
	
	model_file = None
	
	mdig_config = MDiGConfig.getConfig()
	
	# Remove action keyword first
	if len(argv) >= 1:
		mdig_config.action_keyword = argv[0]
	else:
		mdig_config.action_keyword = None
	
	def hRunOptions():
		try:
			opts, args = getopt.getopt(argv[1:], "ht:nafmod:Dv", ["help","time","no-null","all","force","monitor","overwrite","dir=","debug","verbose"])
		except getopt.GetoptError:
			usage()
			sys.exit(2)
	
		if len(args) >= 1:
			mdig_config.model_file = args[0]
			
		for o, a in opts:
			if o in ("-h", "--help"):
				run_usage()
				sys.exit(0)
			elif o in ("-t", "--time"):
				mdig_config.time = int(a)
			elif o in ("-n", "--no-null"):
				mdig_config.remove_null = True
			elif o in ("-a", "--all"):
				mdig_config.rerun_instances = True
			elif o in ("-f", "--force"):
				mdig_config.check_model = False
			elif o in ("-m", "--monitor"):
				mdig_config.show_monitor = True
			elif o in ("-o", "--overwrite"):
				mdig_config.overwrite_flag=1
			elif o in ("-d", "--dir"):
				mdig_config.analysis_dir=a
				if not os.path.isdir(a):
					logger.info("Directory %s doesn't exist, attemping to create\n",a)
					mdig_config.analysis_dir = mdig_config.makepath(a)
			elif o in ("-D", "--debug"):
				mdig_config.DEBUG=1
				logger.setLevel(logging.DEBUG)
				logger.debug("Debug messages enabled.")
			elif o in ("-v", "--verbose"):
				if not mdig_config.DEBUG==1:
					logger.setLevel(logging.INFO)
					logger.debug("Verbose messages enabled.")
		
	def hAnalysisOptions():
		
		try:
			opts, args = getopt.getopt(argv[1:], "hsa:f:txopcl:Dv", ["help","analysis-file=","step=","file=","time","no-xml","overwrite","combined-analysis","probability-envelope",\
			"lifestage=","debug","verbose"])
		except getopt.GetoptError:
			analyse_usage()
			sys.exit(2)
		
		if len(args) >= 1:
			mdig_config.model_file = args[0]
		
		# Default is to run analysis on all timesteps with maps available.
		mdig_config.analysis_step = "all"
		
		for o,a in opts:
			if o in ("-h", "--help"):
				analysis_usage()
				sys.exit(0)
			elif o in ("-s","--step"):
				if a[0] in ("final","all"): 
					mdig_config.analysis_step = a
				else:
					logger.error("Analysis parameter must be 'final' or 'all'")
					sys.exit(1)
			elif o in ("-a", "--analysis-file"):
				mdig_config.analysis_cmd_file = a
			elif o in ("-c", "--combined-analysis"):
				mdig_config.combined_analysis = True
			elif o in ("-p", "--probability-envelope"):
				mdig_config.prob_envelope_only = True
			elif o in ("-l", "--lifestage"):
				mdig_config.analysis_lifestage = a
			elif o in ("-f", "--file"):
				mdig_config.analysis_filename = a
			elif o in ("-t", "--time"):
				mdig_config.analysis_print_time = True
			elif o in ("-x", "--no-xml"):
				mdig_config.analysis_add_to_xml = False
			elif o in ("-o"):
				mdig_config.overwrite_flag = True
			elif o in ("-D", "--debug"):
				mdig_config.DEBUG=1
				logger.setLevel(logging.DEBUG)
				logger.debug("Debug messages enabled.")
			elif o in ("-v", "--verbose"):
				if not mdig_config.DEBUG==1:
					logger.setLevel(logging.INFO)
					logger.debug("Verbose messages enabled.")
			
	def hAdminOptions():
		try:
			opts, args = getopt.getopt(argv[1:], "horgm:Dv", ["help","remove","generate","move-mapset="])
		except getopt.GetoptError:
			admin_usage()
			sys.exit(1)
		
		if len(args) >= 1:
			mdig_config.model_file = args[0]
		
		for o,a in opts:
			if o in ("-h", "--help"):
				null_usage()
				sys.exit(0)
			elif o in ("-r","--remove"):
				mdig_config.remove_null = True
			elif o in ("-g","--generate"):
				mdig_config.generate_null = True
			elif o in ("-c","--check-maps"):
				mdig_config.check_maps = True
			elif o in ("-m","--move-mapset"):
				mdig_config.move_mapset = a
			elif o in ("-D", "--debug"):
				mdig_config.DEBUG=1
				logger.setLevel(logging.DEBUG)
				logger.debug("Debug messages enabled.")
			elif o in ("-v", "--verbose"):
				if not DEBUG==1:
					logger.setLevel(logging.INFO)
					logger.debug("Verbose messages enabled.")	
	
	def hGuiOptions():
		try:
			opts, args = getopt.getopt(argv[1:], "horgDv", ["help","remove","generate"])
		except getopt.GetoptError:
			gui_usage()
			sys.exit(1)

		if len(args) >= 1:
			mdig_config.model_file = args[0]

		for o,a in opts:
			if o in ("-h", "--help"):
				gui_usage()
				sys.exit(0)
		
	def hNodeOptions():
		node_usage()
		
	def hDefaultOptions():
		usage()
	
	switch = { "run":hRunOptions, "analysis":hAnalysisOptions, "admin":hAdminOptions, "node":hNodeOptions, "gui":hGuiOptions }
	function = hDefaultOptions
	if switch.has_key( mdig_config.action_keyword ):
		function = switch[mdig_config.action_keyword]
	function()

def hAnalysis():
	
	mdig_config = MDiGConfig.getConfig()
	global logger
	global exp
	
	ls = mdig_config.analysis_lifestage
	
	# If only a probability envelope is to be created then don't prompt for command
	if not mdig_config.prob_envelope_only and mdig_config.analysis_cmd_file is None:
		print "====================================\nAnalysis: You can use %0 to represent the current map being looked at, %1 to look at the previous saved map, etc. %t for time, %f for output file (specified with -f option or generated by MDiG)"
		prompt_str = "Please enter the analysis command to run for analysis of %s map(s)" % mdig_config.analysis_step
		if ls is None:
			prompt_str += ", all lifestages:\n"
		else:
			prompt_str += ", lifestage [%s]:\n" % ls
				
		mdig_config.analysis_command= raw_input(prompt_str)
	
	
	
	# If a combined analysis is being run (or a prob. envelope is being created)
	# then generate the combined maps.
	if mdig_config.combined_analysis or mdig_config.prob_envelope_only:
		
		logger.info("Updating probability envelopes")
		
		# force parameter for updateProbabilityEnvelope means that probability envelopes will be made
		# regardless of whether they already exist.
		if mdig_config.analysis_step == "all":
			exp.updateProbabilityEnvelope(ls,force=mdig_config.prob_envelope_only)
		elif mdig_config.analysis_step == "final":
			# -1 specifies the last time step
			exp.updateProbabilityEnvelope(ls,-1,force=mdig_config.prob_envelope_only)
		else:
			logger.error("Unknown analysis step : %s" % mdig_config.analysis_step)
			sys.exit(3)
		
		
	# TODO: run analysis
	if not mdig_config.prob_envelope_only:
		print "Running analysis command"
		
		commands_to_run = []
		
		if mdig_config.analysis_cmd_file is not None:
			# get commands from files
			logger.warning("Reading analysis commands from files is not implemented yet.")
			pass
		else:
			# add user prompted command line to the array
			commands_to_run.append(("user",mdig_config.analysis_command))
		
		for cmd in commands_to_run:
			
			if mdig_config.analysis_step == "all":
				exp.runCommandOnMaps(cmd[1], ls, prob=mdig_config.combined_analysis)
			else:
				# -1 specifies the last time step
				exp.runCommandOnMaps(cmd[1], ls, [-1], prob=mdig_config.combined_analysis)
	
	
def hRun():
	
	mdig_config = MDiGConfig.getConfig()
	global logger
	global exp
	
	if mdig_config.time is not None:
		mdig_config.start_time = datetime.now()
		mdig_config.end_time = start_time + timedelta(hours=time)
		logger.debug("Start time %s", mdig_config.start_time.ctime())
		logger.debug("Maximum end time %s", mdig_config.end_time.ctime())
		
	logger.debug("Executing simulation")
	
	if mdig_config.show_monitor:
		exp.addListener(Displayer.Displayer())
	if mdig_config.rerun_instances:
		exp.resetInstances()
	exp.run()

def hAdmin():
	mdig_config = MDiGConfig.getConfig()
	global logger
	global exp
	
	if mdig_config.move_mapset:
		exp.moveMapset(mdig_config.move_mapset)

	if mdig_config.remove_null:
		exp.nullBitmask( False )

	if mdig_config.generate_null:
		exp.nullBitmask( True )

	if mdig_config.check_maps:
		exp.checkInstances()

def hGui():
	pass
	
	
def main(argv):
	
	
	global logger
	global exp
	
	logger = setupLogger()
	
	mdig_config = MDiGConfig.getConfig()
	
	process_options(argv)
	
	signal.signal(signal.SIGINT, exit_catcher)
	
	switch = { "run":hRun, "analysis":hAnalysis, "admin":hAdmin, "gui":hGui }
	function = None
	if switch.has_key( mdig_config.action_keyword ):
		function = switch[mdig_config.action_keyword]
		
		# Check for grass environment and set up interface
		grass_interface = GRASSInterface.getG()
		
		#Load model definition
		if mdig_config.model_file is not None:
			exp = XMLModel.Experiment(mdig_config.model_file)
			
		else:
			logger.error ("No model file specified")
			sys.exit(2)
		
	elif mdig_config.action_keyword in ["-h","--help"]:
		pass
		
	elif mdig_config.action_keyword is not None:
		print "Unknown action %s" % mdig_config.action_keyword
		#logger.debug("Loading GUI")
		#mdigGui()
		
	if function is not None:
		function()
	
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
	global logger
	global exp
	
	logger.debug("Cleaning up")
	
	if exp is not None:
		exp.cleanUp()
		exp.saveModel()
	if GRASSInterface.getG(False) is not None:
		GRASSInterface.getG().cleanUp()
		
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

if __name__ == "__main__":
	main(sys.argv[1:])
	
