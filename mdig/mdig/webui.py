from bottle import route, validate, request, redirect, abort, view, send_file
import bottle

from multiprocessing import Process, Queue, JoinableQueue
from threading import Thread
import Queue as q

import os
import sys
import re
import tempfile
import shutil
import datetime
import logging

import mdig
from model import DispersalModel, ValidationError
import config
import grass
import modelrepository

from mdig.instance import InstanceIncompleteException
from mdig.modelrepository import RepositoryException

app = None
log = logging.getLogger('mdig.web')

reloader = False
root_dir = sys.path[0]
if True:
    bottle.debug(True)
    sys.path.insert(0, os.path.join(root_dir, 'mdig'))
    # reloader is nice, but it loads all module code twice and this
    # confuses the GRASS module.
    # reloader = True

# where js, css, and more are kept
resource_dir = os.path.join(root_dir, 'mdig/views/resources/')

# needed for error template to find bottle...
bottle.TEMPLATE_PATH = [
        os.path.join(root_dir, 'mdig/views/'),
        os.path.join(root_dir, 'mdig/')
        ]

# Which models are currently doing something.
# Each item to have format: [ACTION, state]
models_in_queue = {}

# when the last status headline display completed tasks
last_notice = datetime.datetime.now()

# This queue is used to submit jobs to an mdig process(es) that will run simulations
# and do computational tasks that can be done immediately
work_q = JoinableQueue()

# When the mdig process(es) have completed (either totally or partly) a job
# from the work_q, it will put the results here
results_q = Queue()

# Template for the messages that get passed in the queues
msg_template = {
    "model": "model_name",
    "action": "RUN|OCCUPANCY_GIF|REPLICATE_GIF",
    "status": {
        "description": "status message to be displayed",
        "complete": "true|false",
        "percent_done": "percentage of work done",
        "active_instance": "currently running instance",
        "active_replicate": "current index of rep",
        "error": "error message - implies task failed"
    },
    "parameters": {
        "instance_idx": "for instance specific tasks",
        "lifestage": "for lifestage specific tasks",
        "rerun": "for rerunning",
        "etc": None
    }
}

# dictionary which tracks the last access of map_packs so that we can delete
# the least frequently used
# values are (fn,date) and sorted so that oldest at position 0
map_pack_lfu = []


@route('/models')
@route('/models/')
def redirect_index():
    redirect('/')


def validate_model_name(mname):
    # Get existing models in repository
    models = mdig.repository.get_models()
    if mname not in models.keys():
        abort(404, "No such model")
    try:
        dm = DispersalModel(models[mname])
    except mdig.model.ValidationError:
        abort(500, "Model %s is badly formed" % mname)
    # Hack to get instances to initialise mapsets if they need to
    # and then save them
    dm.get_instances()
    dm.save_model()
    return dm


def validate_instance(dm, instance_idx):
    return instance_idx >= 0 and instance_idx < len(dm.get_instances())


def validate_replicate(instance, rep_num):
    return rep_num >= 0 and rep_num < len(instance.replicates)


@route('/models/', method="POST")
@view('submit.tpl')
def submit_model():
    model_file = request.POST.get('new_model')
    data = model_file.file.read()
    # Use ModelRepository to add model, but we'll need to implement a method
    # that accepts a string and uses a temp file as a proxy.
    error_template = { "name": mdig.version_string }
    try:
        model_name = add_model_to_repo(data)
    except ValidationError, e:
        error_template['error'] = "Error parsing model xml. Validation said:\n%s" % str(e)
        return error_template
    except modelrepository.RepositoryException, e:
        if "already exists" in str(e):
            error_template['error'] = "Model already exists in repository."
        else:
            error_template['error'] = "Error adding model to repository: %s" % str(e)
        return error_template
    # Try to successfully load model
    mdig.repository.get_models()[model_name]
    redirect('/')


def get_map_pack_usage():
    # TODO: This code is not particularly useful, since it doesn't
    # remember map packs generated between runs of a server.

    # sum storage to check if we actually need to delete anything
    sum_storage_mb = 0.0
    to_remove = []
    for i in range(0, len(map_pack_lfu)):
        fn, date = map_pack_lfu[i]
        try:
            sum_storage_mb += float(os.path.getsize(fn)) / (1024*1024)
        except OSError:
            if date is not None:
                to_remove.append(i)
    for i in to_remove:
        del map_pack_lfu[i]
    return sum_storage_mb


def purge_oldest_map_packs():
    # If we are using too much storage, AND
    # If there is only one don't delete, even if it is very big
    allowed_use = float(config.get_config()['WEB']['map_pack_storage']) 
    while get_map_pack_usage() > allowed_use and len(map_pack_lfu) > 1:
        # Delete oldest at position 0
        fn, date = map_pack_lfu[0]
        del map_pack_lfu[0]
        try:
            os.remove(fn)
        except OSError, e:
            if "No such file" not in str(e):
                # ignore missing files, since we're trying to remove them anyhow
                raise e


