
import mdig # for exit status codes
import os
import sys

from mdig.DispersalModel import DispersalModel
from mdig.DispersalInstance import *

def split_instances_into_own_mapsets(dm):
    i_mapset = dm.create_instance_mapset_name()
    instance_node=dm.xml_model.xpath('instances/completed')
    i = dm.get_instances()
    i.set_mapset(i_mapset)
    
    # Avoid loading/looking for maps (since they'd be in the main mapset)
    c = MDiGConfig.get_config()
    if "replicate" not in c: c["replicate"] = {}
    c["replicate"]["check_complete"] = "false"

    g = GRASSInterface.get_g()
    reps = i._load_replicates()
    for r in reps:
        r._load_saved_maps(skip_check=True)
        for ls in r.saved_maps:
            for t in r.saved_maps[ls]:
                src_map=r.saved_maps[ls][t]
                src_mapset = dm.get_mapset()
                dst_map=r.get_map_name_base() + "_" + str(t)
                dst_mapset = i.get_mapset()
                # setup src_mapset in in mapset path
                # change to dest mapset
                # *then* copy map
                g.copy()

def migrate_repository(grassdb_dir):
    mr = ModelRepository(grassdb_dir)
    model_fns = mr.get_models()
    for model_fn in models_fns:
        # check for unseparated instances from main mapset
        dm = DispersalModel(model_fn)
        try:
            instances = dm.get_instances()
            for i in instances:
                mapset = i.get_mapset()
                print mapset + " ok"
        except DispersalInstanceException, e:
            if not "no longer supports instances sharing one mapset" in str(e):
                continue
            # if so, fix them
            print dm.get_mapset() + " not ok.. fixing"
            split_instances_into_own_mapsets(dm)
        dm.get_instances()
        # check existance instance_info in instance mapsets
        # if missing, then create and then rename all maps


def migrate_old_repository(old_format_dir, grassdb_dir):
    model_names = {}
    for i in os.listdir(old_format_dir):
        model_dir = os.path.join(old_format_dir,i)
        # check dir has model.xml
        if os.path.isfile( os.path.join( model_dir,'model.xml' ) ) \
            or os.path.isfile( os.path.join( model_dir,i+'.xml')):
            # create a dictionary of model names
            model_names[i] = None

    for location in os.listdir(grassdb_dir):
        mapset_dir = os.path.join(grassdb_dir,location)
        if not os.path.isdir(mapset_dir) or mapset_dir == old_format_dir: continue
        for mapset in os.listdir(mapset_dir):
            if mapset in model_names:
                model_names[mapset] = location
        
    print "Proposed changes:"
    for m in model_names:
        if model_names[m] is not None:
            print "Will move model %s to location %s" % (m, model_names[m])
        else:
            print "Couldn't find destination for model %s, will not move." % m
    ans = raw_input("Does this seem sane?\n" + \
        "(y will copy model dirs) ")
    if ans != 'y':
        print "Aborting..."
        sys.exit(0)
    import shutil
    force = False
    for m in model_names:
        if model_names[m] is not None:
            # copy if mapset found
            model_dir = os.path.join(old_format_dir,m)
            dest_dir = os.path.join(grassdb_dir,model_names[m],m,"mdig")
            print "Copying %s to %s..." % (m, dest_dir)
            if os.path.isdir(dest_dir):
                if not force:
                    ans = raw_input( "Destination dir exists, overwrite? (y/n/a) ")
                    if ans == 'a':
                        force=True
                    if ans != 'y': 
                        continue
                shutil.rmtree(dest_dir)
            shutil.copytree(model_dir,dest_dir)
    old_dir = old_format_dir

    print "Migrate complete.\n================="
    print "You will have to manually remove the" + \
            " old repository directory (or you can keep it as a backup," + \
            " just in case) currently stored at:\n%s" % old_dir

