import os
import sys
import glob
import pdb
import logging

import mdig
from mdig import MDiGConfig
from mdig import GRASSInterface 
from mdig import DispersalModel

class ModelRepository:

    def __init__(self, grassdb=None):
        self.log = logging.getLogger("mdig.repos")
        c = MDiGConfig.get_config()
        # Model repository is now a part of a GRASS db directory
        if grassdb:
            self.db = grassdb 
        else:
            self.db = c["GRASS"]["GISDBASE"]
        self.log.info("Using GRASS DB location " + self.db)

    def add_model(self, model_fn):
        import shutil
        if not os.path.isfile(model_fn):
            self.log.error("Model file %s is not a file."%model_fn)
            sys.exit(5)

        dm = DispersalModel.DispersalModel(model_fn,setup=False)
        g = GRASSInterface.get_g()
        # create model mapset
        self.log.info("Create mapset for model %s."%dm.get_mapset())
        if g.check_mapset(dm.get_name()):
            self.log.error("Couldn't create mapset %s, it already exists." % dm.get_mapset())
            sys.exit(5)
        if not g.change_mapset(self.get_name(),dm.get_location(),True):
            self.log.error("Couldn't create mapset %s." % dm.get_mapset())
            sys.exit(5)
        self.log.info("Created mapset for model " + dm.get_name())

        # create mdig dir in mapset
        try:
            g.create_mdig_subdir(dm.get_mapset())
        except OSError, e:
            g.remove_mapset(dm.get_mapset(),force=True)
            self.log.error("Error creating mdig dir in mapset. %s" % str(e))
            sys.exit(5)

        # copy lifestage transition model file if it exists
        for pm in dm.get_popmod_files():
            src_file = pm
            # check if this exists, directly and then relative to model file
            if not os.path.exists(src_file):
                src_file = os.path.join(os.path.dirname(model_fn), src_file)
                if not os.path.exists(src_file):
                    self.log.error("Can't find internally specified popmod lifestage transition file!")
                    g.remove_mapset(dm.get_mapset(),force=True)
                    sys.exit(mdig.mdig_exit_codes["missing_popmod"])
            
            for lt in dm.get_lifestage_transitions():
                coda_files = lt.get_coda_files_in_xml()
                new_coda_files = []
                for cf in coda_files:
                    # check if this exists, directly and then relative to transition file
                    if not os.path.exists(cf):
                        cf = os.path.join(os.path.dirname(src_file), cf)
                        if not os.path.exists(cf):
                            self.log.error("Can't find internally specified " + \
                                    "lifestage transition CODA file!")
                            g.remove_mapset(dm.get_mapset(),force=True)
                            sys.exit(mdig.mdig_exit_codes["missing_popmod"])
                    shutil.copyfile(cf,os.path.join(dest_dir,os.path.basename(cf)))
                    new_coda_files.append(os.path.basename(cf))
                lt.set_coda_files_in_xml(new_coda_files)
            shutil.copyfile(src_file,os.path.join(dest_dir,os.path.basename(src_file)))

        # write dispersal model to new dir 
        #shutil.copyfile(model_fn,os.path.join(dest_dir,"model.xml"))
        dm.save_model(os.path.join(dest_dir,"model.xml"))

        # TODO: check whether referenced maps exist or not...
        # TODO: create dispersal model method to scan for these

        # set up model directory
        dm.set_base_dir() 

    def remove_model(self, model_name, force=False):
        models = self.get_models()
        if model_name not in models:
            self.log.error("The model '" + model_name + "' doesn't exist in the repository.")
            sys.exit(mdig.mdig_exit_codes["model_not_found"])

        if not force:
            # TODO list ALL associated mapsets
            ans = raw_input("Are you sure you wish to remove model " + model_name + 
                    " and it's associate mapset? [y/N] ")
            if ans.upper() == "Y":
                force = True
            else:
                self.log.error("Not removing model " + model_name)

        if force:
            import shutil
            shutil.rmtree(model_dir)
            # TODO  remove ALL associated mapsets
            GRASSInterface.get_g().remove_mapset(model_name, force)

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
                    elif len(xml_files) == 0:
                        self.log.warn("No xml files in mdig dir of mapset " + mapset)
                        model_file = None
                    else:
                        self.log.warn("No model.xml and more than one xml file in " + mapset_dir)
                        model_file = None
                if model_file is not None:
                    models[mapset] = model_file
        return models