def add_to_map_pack_lfu(fn, nodate=False):
    index = None
    for i in range(0, len(map_pack_lfu)):
        xfn, xdate = map_pack_lfu[i]
        if fn == xfn:
            index = i
            break
    if index is not None:
        del map_pack_lfu[index]
    if nodate:
        map_pack_lfu.append((fn, None))
    else:
        map_pack_lfu.append((fn, datetime.datetime.now()))


def process_tasks():
    """
    Go through all the tasks in models_in_queue and when they were completed.

    Return those that have been completed since last time this method was called.
    """
    global last_notice
    new_last_notice = last_notice
    updates = {}
    time_index = {}
    to_remove = []
    for m_name, tasks in models_in_queue.items():
        for task_name in tasks:
            t = tasks[task_name]
            if 'complete' in t:
                # deal with completion events which should only display once
                if datetime.datetime.now() - t['last_update'] \
                        > datetime.timedelta(days=7):
                    # remove tasks that are complete but older than a week
                    to_remove.append((m_name, task_name))
                if t['complete'] <= last_notice:
                    continue
                if m_name not in updates:
                    updates[m_name] = {}
                updates[m_name][task_name] = t
                complete_time = t['complete']
                if new_last_notice < complete_time:
                    new_last_notice = complete_time
                time_index[(m_name, task_name)] = complete_time
            elif 'error' in t:
                # deal with error events which should only display once
                if t['last_update'] <= last_notice:
                    continue
                if m_name not in updates:
                    updates[m_name] = {}
                updates[m_name][task_name] = t
                err_time = t['last_update']
                if new_last_notice < err_time:
                    new_last_notice = err_time
                time_index[(m_name, task_name)] = err_time
            elif 'complete' not in t:
                # deal with status of incomplete tasks
                if m_name not in updates:
                    updates[m_name] = {}
                updates[m_name][task_name] = t
                time_index[(m_name, task_name)] = t['last_update']
    for m_name, task in to_remove:
        del models_in_queue[m_name][task]
    last_notice = new_last_notice
    k = time_index.keys()
    k.sort(key=lambda x: time_index[x])
    return k, updates


@route('/models/:model/del', method='POST')
def del_model(model):
    # TODO ensure the model isn't running or in the job queue!
    try:
        mdig.repository.remove_model(model, force=True)
    except RepositoryException, e:
        if "doesn't exist in the repository" in str(e):
            abort(404, "No such model")
        abort(500, "Repository Error")
    redirect('/')


@route('/models/:model/run', method='POST')
@view('run.tpl')
@validate(model=validate_model_name)
def run_model(model):
    global models_in_queue
    qsize = work_q.qsize()
    m_name = model.get_name()
    exists = False
    rerun = False
    started = None
    i_specified = None
    if "rerun" in request.POST:
        if request.POST["rerun"].lower() == "true":
            rerun = True
    if not model.is_complete() or rerun:
        instance_idxs = None
        if "instance" in request.POST:
            instance_idxs = [int(request.POST["instance"])]
            i_specified = instance_idxs
        else:
            instance_idxs = [x for x in range(0, len(model.get_instances()))]
        if m_name not in models_in_queue:
            models_in_queue[m_name] = {}
        if 'RUN' in models_in_queue[m_name] and 'complete' not in models_in_queue[m_name]['RUN']:
            exists = True
        else:
            models_in_queue[m_name]['RUN'] = {"approx_q_pos": qsize,
                                              "last_update": datetime.datetime.now()}
            work_q.put({'action': 'RUN', 'model': m_name,
                        'parameters': {"rerun": rerun, "instances": instance_idxs}})
        started = 'started' in models_in_queue[m_name]['RUN']
    task_order, task_updates = process_tasks()
    return dict(model=model, already_exists=exists, rerun=rerun,
                complete=model.is_complete() and not rerun,
                started=started,
                name=mdig.version_string,
                queue_size=qsize, instance_idx=i_specified,
                task_order=task_order, task_updates=task_updates)


def add_model_to_repo(data):
    """ Create a temporary directory to store a model file and extract required
    files.
    """
    # import lxml
    # make temp dir
    temp_model_dir = tempfile.mkdtemp(prefix="mdig_web")
    # write data to actual file
    model_fn = os.path.join(temp_model_dir, "model.xml")
    f = open(model_fn, 'w')
    f.write(data)
    f.close()
    model_name = mdig.repository.add_model(model_fn)
    # remove temp dir/file
    shutil.rmtree(temp_model_dir)
    return model_name


