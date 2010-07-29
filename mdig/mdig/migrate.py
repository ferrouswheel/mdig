
import mdig # for exit status codes
import os
import sys

from mdig.DispersalModel import DispersalModel
from mdig.DispersalInstance import *
from mdig.ModelRepository import ModelRepository,RepositoryException

def split_instances_into_own_mapsets(dm):
    instances = dm.get_instances()
    dm_mapset = dm.get_mapset()
    print "Splitting instances from model %s" % dm.get_name()
    for i in instances:
        try:
            i.get_mapset()
            print "Instance %d is already in own mapset, skipping..." % i.get_index()
            continue
        except DispersalInstanceException,e:
            pass
        i_mapset = dm.create_instance_mapset_name()
        i.set_mapset(i_mapset)
        sys.stdout.write("Moving instance %d into mapset %s... reps: " %
                (i.get_index(),i_mapset))
        sys.stdout.flush()
        
        # Avoid loading/looking for maps (since they'd be in the main mapset)
        c = MDiGConfig.get_config()
        if "replicate" not in c: c["replicate"] = {}
        c["replicate"]["check_complete"] = "false"

        g = GRASSInterface.get_g()
        reps = i.replicates
        src_mapset = dm_mapset
        # change to dest mapset
        i.change_mapset()
        r_count = 1
        for r in reps:
            r._load_saved_maps(skip_check=True)
            sys.stdout.write(str(r_count) + ' '); sys.stdout.flush()
            for ls in r.saved_maps:
                for t in r.saved_maps[ls]:
                    src_map=r.saved_maps[ls][t]
                    dst_map=r.get_map_name_base() + "_ls_" + ls + '_t_' + str(t)
                    # copy map
                    g.copy_map('%s@%s' % (src_map,src_mapset),dst_map)
                    # remove original
                    g.remove_map(src_map, src_mapset)
            r_count += 1
        # TODO: Also move rep/instance analysis results and envelopes?
        print ''

    dm.save_model()


def migrate_repository(grassdb_dir):
    mr = ModelRepository(grassdb_dir)
    model_fns = mr.get_models()
    for model in model_fns:
        model_fn = model_fns[model]
        # check for unseparated instances from main mapset
        dm = DispersalModel(model_fn)
        try:
            instances = dm.get_instances()
            for i in instances:
                mapset = i.get_mapset()
            if not check_instances_have_info_file(dm.get_instances()):
                print "Model %s ok" % model
        except DispersalInstanceException, e:
            if not "no longer supports instances sharing one mapset" in str(e):
                continue
            # if so, fix them
            print dm.get_mapset() + " not ok.. fixing"
            split_instances_into_own_mapsets(dm)

def check_instances_have_info_file(instances):
    # check existance instance_info in instance mapsets
    # if missing, then create and then rename all maps
    made_a_change = False
    for i in instances:
        try:
            i.check_mdig_files()
            continue
        except InstanceMetadataException, e:
            pass
        made_a_change = True
        i_mapset = i.get_mapset()
        sys.stdout.write("Fixing metadata (and also renaming maps) for instance %d... reps: " %
                i.get_index())
        sys.stdout.flush()
        
        # Avoid loading/looking for maps
        c = MDiGConfig.get_config()
        if "replicate" not in c: c["replicate"] = {}
        c["replicate"]["check_complete"] = "false"

        g = GRASSInterface.get_g()
        reps = i.replicates
        # change to dest mapset
        i.change_mapset()
        r_count = 1
        for r in reps:
            r._load_saved_maps(skip_check=True)
            sys.stdout.write(str(r_count) + ' '); sys.stdout.flush()
            for ls in r.saved_maps:
                for t in r.saved_maps[ls]:
                    src_map=r.saved_maps[ls][t]
                    dst_map=r.get_map_name_base() + "_ls_" + ls + '_t_' + str(t)
                    g.rename_map(src_map,dst_map)
            r_count += 1
        print ''
    return made_a_change

def migrate_old_repository(old_format_dir, grassdb_dir):
    model_names = {}
    for i in os.listdir(old_format_dir):
        model_dir = os.path.join(old_format_dir,i)
        # check dir has model.xml
        if os.path.isfile( os.path.join( model_dir,'model.xml' ) ) \
            or os.path.isfile( os.path.join( model_dir,i+'.xml')):
            # create a dictionary of model names
            model_names[i] = None

    old_repo_dir_name = os.path.split(old_format_dir)[1]
    for location in os.listdir(grassdb_dir):
        # in the weird case that the mdig_repo is in the GISDBASE...
        if location == old_repo_dir_name: continue
        # otherwise check for a matching mapset name
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
        return False
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
    return True

