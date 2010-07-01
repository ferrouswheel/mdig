
import mdig # for exit status codes
import os
import sys

def migrate_repository(grassdb_dir):
    pass


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