@route('/')
@view('index.tpl')
def index():
    # Get existing models in repository
    models = mdig.repository.get_models()
    ms = models.keys()[:]
    ms.sort()

    m_list = []
    for m in ms:
        try:
            dm = DispersalModel(models[m], setup=False)
            desc = dm.get_description()
            desc = re.sub("[\\s\\t]+", " ", desc)
            m_list.append((m, desc, dm.infer_location()))
        except mdig.model.ValidationError, e:
            log.error(str(e))

    env = grass.get_g().get_gis_env()
    task_order, task_updates = process_tasks()
    return dict(name=mdig.version_string, version=mdig.version,
                v_name=mdig.version_name, models=m_list,
                repo_location=mdig.repository.db,
                grass_env=env,
                task_order=task_order, task_updates=task_updates)


@route('/models/:model', method='GET')
@route('/models/:model', method='POST')
@view('model.tpl')
@validate(model=validate_model_name)
def show_model(model):
    dm = model
    if request.method == "POST":
        to_enable = [int(x) for x in request.POST.getall('enabled')]
        if len(to_enable) != 0:
            i_index = 0
            for i in dm.get_instances():
                if i.enabled and i_index not in to_enable:
                    i.enabled = False
                    i.update_xml()
                if not i.enabled and i_index in to_enable:
                    i.enabled = True
                    i.update_xml()
                i_index += 1
            dm.save_model()
        # event_to_remove = request.POST.getall('delEvent')]
        # elif if len(event_to_remove) > 0:
        #    ls.delEvent(
    active_instances = []
    m = dm.get_name()
    if m in models_in_queue:
        if 'RUN' in models_in_queue[m]:
            if 'status' in models_in_queue[m]['RUN']:
                if 'active_instance' in models_in_queue[m]['RUN']['status']:
                    active_instances.append(models_in_queue[
                                            m]['RUN']['status']['active_instances'])
    task_order, task_updates = process_tasks()
    missing_resources = [i for i in dm.get_resources() if i[2] is None]
    return dict(model=dm, name=mdig.version_string,
                repo_location=mdig.repository.db,
                task_order=task_order, task_updates=task_updates,
                active_instances=active_instances,
                missing_resources=missing_resources)


@route('/models/:model/instances/:instance', method='GET')
@route('/models/:model/instances/:instance', method='POST')
@view('instance.tpl')
@validate(instance=int, model=validate_model_name)
def show_instance(model, instance):
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    envelope = None
    error = None
    m_name = dm.get_name()

    # Scan output dir to see if gifs have been generated for this instance
    envelopes_present = []
    for ls_id in instance.experiment.get_lifestage_ids():
        # if there is an envelope generated then collect it
        fn = instance.get_occ_envelope_img_filenames(ls=ls_id, gif=True)
        if os.path.isfile(fn):
            # get creation time
            mtime = datetime.datetime.fromtimestamp(os.stat(fn).st_mtime)
            envelopes_present.append((ls_id, mtime))
        else:
            envelopes_present.append((ls_id, None))

    # Scan output dir to see if map_packs have been generated for this instance
    map_packs_present = []
    for ls_id in instance.experiment.get_lifestage_ids():
        fn = instance.get_occ_envelope_img_filenames(
            ls=ls_id, extension=False, gif=True)[:-5] + '.zip'
        if os.path.isfile(fn):
            # get creation time
            mtime = datetime.datetime.fromtimestamp(os.stat(fn).st_mtime)
            # add to list
            map_packs_present.append((ls_id, mtime))
        else:
            map_packs_present.append((ls_id, None))

    task_order, task_updates = process_tasks()
    # TODO update template to display error message
    return dict(idx=idx, instance=instance, name=mdig.version_string,
                envelopes_present=envelopes_present,
                map_packs_present=map_packs_present,
                repo_location=mdig.repository.db,
                task_order=task_order, task_updates=task_updates, error=error)


@route('/models/:model/instances/:instance/replicates/:replicate', method='GET')
@route('/models/:model/instances/:instance/replicates/:replicate', method='POST')
@view('replicate.tpl')
@validate(replicate=int, instance=int, model=validate_model_name)
def show_replicate(model, instance, replicate):
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    rep_num = int(replicate)
    if not validate_replicate(instance, rep_num):
        abort(404, "No such replicate, or replicate doesn't exist yet")
    rep = instance.replicates[rep_num]
    error = None

    # Scan output dir to see if gifs have been generated for this instance
    gifs_present = []
    for ls_id in instance.experiment.get_lifestage_ids():
        # if there is an envelope generated then collect it
        fn = rep.get_base_filenames(ls=ls_id, single_file=True, extension='_anim.gif')
        if os.path.isfile(fn):
            # get creation time
            mtime = datetime.datetime.fromtimestamp(os.stat(fn).st_mtime)
            gifs_present.append((ls_id, mtime))
        else:
            gifs_present.append((ls_id, None))

    # Scan output dir to see if map_packs have been generated for this instance
    map_packs_present = []
    for ls_id in instance.experiment.get_lifestage_ids():
        fn = rep.get_base_filenames(ls=ls_id, extension='.zip', single_file=True)
        if os.path.isfile(fn):
            # get creation time
            mtime = datetime.datetime.fromtimestamp(os.stat(fn).st_mtime)
            # add to list
            map_packs_present.append((ls_id, mtime))
        else:
            map_packs_present.append((ls_id, None))

    task_order, task_updates = process_tasks()
    # TODO update template to display error message
    return dict(
        idx=idx, instance=instance, replicate=rep, name=mdig.version_string,
        gifs_present=gifs_present, repo_location=mdig.repository.db,
        map_packs_present=map_packs_present,
        task_order=task_order, task_updates=task_updates, error=error)

