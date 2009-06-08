import os
import sys
import glob
import pdb
import logging

from mdig import MDiGConfig

class ModelRepository:

    def __init__(self, dir=None):
        self.location = None
        if dir is not None:
            if os.path.isdir(dir):
                self.location = dir
                logging.getLogger("mdig.repos").info(
                    "Using repository location " + self.location)
            else:
                raise Exception("Repository directory doesn't exist. d=" +
                        dir)
        if self.location is None:
            c = MDiGConfig.getConfig()
            self.location = c["repository"]["location"]
            logging.getLogger("mdig.repos").info(
                    "Using repository location " + self.location)
            if not os.path.isdir(self.location):
                pdb.set_trace()
                raise Exception("Repository directory doesn't exist. d=" +
                        self.location)

    def get_models(self):
        models = {}
        for d in os.listdir(self.location):
            model_file = os.path.join(self.location, "model.xml")
            if not os.path.isfile(model_file):
                xml_files = glob.glob(os.path.join(self.location, d, "*.xml"))
                if len(xml_files) == 1:
                    model_file = xml_files[0]
                    #logging.getLogger("mdig.repos").debug(
                        #"no model.xml for dir " + d +
                        #" - however found xml file " +
                        #os.path.basename(xml_files[0]))
                elif len(xml_files) == 0:
                    logging.getLogger("mdig.repos").warn(
                        "No xml files in model dir " + d)
                    model_file = None
                else:
                    logging.getLogger("mdig.repos").warn(
                        "No model.xml and more than one xml file in " + d)
                    model_file = None
            if model_file is not None:
                models[d] = model_file
        return models



