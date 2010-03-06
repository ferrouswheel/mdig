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

    def __init__(self, dir=None):
        self.location = None
        self.log = logging.getLogger("mdig.repos")
        # If given a specific directory, then check it exists
        if dir is not None:
            if os.path.isdir(dir):
                self.location = dir
                self.log.info("Using repository location " + self.location)
            else:
                raise Exception("Repository directory doesn't exist. d=" +
                        dir)
        # Otherwise find the repository location through the config file
        if self.location is None:
            c = MDiGConfig.getConfig()
            self.location = c["repository"]["location"]
            self.log.debug("Using repository location " + self.location)
            if not os.path.isdir(self.location):
                pdb.set_trace()
                raise Exception("Repository directory doesn't exist. d=" +
                        self.location)

    def add_model(self, model_fn):
        import shutil
        if not os.path.isfile(model_fn):
            log.error("Model file %s is not a file."%model_fn)
            sys.exit(5)

        # create dir in repo
        # dirname is from model name
        repo_dir = self.location
        dm = DispersalModel.DispersalModel(model_fn,setup=False)
        dest_dir = os.path.join(repo_dir,dm.get_name())
        if os.path.exists(dest_dir):
            if not MDiGConfig.getConfig().overwrite_flag:
                self.log.error("A model with the same name as %s already exists. Use " % model_fn +
                        "'remove' first or use overwrite flag.")
                sys.exit(mdig.mdig_exit_codes["exists"])
            else:
                self.log.warning("A model with the same name as %s already exists. Overwriting." % dm.get_name())
                shutil.rmtree(dest_dir)
        MDiGConfig.makepath(dest_dir)
        self.log.info("Created repo dir for model " + dm.get_name())

        # copy lifestage transition model file if it exists
        if dm.get_popmod_file() is not None:
            src_file = dm.get_popmod_file()
            # check if this exists, directly and then relative to model file
            if not os.path.exists(src_file):
                src_file = os.path.join(os.path.dirname(model_fn), src_file)
                if not os.path.exists(src_file):
                    self.log.error("Can't find internally specified popmod lifestage transition file!")
                    sys.exit(mdig.mdig_exit_codes["missing_popmod"])
            
            lt = dm.get_lifestage_transition()
            coda_files = lt.get_coda_files_in_xml()
            new_coda_files = []
            for cf in coda_files:
                # check if this exists, directly and then relative to transition file
                if not os.path.exists(cf):
                    cf = os.path.join(os.path.dirname(src_file), cf)
                    if not os.path.exists(cf):
                        self.log.error("Can't find internally specified " + \
                                "lifestage transition CODA file!")
                        sys.exit(mdig.mdig_exit_codes["missing_popmod"])
                shutil.copyfile(cf,os.path.join(dest_dir,os.path.basename(cf)))
                new_coda_files.append(os.path.basename(cf))
            lt.set_coda_files_in_xml(new_coda_files)

            shutil.copyfile(src_file,os.path.join(dest_dir,"lifestage_transition.xml"))
            dm.set_popmod_file("lifestage_transition.xml")
            

        # write dispersal model to new dir 
        #shutil.copyfile(model_fn,os.path.join(dest_dir,"model.xml"))
        dm.save_model(os.path.join(dest_dir,"model.xml"))

        # set up model directory
        dm.set_base_dir() 
        # change to and create model mapset
        dm.init_mapset()

    def remove_model(self, model_name, force=False):
        models = self.get_models()
        if model_name not in models:
            self.log.error("The model '" + model_name + "' doesn't exist in the repository.")
            sys.exit(mdig.mdig_exit_codes["model_not_found"])

        model_dir = os.path.join(self.location, model_name)
        if not os.path.isdir(model_dir):
            self.log.error("The model directory can't be found: " + model_dir)
            sys.exit(mdig.mdig_exit_codes["model_not_found"])
            
        if not force:
            ans = raw_input("Are you sure you wish to remove model " + model_name + 
                    " and it's associate mapset? [y/N] ")
            if ans.upper() == "Y":
                force = True
            else:
                self.log.error("Not removing model " + model_name)

        if force:
            import shutil
            shutil.rmtree(model_dir)
            GRASSInterface.getG().removeMapset(model_name, force)

    def get_models(self):
        models = {}
        for d in os.listdir(self.location):
            if not os.path.isdir(os.path.join(self.location, d)):
                continue
            model_file = os.path.join(self.location, d, "model.xml")
            if not os.path.isfile(model_file):
                xml_files = glob.glob(os.path.join(self.location, d, "*.xml"))
                if len(xml_files) == 1:
                    model_file = xml_files[0]
                    #logging.getLogger("mdig.repos").debug(
                        #"no model.xml for dir " + d +
                        #" - however found xml file " +
                        #os.path.basename(xml_files[0]))
                elif len(xml_files) == 0:
                    self.log.warn("No xml files in model dir " + d)
                    model_file = None
                else:
                    self.log.warn("No model.xml and more than one xml file in " + d)
                    model_file = None
            if model_file is not None:
                models[d] = model_file
        return models