# Following methods are for getting and creating occupancy envelopes


def submit_occupancy_envelope_job(dm, idx, ls_id, action):
    instance = dm.get_instances()[idx]
    added = False
    m_name = dm.get_name()
    if instance.is_complete():
        if m_name not in models_in_queue:
            models_in_queue[m_name] = {}
        else:
            log.info("Model name already in queue")
        if action in models_in_queue[m_name] and \
                'complete' not in models_in_queue[m_name][action]:
            # job already exists
            exists = True
        elif ls_id not in dm.get_lifestage_ids():
            # Invalid lifestage ID
            error = "Invalid lifestage ID"
        else:
            qsize = work_q.qsize()
            models_in_queue[m_name][action] = {
                "approx_q_pos": qsize,
                "last_update": datetime.datetime.now()
            }
            work_q.put({
                "action": action,
                "model": dm.get_name(),
                "parameters": {
                    "instance_idx": idx,
                    "lifestage": ls_id
                }
            })
            added = True
    else:
        # if instance isn't complete, then we can't create an
        # occupancy envelope
        raise InstanceIncompleteException(
            "The instance isn't complete, can't create envelope")
    return added


@route('/models/:model/instances/:instance/:ls_id/envelope.gif', method='POST')
@validate(instance=int, model=validate_model_name)
def create_instance_occ_envelope_gif(model, instance, ls_id):
    """ Create a job to generate the occupancy envelope for an instance and
    convert to a gif """
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    # submit a job to generate the occupancy envelope
    ls_id = request.POST['envelope']
    print ls_id
    try:
        submit_occupancy_envelope_job(dm, idx, ls_id, 'OCCUPANCY_GIF')
    except InstanceIncompleteException:
        redirect('/models/%s/instances/%s' % (model.get_name(), idx))
    redirect('/models/%s/instances/%s' % (model.get_name(), idx))


@route('/models/:model/instances/:instance/:ls_id/envelope.gif')
@validate(instance=int, model=validate_model_name)
def instance_occ_envelope_gif(model, instance, ls_id):
    """ Return the occupancy envelope for an instance as a gif """
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    # do per lifestage!
    fn = instance.get_occ_envelope_img_filenames(ls=ls_id, gif=True)
    root_dir = os.path.dirname(fn)
    send_file(os.path.basename(fn), root=root_dir)


@route('/models/:model/instances/:instance/:ls_id/map_pack.zip', method='POST')
@validate(instance=int, model=validate_model_name)
def create_instance_occ_envelope_map_pack(model, instance, ls_id):
    """ Create the occupancy envelopes for an instance and export to a map pack
    of GeoTIFFs """
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    # submit a job to generate the occupancy envelope
    ls_id = request.POST['map_pack']
    action = 'OCCUPANCY_MAP_PACK'
    try:
        submit_occupancy_envelope_job(dm, idx, ls_id, action)
    except InstanceIncompleteException:
        redirect('/models/%s/instances/%s' % (model.get_name(), idx))
    purge_oldest_map_packs()
    fn = instance.get_occ_envelope_img_filenames(
        ls=ls_id, extension=False, gif=True)
    fn += '.zip'
    add_to_map_pack_lfu(fn, nodate=True)
    redirect('/models/%s/instances/%s' % (model.get_name(), idx))


@route('/models/:model/instances/:instance/:ls_id/map_pack.zip')
@validate(instance=int, model=validate_model_name)
def instance_occ_envelope_map_pack(model, instance, ls_id):
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    # do per lifestage!
    fn = instance.get_occ_envelope_img_filenames(
        ls=ls_id, extension=False, gif=True)
    fn += '.zip'
    if os.path.isfile(fn):
        add_to_map_pack_lfu(fn)
        root_dir = os.path.dirname(fn)
        send_file(os.path.basename(fn), root=root_dir)
    abort(404, "No map pack generated")

####################
### Following methods are for getting and creating replicate maps
# redirect('/models/%s/instances/%s/replicates/%s' %
# (model.get_name(),idx,replicate))


