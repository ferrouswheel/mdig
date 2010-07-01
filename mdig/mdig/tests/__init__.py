from mdig import MDiGConfig

import os
import logging
import shutil
import tempfile

test_dir = ""

__all__=['test_Model']

def setup():
    # This is why logging spews on nosetests
    #setup_logger()

    # Setup config file to use test mdig.conf which refers to test GRASS db
    MDiGConfig.MDiGConfig.config_file = os.path.join(os.path.dirname(__file__),'mdig.conf')
    
    # Copy test repository
    c = MDiGConfig.get_config()
    global test_dir
    test_dir = tempfile.mkdtemp(prefix="mdig_test_")
    end_part = os.path.split(c['GRASS']['GISDBASE'])[1]
    shutil.copytree(c['GRASS']['GISDBASE'], os.path.join(test_dir,end_part))
    c['GRASS']['GISDBASE'] = os.path.join(test_dir,end_part)

# Setup logger so that things are happy
def setup_logger():
    logger = logging.getLogger("mdig")
    #create non ANSI formatter
    ascii_formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt='%Y%m%d %H:%M:%S')
    # create handlers for each stream
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(ascii_formatter)
    logger.addHandler(ch)

def teardown():
    # Delete test repository
    if len(test_dir) > 0:
        shutil.rmtree(test_dir)
