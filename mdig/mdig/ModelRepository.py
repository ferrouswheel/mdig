import os
import sys
import glob
import pdb
import logging
import tempfile

import mdig
from mdig import MDiGConfig
from mdig import GRASSInterface 
from mdig import DispersalModel


class RepositoryException(Exception):
    pass

class ModelRepository:

    def __init__(self, gisdbase=None):
        self.log = logging.getLogger("mdig.repos")
        c = MDiGConfig.get_config()
        # Model repository is now a part of a GRASS db directory
        g = GRASSInterface.get_g()
        if gisdbase is None:
            if g.in_grass_shell:
                self.db = g.grass_vars["GISDBASE"]
            else:
                self.db = c["GRASS"]["GISDBASE"]
        else:
            if not os.path.isdir(gisdbase):
                raise OSError("Bad GISDBASE")
            self.db = gisdbase 
        self.log.info("Using GRASS DB location " + self.db)

    def add_model(self, model_fn):
        import shutil
        if not os.path.isfile(model_fn):
            raise RepositoryException("Model file %s is not a file."%model_fn)
        g = GRASSInterface.get_g()
        dm = DispersalModel.DispersalModel(model_fn,setup=False)
        loc = dm.get_location()
        if dm.get_location() == None:
            raise RepositoryException("Model doesn't define GIS Location for simulation")
        if not os.path.isdir(os.path.join(self.db,loc,"PERMANENT")):
            raise RepositoryException("Model defines a GIS Location " + loc + " that " + "doesn't exist in " + self.db)
        g.change_mapset(dm.get_location(),"PERMANENT")
        # create model mapset
        self.log.info("Creating mapset for model %s"%dm.get_mapset())
        if g.check_mapset(dm.get_name()):
            raise RepositoryException("Couldn't create mapset %s, it already exists in location %s." \
                    % (dm.get_mapset(),g.get_mapset_full_path(dm.get_mapset()) ))
        if not g.change_mapset(dm.get_name(),dm.get_location(),True):
            raise RepositoryException("Couldn't create mapset %s." % dm.get_mapset())
        self.log.info("Created mapset for model " + dm.get_name())

        # create mdig dir in mapset
        try:
            dest_dir = g.create_mdig_subdir(dm.get_mapset())
        except OSError, e:
            g.remove_mapset(dm.get_mapset(),force=True)
            raise RepositoryException("Error creating mdig dir in mapset. %s" % str(e))

        # copy lifestage transition model file if it exists
        for pm in dm.get_popmod_files():
            src_file = pm
            # check if this exists, directly and then relative to model file
            if not os.path.exists(src_file):
                src_file = os.path.join(os.path.dirname(model_fn), src_file)
                if not os.path.exists(src_file):
                    g.remove_mapset(dm.get_mapset(),force=True)
                    raise RepositoryException("Can't find internally specified popmod lifestage transition file!")
            
            for lt in dm.get_lifestage_transitions():
                coda_files = lt.get_coda_files_in_xml()
                new_coda_files = []
                for cf in coda_files:
                    # check if this exists, directly and then relative to transition file
                    if not os.path.exists(cf):
                        cf = os.path.join(os.path.dirname(src_file), cf)
                        if not os.path.exists(cf):
                            g.remove_mapset(dm.get_mapset(),force=True)
                            raise RepositoryException("Can't find internally specified lifestage transition CODA file!")
                    shutil.copyfile(cf,os.path.join(dest_dir,os.path.basename(cf)))
                    new_coda_files.append(os.path.basename(cf))
                lt.set_coda_files_in_xml(new_coda_files)
            shutil.copyfile(src_file,os.path.join(dest_dir,os.path.basename(src_file)))

        # remove explicit location and rely on implicit location finding
        dm.remove_location()
        # write dispersal model to new dir (original copy)
        dm.save_model(os.path.join(dest_dir,"model_original.xml"))
        # write dispersal model to new dir (working copy)
        dm.save_model(os.path.join(dest_dir,"model.xml"))

        # TODO: check whether referenced maps exist or not...
        # TODO: create dispersal model method to scan for these

        # set up model directory
        dm.set_base_dir() 
        print "Successfully added model to mapset %s" % \
            g.get_mapset_full_path(dm.get_mapset())

    def remove_model(self, model_name, force=False):
        models = self.get_models()
        if model_name not in models:
            raise RepositoryException("The model '" + model_name + "' doesn't exist in the repository.")

        if not force:
            # TODO list ALL associated mapsets
            ans = raw_input("Are you sure you wish to remove model " + model_name + 
                    " and it's associate mapset? [y/n] ")
            if ans.upper() == "Y":
                force = True
            else:
                print "Not removing model " + model_name

        if force:
            import shutil
            g = GRASSInterface.get_g()
            dm = DispersalModel.DispersalModel(models[model_name],setup=False)
            loc = dm.get_location()
            if loc == None:
                loc = dm.infer_location()
            if not os.path.isdir(os.path.join(self.db,loc,"PERMANENT")):
                raise RepositoryException("Model defines a GIS Location " + loc + " that doesn't exist in " + self.db)
            g.change_mapset(dm.get_location(),"PERMANENT")
            #shutil.rmtree(model_dir)
            # TODO  remove ALL associated mapsets first (because we need the
            # model file to tell us which once are associated)
            GRASSInterface.get_g().remove_mapset(model_name, force)
            print "Model removed"

    def get_models(self):
        models = {}
        for loc in os.listdir(self.db):
            loc_dir = os.path.join(self.db, loc)
            if not os.path.isdir(loc_dir): continue
            for mapset in os.listdir(loc_dir):
                mapset_dir = os.path.join(loc_dir, mapset, "mdig")
                if not os.path.isdir(mapset_dir): continue
                model_file = os.path.join(mapset_dir, "model.xml")
                if not os.path.isfile(model_file):
                    xml_files = glob.glob(os.path.join(mapset_dir, "*.xml"))
                    if len(xml_files) == 1:
                        model_file = xml_files[0]
                        #logging.getLogger("mdig.repos").debug(
                            #"no model.xml for dir " + d +
                            #" - however found xml file " +
                            #os.path.basename(xml_files[0]))
                    elif len(xml_files) == 0 and not \
                        os.path.isfile(os.path.join(mapset_dir,"original_model")):
                        self.log.warn("No xml files or 'original' file in mdig "
                            + "dir of mapset " + mapset + " in location " + loc)
                        model_file = None
                    elif len(xml_files) > 1:
                        self.log.warn("No model.xml and more than one xml file in " + mapset_dir + " in location " + loc)
                        model_file = None
                    else:
                        # In this case, there is a mapset with original_model in it
                        model_file = None
                if model_file is not None:
                    models[mapset] = model_file
        return models