def submit_replicate_job(dm, idx, rep_num, ls_id, action):
    instance = dm.get_instances()[idx]
    rep = instance.replicates[rep_num]
    m_name = dm.get_name()
    added = False
    if rep.complete:
        if m_name not in models_in_queue:
            models_in_queue[m_name] = {}
        if action in models_in_queue[m_name] and \
                'complete' not in models_in_queue[m_name][action]:
            exists = True
        elif ls_id not in dm.get_lifestage_ids():
            # Invalid lifestage ID
            error = "Invalid lifestage ID"
        else:
            qsize = work_q.qsize()
            models_in_queue[m_name][action] = {"approx_q_pos": qsize,
                                               "last_update": datetime.datetime.now()}
            job_details = {"instance_idx": idx, "lifestage": ls_id,
                           "replicate": rep_num}
            work_q.put({'action': action, 'model':
                       dm.get_name(), 'parameters': job_details})
            added = True
    else:
        error = "The replicate isn't complete, please run the instance first"
    return added


@route('/models/:model/instances/:instance/replicates/:replicate/:ls_id/spread.gif', method='POST')
@validate(replicate=int, instance=int, model=validate_model_name)
def create_replicate_gif(model, instance, replicate, ls_id):
    """ Create animated gif of replicate """
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    if not validate_replicate(instance, replicate):
        abort(404, "No such replicate, or replicate doesn't exist yet")
    # submit a job to generate the occupancy envelope
    ls_id = request.POST['gif']
    action = 'REPLICATE_GIF'
    submit_replicate_job(dm, idx, replicate, ls_id, action)
    redirect('/models/%s/instances/%d/replicates/%d' %
            (model.get_name(), idx, replicate))


@route('/models/:model/instances/:instance/replicates/:replicate/:ls_id/spread.gif')
@validate(replicate=int, instance=int, model=validate_model_name)
def replicate_spread_gif(model, instance, replicate, ls_id):
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    replicate = int(replicate)
    if not validate_replicate(instance, replicate):
        abort(404, "No such replicate, or replicate doesn't exist yet")
    r = instance.replicates[replicate]
    # do per lifestage!
    fn = r.get_base_filenames(ls=ls_id, extension='_anim.gif', single_file=True)
    root_dir = os.path.dirname(fn)
    send_file(os.path.basename(fn), root=root_dir)


@route('/models/:model/instances/:instance/replicates/:replicate/:ls_id/map_pack.zip', method='POST')
@validate(replicate=int, instance=int, model=validate_model_name)
def create_replicate_map_pack(model, instance, replicate, ls_id):
    """ Export the maps of a replicate to a map pack of GeoTIFFs """
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    if not validate_replicate(instance, replicate):
        abort(404, "No such replicate, or replicate doesn't exist yet")
    # submit a job to generate the occupancy envelope
    ls_id = request.POST['map_pack']
    action = 'REPLICATE_MAP_PACK'
    submit_replicate_job(dm, idx, replicate, ls_id, action)
    purge_oldest_map_packs()
    r = instance.replicates[replicate]
    fn = r.get_base_filenames(ls=ls_id, extension='_anim.zip', single_file=True)
    add_to_map_pack_lfu(fn, nodate=True)
    redirect('/models/%s/instances/%d/replicates/%d' %
            (model.get_name(), idx, replicate))


@route('/models/:model/instances/:instance/replicates/:replicate/:ls_id/map_pack.zip')
@validate(replicate=int, instance=int, model=validate_model_name)
def replicate_map_pack(model, instance, replicate, ls_id):
    dm = model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    replicate = int(replicate)
    if not validate_replicate(instance, replicate):
        abort(404, "No such replicate, or replicate doesn't exist yet")
    r = instance.replicates[replicate]
    # do per lifestage!
    fn = r.get_base_filenames(ls=ls_id, extension='_anim.zip', single_file=True)
    if os.path.isfile(fn):
        add_to_map_pack_lfu(fn)
        root_dir = os.path.dirname(fn)
        send_file(os.path.basename(fn), root=root_dir)
    abort(404, "No map pack generated")


@route('/resources/:filename#.*#')
def static_resources(filename):
    send_file(filename, root=resource_dir)


@route('/favicon.ico')
def static_resources():
    send_file("favicon.ico", root=resource_dir)


