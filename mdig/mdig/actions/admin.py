from mdig.actions.base import Action

import os
import sys

from optparse import OptionParser

import mdig
from mdig import config
from mdig import grass
from mdig.model import DispersalModel


class AdminAction(Action):
    description = "Perform miscellaneous administative tasks"

    def __init__(self):
        super(AdminAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
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
                help="Move model to a new mapset",
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
            mdig_model.move_mapset(self.options.move_mapset)
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


class RepositoryAction(Action):
    description = "Set/modify the current MDiG repository and location"

    def __init__(self):
        super(RepositoryAction, self).__init__()
        self.check_model = False
        self.preload = False
        self.init_repository = False
        self.init_grass = False
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
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
        print "Set repository to: " + c['GRASS']['GISDBASE']
        print "Set default location to: " + c['GRASS']['LOCATION_NAME']


class ResetAction(Action):
    description = "Reset the model. Delete all prior instances/replicates."

    def __init__(self):
        super(ResetAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
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
        super(AddAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
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
        super(RemoveAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
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
        super(ListAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
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
            except mdig.model.ValidationError:
                print "%s [ERROR]" % (m,)
        sys.exit(0)

class InfoAction(Action):
    description = "Display information about a model in the MDiG repository."

    def __init__(self):
        super(InfoAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
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