class Worker_InstanceListener():

    def __init__(self, results_q):
        self.results_q = results_q

    def replicate_complete(self, rep):
        instance = rep.instance
        model = instance.experiment
        percent = len([x for x in instance.replicates if x.complete])/float(
            model.get_num_replicates())
        percent = percent * 100.0
        msg = {'action': 'RUN', 'model': model.get_name(), 'status': {
            "active_instance": model.get_instances().index(instance),
            "percent_done": percent}}
        self.results_q.put(msg)

    def occupancy_envelope_complete(self, instance, ls, t):
        model = instance.experiment
        start, end = model.get_period()
        percent = float(int(t) - start) / (end - start)
        percent = percent * 100.0
        msg = {'action': 'OCCUPANCY_GIF', 'model': model.get_name(), 'status': {
            "active_instance": model.get_instances().index(instance),
            "percent_done": percent}}
        self.results_q.put(msg)

    def export_image_complete(self, instance, replicate, ls, t):
        if replicate:
            instance = replicate.instance
        model = instance.experiment
        start, end = model.get_period()
        # bad bad t is a string, this should be fixed
        percent = float(int(t) - start) / (end - start)
        percent = percent * 100.0
        if replicate:
            msg = {'action': 'REPLICATE_GIF', 'model': model.get_name(),
                   'status': {
                       "active_instance": model.get_instances().index(instance),
                       "active_replicate": instance.replicates.index(replicate),
                       "percent_done": percent}}
        else:
            msg = {'action': 'OCCUPANCY_GIF', 'model': model.get_name(),
                   'status': {
                       "active_instance": model.get_instances().index(instance),
                       "percent_done": percent}}
        self.results_q.put(msg)

    def export_map_pack_complete(self, instance, replicate, ls, t):
        if replicate:
            instance = replicate.instance
        model = instance.experiment
        start, end = model.get_period()
        # bad bad t is a string, this should be fixed
        percent = float(int(t) - start) / (end - start)
        percent = percent * 100.0
        if replicate:
            msg = {'action': 'REPLICATE_MAP_PACK', 'model': model.get_name(),
                   'status': {
                       "active_instance": model.get_instances().index(instance),
                       "active_replicate": instance.replicates.index(replicate),
                       "percent_done": percent}}
        else:
            msg = {'action': 'OCCUPANCY_MAP_PACK', 'model': model.get_name(),
                   'status': {
                       "active_instance": model.get_instances().index(instance),
                        "percent_done": percent}}
        self.results_q.put(msg)


class MDiGWorker():

    def __init__(self, work_q, results_q):
        self.work_q = work_q
        self.results_q = results_q
        self.running = True
        self.log = logging.getLogger('mdig.worker')
        self.listener = Worker_InstanceListener(self.results_q)

    def run_model(self, m_name, instances, rerun=False):

        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        if rerun:
            dm.reset_instances()
        msg = {
                'model': m_name,
                'action': "RUN",
                'status': {
                    'started': datetime.datetime.now()
                    }
              }
        self.results_q.put(msg)
        i_objs = dm.get_instances()
        for instance in instances:
            i = i_objs[instance]
            i.listeners.append(self.listener)
            msg = {
                    'model': m_name,
                    'action': "RUN",
                    'status': {
                        'active_instance': instance
                        }
                  }
            i.run()
        msg = {'model': m_name, 'action': "RUN",
                'status': {'complete': datetime.datetime.now()}}
        self.results_q.put(msg)

    def create_occupancy_gif(self, m_name, instance_idx=None, ls=None):
        action = "OCCUPANCY_GIF"

        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)

        instance = dm.get_instances()[instance_idx]
        # Tell web interface we've started
        msg = {
                'model': m_name,
                'action': action,
                'status': {
                    'started': datetime.datetime.now()
                    }
                }
        self.results_q.put(msg)

        self.log.debug("Checking/creating envelopes")
        # Tell web interface what we're doing
        msg = {
                'model': m_name,
                'action': action,
                'status': {
                    'active_instance': instance_idx,
                    'description': "Creating occupancy envelopes"
                    }
                }
        self.results_q.put(msg)

        # Add listener so that we have progress updates
        instance.listeners.append(self.listener)

        # ...now actually create the envelopes if necessary
        instance.update_occupancy_envelope(ls_list=[ls])

        # ...now convert occupancy envelopes into images via ExportAction
        from actions import ExportAction
        ea = ExportAction()
        ea.parse_options([])
        ea.options.output_gif = True
        ea.options.output_image = True
        ea.options.output_lifestage = ls
        ea.options.overwrite_flag = True
        ea.listeners.append(self.listener)
        self.log.debug("Generating images")

        msg = {
                'model': m_name,
                'action': action,
                'status': {
                    'active_instance': instance_idx,
                    'description': "Generating images"
                    }
                }
        self.results_q.put(msg)

        ea.do_instance(instance)

        dm.save_model()
        msg = {
                'model': m_name,
                'action': action,
                'status': {
                    'complete': datetime.datetime.now()
                    }
                }
        self.results_q.put(msg)

    def create_occupancy_map_pack(self, m_name, instance_idx=None, ls=None):
        action = "OCCUPANCY_MAP_PACK"
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        instance = dm.get_instances()[instance_idx]
        # Tell web interface we've started
        msg = {'model': m_name, 'action': action,
                'status': {'started': datetime.datetime.now()}}
        self.results_q.put(msg)
        self.log.debug("Checking/creating envelopes")
        # Tell web interface what we're doing
        msg = {'model': m_name, 'action': action,
                'status': {'active_instance': instance_idx, 'description': "Creating occupancy envelopes"}}
        self.results_q.put(msg)
        # Add listener so that we have progress updates
        instance.listeners.append(self.listener)
        # Now actually create the envelopes if necessary
        instance.update_occupancy_envelope(ls_list=[ls])
        # also convert occupancy envelopes into images
        # via ExportAction
        from actions import ExportAction
        ea = ExportAction()
        ea.parse_options([])
        ea.options.output_map_pack = True
        ea.options.output_lifestage = ls
        ea.options.overwrite_flag = True
        ea.listeners.append(self.listener)
        self.log.debug("Exporting maps")
        msg = {'model': m_name, 'action': action,
                'status': {'active_instance': instance_idx,
                    'description': "Exporting maps"}}
        self.results_q.put(msg)
        try:
            ea.do_instance(instance)
        except:
            raise
        msg = {'model': m_name, 'action': action, 'status': {
            'complete': datetime.datetime.now()}}
        self.results_q.put(msg)

    def create_replicate_gif(self, m_name, instance_idx, replicate, ls):
        action = "REPLICATE_GIF"
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        instance = dm.get_instances()[instance_idx]
        # Tell web interface we've started
        msg = {'model': m_name, 'action': action,
                'status': {'started': datetime.datetime.now(),
                'active_instance': instance_idx,
                'description': "Generating images",
                'active_replicate': replicate}}
        self.results_q.put(msg)
        # Add listener so that we have progress updates
        instance.listeners.append(self.listener)
        # also convert replicate maps into images
        # via ExportAction
        from actions import ExportAction
        ea = ExportAction()
        ea.parse_options([])
        ea.options.output_gif = True
        ea.options.output_image = True
        ea.options.output_lifestage = ls
        ea.options.overwrite_flag = True
        ea.options.reps = [replicate]
        try:
            ea.do_instance(instance)
        except:
            raise
        msg = {'model': m_name, 'action': action,
                'status': {
                'active_instance': instance_idx,
                'description': "Generating images",
                'active_replicate': replicate,
                'complete': datetime.datetime.now()}}
        self.results_q.put(msg)

    def create_replicate_map_pack(self, m_name, instance_idx, replicate, ls):
        action = "REPLICATE_MAP_PACK"
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        instance = dm.get_instances()[instance_idx]
        # Tell web interface we've started
        msg = {'model': m_name, 'action': action,
                'status': {'started': datetime.datetime.now(),
                'active_instance': instance_idx,
                'description': "Generating images",
                'active_replicate': replicate}}
        self.results_q.put(msg)
        # Add listener so that we have progress updates
        instance.listeners.append(self.listener)
        # also convert replicate maps into images
        # via ExportAction
        from actions import ExportAction
        ea = ExportAction()
        ea.parse_options([])
        ea.options.output_map_pack = True
        ea.options.output_lifestage = ls
        ea.options.overwrite_flag = True
        ea.options.reps = [replicate]
        try:
            ea.do_instance(instance)
        except:
            raise
        msg = {'model': m_name, 'action': action,
                'status': {
                'active_instance': instance_idx,
                'description': "Generating images",
                'active_replicate': replicate,
                'complete': datetime.datetime.now()}}
        self.results_q.put(msg)

    def run(self):
        # NOTE: To add a pdb statement to this process you need to use:
        # (of course, this only works in *nix)
        # import pdb;
        # pdb.Pdb(stdin=open('/dev/stdin', 'r+'), stdout=open('/dev/stdout',
        # 'r+')).set_trace()

        # Hack to fix errant Windows behaviour (should inherit from parent
        # process)
        import mdig
        if mdig.repository is None:
            import mdig.modelrepository
            mdig.repository = mdig.modelrepository.ModelRepository()
        while self.running:
            s = None
            try:
                s = self.work_q.get(timeout=1)
                action = s['action']  # the action to perform
                if 'model' in s:
                    m_name = s['model']  # the model it applies to
                if action == "SHUTDOWN":
                    self.running = False
                elif action == "RUN":
                    rerun = s['parameters']['rerun']
                    instances = s['parameters']['instances']
                    self.run_model(m_name, instances, rerun=rerun)
                elif action == "OCCUPANCY_GIF":
                    # format of s[2]:
                    # { "instance_idx": idx, "lifestage": ls_id }
                    ls_id = s['parameters']['lifestage']
                    instance_idx = s['parameters']['instance_idx']
                    self.create_occupancy_gif(m_name, instance_idx, ls_id)
                elif action == "REPLICATE_GIF":
                    ls_id = s['parameters']['lifestage']
                    instance_idx = s['parameters']['instance_idx']
                    rep = s['parameters']['replicate']
                    self.create_replicate_gif(m_name, instance_idx, rep, ls_id)
                elif action == "OCCUPANCY_MAP_PACK":
                    ls_id = s['parameters']['lifestage']
                    instance_idx = s['parameters']['instance_idx']
                    self.create_occupancy_map_pack(m_name, instance_idx, ls_id)
                elif action == "REPLICATE_MAP_PACK":
                    ls_id = s['parameters']['lifestage']
                    instance_idx = s['parameters']['instance_idx']
                    rep = s['parameters']['replicate']
                    self.create_replicate_map_pack(
                        m_name, instance_idx, rep, ls_id)
                else:
                    self.log.error("Unknown task: %s" % str(s))
                self.work_q.task_done()
            except q.Empty:
                pass
            except Exception, e:
                import traceback
                self.log.error(
                    "Unexpected exception in worker process: %s" % str(e))
                traceback.print_exc()
                if not s:
                    # Very rarely, s will be None when shutting down
                    self.running = False
                    continue
                # Send error notice back to web interface
                s = s.copy()
                s.setdefault('status', {})
                s['status']['error'] = str(e)
                self.results_q.put(s)
                self.work_q.task_done()
        self.clean_up()

    def clean_up(self):
        g = grass.get_g()
        g.clean_up()


def mdig_worker_start(work_q, results_q):
    # Have to replace some of the environment variables, otherwise they get
    # remembered and will confuse original Web server process
    g = grass.get_g()
    g.init_pid_specific_files()
    g.grass_vars["MAPSET"] = "PERMANENT"
    g.set_gis_env()

    worker = MDiGWorker(work_q, results_q)
    try:
        worker.run()
    except KeyboardInterrupt, e:
        worker.running = False
        worker.clean_up()


class ResultMonitor(Thread):
    def __init__(self, result_q):
        Thread.__init__(self)
        self.result_q = result_q
        self.running = False
        self.log = logging.getLogger('mdig.rm')

    def run(self):
        self.running = True
        global models_in_queue
        while self.running:
            try:
                s = self.result_q.get(timeout=1)
                self.log.debug("Received" + str(s))
                self.log.debug("Before: " + str(models_in_queue))
                m_action = s['action']
                if 'model' in s:
                    m_name = s['model']
                    if 'started' in s['status']:
                        # if just started then nuke existing status
                        models_in_queue[m_name][m_action] = s['status']
                    else:
                        # otherwise we should just update the status object
                        models_in_queue[m_name][m_action].update(s['status'])
                    models_in_queue[m_name][m_action][
                        'last_update'] = datetime.datetime.now()
                    self.log.debug("After: " + str(models_in_queue))
            except q.Empty:
                pass
            except Exception, e:
                import traceback
                self.log.error(
                    "Unexpected exception in result monitor process: %s" % str(e))
                traceback.print_exc()

# This thread monitors the results_q and updates the local process status (since
# there is no easy other way except processing the queues on HTTP requests, and
# this would potentially lead to slow responsiveness).
rt = ResultMonitor(results_q)
# spawn a thread with mdig.py and use a multiprocessing queue
mdig_worker_process = Process(
    target=mdig_worker_start, args=(work_q, results_q))

# Wrapper middleware to ensure the WebService returns to mdig_webservice


class RestoreMapset:

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        # The awesomest cleanup code care of:
        # http://code.google.com/p/modwsgi/wiki/RegisteringCleanupCode
        try:
            return self.application(environ, start_response)
        finally:
            change_to_web_mapset()


def start_web_service():
    change_to_web_mapset()
    rt.start()
    mdig_worker_process.start()

    # setup and run webapp
    global app
    app = bottle.app()
    app.catchall = False
    try:
        import paste.evalexception
        myapp = paste.evalexception.middleware.EvalException(app)
    except ImportError:
        myapp = app
    myapp = RestoreMapset(myapp)
    c = config.get_config()
    # Don't check replicates are complete, since this will make the web service
    # too slow if there are lots of replicates
    if "replicate" not in c:
        c["replicate"] = {}
    c["replicate"]["check_complete"] = "false"
    # for testing ports available in windows
    # c["WEB"]["port"] = 8080
    bottle.run(app=myapp, host=c["WEB"]["host"], port=int(
        c["WEB"]["port"]), reloader=reloader)

# Store the web mapsets that have been created so that we can tidy up afterwards
# indexed by location, since webservice can potentially move around locations
mapsets = {}


def change_to_web_mapset():
    log.debug("Changing the web service mapset")
    g = grass.get_g(create=False)
    ms = "mdig_webservice"
    if not g.check_mapset(ms):
        g.change_mapset(ms, create=True)
        mapsets[g.grass_vars["LOCATION_NAME"]] = ms
    else:
        g.change_mapset(ms)


def shutdown_webapp():
    if app is None:
        return
    log.info("Shutting down the web service...")
    rt.running = False
    work_q.put({'action': "SHUTDOWN"})
    if mdig_worker_process.pid:
        mdig_worker_process.join()
    g = grass.get_g(create=False)
    # Remove webservice mapsets
    log.debug("Removing temporary mapsets")
    global mapsets
    for loc in mapsets:
        g.remove_mapset(mapsets[loc], loc, force=True)
