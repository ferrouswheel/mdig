from bottle import route, validate, request, redirect, abort
from bottle import view
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

import pdb

import mdig
from DispersalModel import DispersalModel
import MDiGConfig
import GRASSInterface

app = None

reloader = False
if True:
    bottle.debug(True)
    sys.path.insert(0, './mdig/')
    # reloader is nice, but it loads all module code twice and this
    # confuses the GRASS module.
    #reloader = True
# TODO - make this based on where mdig executable is
bottle.TEMPLATE_PATH = ['./mdig/views/', './mdig/' ]
# needed for error template to find bottle

@route('/models')
@route('/models/')
def redirect_index():
    redirect('/')

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


# dictionary of models that are being uploaded but have yet to have supporting
# files uploaded
# key: model_name, value:
# { dir: tempdir, "maps": [survival], "CODA": [filename], ...
# }
models_staging = {}

def validate_model_name(mname):
    # Get existing models in repository
    models = mdig.repository.get_models()
    if mname not in models.keys():
        raise ValueError()
    try:
        dm = DispersalModel(models[mname]) #,setup=False)
    except mdig.DispersalModel.ValidationError, e:
        return "Model %s is badly formed" % mname
    # Hack to get instances to initialise mapsets if they need to
    # and then save them
    dm.get_instances()
    dm.save_model()
    return dm 

def validate_instance(dm,instance_idx):
    if instance_idx < 0 or instance_idx >= len(dm.get_instances()):
        return False
    return True

def validate_replicate(instance, rep_num):
    if rep_num < 0 or rep_num >= len(instance.replicates):
        return False
    return True

@route('/models/',method="POST")
def submit_model():
    model_file = request.POST.get('new_model')
    data = model_file.file.read()
    # use ModelRepository to add model, but we'll need to implement a method
    # that accepts a string and uses a temp file as a proxy.
    model_name = ""
    try:
        model_name = add_model_to_staging(data)
    except Exception, e:
        if "Model exists" in str(e):
            # TODO provide a force parameter in query string which asks user
            # whether to overwrite model (or just to overwrite the model xml
            # file, and leave the uploaded maps)
            return "Model already exists in staging area"
    # check if model name exists in repository 
    return str(models_staging[model_name])

def process_tasks():
    """ go through all the tasks in models_in_queue and when they were
    completed.
    return those that have been completed since last time this method was
    called.
    """
    global last_notice
    new_last_notice = last_notice
    updates = {}
    time_index = {}
    to_remove = []
    for m_name, tasks in models_in_queue.items():
        for task_name in tasks:
            t = tasks[task_name]
            #if 'last_update' not in t:
            #    continue
            if 'complete' not in t:
                # deal with status of incomplete tasks
                if m_name not in updates: updates[m_name] = {}
                updates[m_name][task_name] = t
                time_index[(m_name,task_name)]=t['last_update']
            elif t['complete'] > last_notice:
                # deal with completion events which should only display once
                if m_name not in updates: updates[m_name] = {}
                updates[m_name][task_name] = t
                complete_time = t['complete']
                if new_last_notice < complete_time:
                    new_last_notice = complete_time
                time_index[(m_name,task_name)]=complete_time
            elif datetime.datetime.now() - t['last_update'] \
                    > datetime.timedelta(days=7):
                # remove tasks that are complete but older than a week
                to_remove.append((m_name,task_name))
    for m_name, task in to_remove:
        del models_in_queue[m_name][task]
        print "models in queue"
        print models_in_queue[m_name]
    last_notice = new_last_notice
    k = time_index.keys()
    k.sort(key=lambda x: time_index[x])
    print "update order:" + str(k)
    print "updates:" + str(updates)
    return k, updates

@route('/models/:model/run',method='POST')
@view('run.tpl')
@validate(model=validate_model_name)
def run_model(model):
    qsize = work_q.qsize()
    m_name = model.get_name()
    exists=False
    global models_in_queue
    rerun = False
    started = None
    if "rerun" in request.POST:
        if request.POST["rerun"].lower() == "true": rerun = True
    if not model.is_complete() or rerun:
        if m_name not in models_in_queue:
            models_in_queue[m_name] = {}
        else:
            print models_in_queue
        if 'RUN' in models_in_queue[m_name] and 'complete' not in models_in_queue[m_name]['RUN']:
            exists = True
        else:
            models_in_queue[m_name]['RUN'] = {"approx_q_pos":qsize,
                    "last_update":datetime.datetime.now()}
            work_q.put({'action':'RUN','model':model.get_name(),'parameters':{"rerun": rerun}})
        started = 'started' in models_in_queue[m_name]['RUN']
    task_order, task_updates = process_tasks()
    return dict(model=model, already_exists=exists, rerun = rerun,
            complete = model.is_complete() and not rerun,
            started = started,
            name=mdig.version_string,
            queue_size=qsize,
            task_order=task_order, task_updates = task_updates)

def add_model_to_staging(data):
    """ Create a temporary directory to store a model file and extract required
    files.
    """
    # make temp dir
    temp_model_dir = tempfile.mkdtemp(prefix="mdig_web")
    # write data to actual file
    model_fn = os.path.join(temp_model_dir, "model.xml") 
    f = open(model_fn,'w')
    f.write(data)
    f.close()
    # open temp dir to extract info like name and dependencies
    dm = DispersalModel(model_fn,setup=False)
    name = dm.get_name()
    if name in models_staging:
        shutil.rmtree(temp_model_dir)
        raise Exception("Model exists")
    models_staging[name] = {}
    models_staging[name]["dir"] = temp_model_dir
    maps = dm.get_map_dependencies()
    if len(maps) > 0:
        models_staging[name]["maps"] = maps
    transition_files = dm.get_popmod_files()
    #maps = dm.get_coda_files()
    if len(transition_files) > 0:
        models_staging[name]["ls_transition"] = transition_files
    return name

@route('/')
@view('index.tpl')
def index():
    # Get existing models in repository
    models = mdig.repository.get_models()
    ms=models.keys()[:]
    ms.sort()

    m_list = []
    for m in ms:
        try:
            dm = DispersalModel(models[m],setup=False)
            desc = dm.get_description()
            desc = re.sub("[\\s\\t]+"," ",desc)
            m_list.append((m,desc))
        except mdig.DispersalModel.ValidationError, e:
            print str(e)
            pass
    env = GRASSInterface.get_g().get_gis_env()
    task_order, task_updates = process_tasks()
    return dict(name=mdig.version_string, version=mdig.version,
            v_name=mdig.version_name, models=m_list,
            repo_location=mdig.repository.db,
            grass_env=env,
            task_order=task_order, task_updates = task_updates)

@route('/models/:model',method='GET')
@route('/models/:model',method='POST')
@view('model.tpl')
@validate(model=validate_model_name)
def show_model(model):
    dm=model
    if request.method=="POST":
        to_enable = [int(x) for x in request.POST.getall('enabled')]
        if len(to_enable) != 0:
            i_index=0
            for i in dm.get_instances():
                if i.enabled and i_index not in to_enable:
                    print "changing to false"
                    i.enabled=False
                    i.update_xml()
                if not i.enabled and i_index in to_enable:
                    print "changing to true"
                    i.enabled=True
                    i.update_xml()
                i_index+=1
            dm.save_model()
        else:
            print "unknown post"
        #event_to_remove = request.POST.getall('delEvent')]
        #elif if len(event_to_remove) > 0:
        #    ls.delEvent(
    active_instances=[]
    m = dm.get_name()
    if m in models_in_queue:
        if 'RUN' in models_in_queue[m]:
            if 'status' in models_in_queue[m]['RUN']:
                if 'active_instance' in models_in_queue[m]['RUN']['status']:
                    active_instances.append(models_in_queue[m]['RUN']['status']['active_instances'])
    task_order, task_updates = process_tasks()
    return dict(model=dm, name=mdig.version_string,
            repo_location=mdig.repository.db,
            task_order = task_order, task_updates= task_updates,
            active_instances=active_instances)

@route('/models/:model/instances/:instance',method='GET')
@route('/models/:model/instances/:instance',method='POST')
@view('instance.tpl')
@validate(instance=int, model=validate_model_name)
def show_instance(model,instance):
    dm=model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    envelope = None
    error = None
    m_name = dm.get_name()
    if request.method=="POST":
        # submit a job to generate map pack zip
        if 'map_pack' in request.POST:
            action = 'OCCUPANCY_MAP_PACK'
            ls_id=request.POST['map_pack']
            if m_name not in models_in_queue:
                models_in_queue[m_name] = {}
            if action in models_in_queue[m_name] and \
                    'complete' not in models_in_queue[m_name][action]:
                exists = True
            elif ls_id not in dm.get_lifestage_ids():
                # Invalid lifestage ID
                error="Invalid lifestage ID"
            else:
                qsize=work_q.qsize()
                models_in_queue[m_name][action] = {"approx_q_pos":qsize,
                        "last_update":datetime.datetime.now()}
                job_details = { "instance_idx": idx, "lifestage": ls_id }
                work_q.put({'action':action,'model':dm.get_name(),'parameters':job_details})
        # submit a job to generate the occupancy envelope
        elif 'envelope' in request.POST and dm.is_complete():
            ls_id=request.POST['envelope']
            if m_name not in models_in_queue:
                models_in_queue[m_name] = {}
            else:
                print models_in_queue
            if 'OCCUPANCY_GIF' in models_in_queue[m_name] and \
                    'complete' not in models_in_queue[m_name]['OCCUPANCY_GIF']:
                exists = True
            elif ls_id not in dm.get_lifestage_ids():
                # Invalid lifestage ID
                error="Invalid lifestage ID"
            else:
                qsize=work_q.qsize()
                models_in_queue[m_name]['OCCUPANCY_GIF'] = {"approx_q_pos":qsize,
                        "last_update":datetime.datetime.now()}
                job_details = { "instance_idx": idx, "lifestage": ls_id }
                work_q.put({'action':'OCCUPANCY_GIF','model':dm.get_name(),'parameters':job_details})
            #started = 'started' in models_in_queue[m_name]['OCCUPANCY_GIF']
        elif dm.is_complete():
            error = "Unknown POST request" + str(request.POST.keys())
        else:
            # if instance isn't complete, then we can't create an
            # occupancy envelope
            error="The model isn't complete, please run the model first"

    # Scan output dir to see if gifs have been generated for this instance
    envelopes_present=[]
    for ls_id in instance.experiment.get_lifestage_ids():
        # if there is an envelope generated then collect it
        if os.path.isfile(instance.get_occ_envelope_img_filenames(ls=ls_id,gif=True)):
            envelopes_present.append((ls_id, True))
        else:
            envelopes_present.append((ls_id, False))

    # Scan output dir to see if map_packs have been generated for this instance
    map_packs_present=[]
    for ls_id in instance.experiment.get_lifestage_ids():
        if os.path.isfile(instance.get_occ_envelope_img_filenames(ls=ls_id,extension=False,gif=True) + '.zip'):
            map_packs_present.append((ls_id, True))
        else: map_packs_present.append((ls_id, False))

    task_order, task_updates = process_tasks()
    #TODO update template to display error message
    return dict(idx=idx, instance=instance, name=mdig.version_string,
            envelopes_present = envelopes_present,
            map_packs_present = map_packs_present,
            repo_location=mdig.repository.db,
            task_order=task_order, task_updates = task_updates, error=error)

@route('/models/:model/instances/:instance/replicates/:replicate',method='GET')
@route('/models/:model/instances/:instance/replicates/:replicate',method='POST')
@view('replicate.tpl')
@validate(replicate=int, instance=int, model=validate_model_name)
def show_replicate(model,instance,replicate):
    dm=model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    rep_num = int(replicate)
    if not validate_replicate(instance, rep_num):
        abort(404, "No such replicate, or replicate doesn't exist yet")
    rep = instance.replicates[rep_num]
    error = None
    m_name = dm.get_name()
    if request.method=="POST":
        if 'map_pack' in request.POST:
            action = 'REPLICATE_MAP_PACK'
            ls_id=request.POST['map_pack']
            if m_name not in models_in_queue:
                models_in_queue[m_name] = {}
            if action in models_in_queue[m_name] and \
                    'complete' not in models_in_queue[m_name][action]:
                exists = True
            elif ls_id not in dm.get_lifestage_ids():
                # Invalid lifestage ID
                error="Invalid lifestage ID"
            else:
                qsize=work_q.qsize()
                models_in_queue[m_name][action] = {"approx_q_pos":qsize,
                        "last_update":datetime.datetime.now()}
                job_details = { "instance_idx": idx, "lifestage": ls_id,
                        "replicate": rep_num }
                work_q.put({'action':action,'model':dm.get_name(),'parameters':job_details})
        # submit a job to generate the occupancy gif 
        if 'gif' in request.POST and rep.complete:
            ls_id=request.POST['gif']
            if m_name not in models_in_queue:
                models_in_queue[m_name] = {}
            if 'REPLICATE_GIF' in models_in_queue[m_name] and \
                    'complete' not in models_in_queue[m_name]['REPLICATE_GIF']:
                exists = True
            elif ls_id not in dm.get_lifestage_ids():
                # Invalid lifestage ID
                error="Invalid lifestage ID"
            else:
                qsize=work_q.qsize()
                models_in_queue[m_name]['REPLICATE_GIF'] = {"approx_q_pos":qsize,
                        "last_update":datetime.datetime.now()}
                job_details = { "instance_idx": idx, "lifestage": ls_id,
                        "replicate": rep_num }
                work_q.put({'action':'REPLICATE_GIF','model':dm.get_name(),'parameters':job_details})
        elif rep.complete:
            error = "Unknown POST request"
        else:
            # if instance isn't complete, then we can't create an
            # occupancy gif
            error="The replicate isn't complete, please run the instance first"

    # Scan output dir to see if gifs have been generated for this replicate
    gifs_present=[]
    for ls_id in instance.experiment.get_lifestage_ids():
        if os.path.isfile(rep.get_img_filenames(ls=ls_id,gif=True)):
            gifs_present.append((ls_id, True))
        else: gifs_present.append((ls_id, False))

    # Scan output dir to see if map_packs have been generated for this replicate
    map_packs_present=[]
    for ls_id in instance.experiment.get_lifestage_ids():
        if os.path.isfile(rep.get_img_filenames(ls=ls_id,extension=False,gif=True) + '.zip'):
            map_packs_present.append((ls_id, True))
        else: map_packs_present.append((ls_id, False))

    task_order, task_updates = process_tasks()
    #TODO update template to display error message
    return dict(idx=idx, instance=instance, replicate=rep, name=mdig.version_string,
            gifs_present = gifs_present, repo_location=mdig.repository.db,
            map_packs_present = map_packs_present,
            task_order=task_order, task_updates = task_updates, error=error)

from bottle import send_file
from mdig import OutputFormats

@route('/models/:model/instances/:instance/:ls_id/envelope.gif')
@validate(instance=int, model=validate_model_name)
def instance_occ_envelope_gif(model, instance, ls_id):
    dm=model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    # do per lifestage!
    fn = instance.get_occ_envelope_img_filenames(ls=ls_id, gif=True)
    root_dir = os.path.dirname(fn)
    send_file(os.path.basename(fn),root=root_dir)

@route('/models/:model/instances/:instance/:ls_id/map_pack.zip')
@validate(instance=int, model=validate_model_name)
def instance_occ_envelope_gif(model, instance, ls_id):
    dm=model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    # do per lifestage!
    fn = instance.get_occ_envelope_img_filenames(ls=ls_id, extension=False, gif=True)
    fn += '.zip'
    root_dir = os.path.dirname(fn)
    send_file(os.path.basename(fn),root=root_dir)

@route('/models/:model/instances/:instance/replicates/:replicate/:ls_id/spread.gif')
@validate(replicate=int, instance=int, model=validate_model_name)
def replicate_spread_gif(model, instance, replicate, ls_id):
    dm=model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    replicate = int(replicate)
    if not validate_replicate(instance, replicate):
        abort(404, "No such replicate, or replicate doesn't exist yet")
    r = instance.replicates[replicate]
    # do per lifestage!
    fn = r.get_img_filenames(ls=ls_id, gif=True)
    root_dir = os.path.dirname(fn)
    send_file(os.path.basename(fn),root=root_dir)

@route('/models/:model/instances/:instance/replicates/:replicate/:ls_id/map_pack.zip')
@validate(replicate=int, instance=int, model=validate_model_name)
def replicate_spread_gif(model, instance, replicate, ls_id):
    dm=model
    idx = int(instance)
    if not validate_instance(dm, idx):
        abort(404, "No such instance")
    instance = dm.get_instances()[idx]
    replicate = int(replicate)
    if not validate_replicate(instance, replicate):
        abort(404, "No such replicate, or replicate doesn't exist yet")
    r = instance.replicates[replicate]
    # do per lifestage!
    fn = r.get_img_filenames(ls=ls_id, extension=False, gif=True)
    fn += '.zip'
    root_dir = os.path.dirname(fn)
    send_file(os.path.basename(fn),root=root_dir)

class Worker_InstanceListener():

    def __init__(self, results_q):
        self.results_q = results_q
        
    def replicate_complete(self,rep):
        instance = rep.instance
        model = instance.experiment
        percent = len([x for x in instance.replicates if x.complete])/float(model.get_num_replicates())
        percent = percent * 100.0
        msg = {'action': 'RUN', 'model':model.get_name(), 'status': {
                    "active_instance": model.get_instances().index(instance),
                    "percent_done":percent} }
        self.results_q.put(msg)

    def occupancy_envelope_complete(self,instance,ls,t):
        model = instance.experiment
        start, end = model.get_period()
        percent = float(int(t) - start) / (end - start)
        msg = {'action': 'OCCUPANCY_GIF', 'model':model.get_name(), 'status': {
                    "active_instance": model.get_instances().index(instance),
                    "percent_done":percent} }
        self.results_q.put(msg)

    def export_image_complete(self,instance,replicate,ls,t):
        if replicate:
            instance=replicate.instance
        model = instance.experiment
        start, end = model.get_period()
        # bad bad t is a string, this should be fixed
        percent = float(int(t) - start) / (end - start)
        if replicate:
            msg = {'action': 'REPLICATE_GIF', 'model':model.get_name(),
                    'status': {
                        "active_instance": model.get_instances().index(instance),
                        "active_replicate": instance.replicates.index(replicate),
                        "percent_done":percent} }
        else:
            msg = {'action': 'OCCUPANCY_GIF', 'model':model.get_name(),
                    'status': {
                        "active_instance": model.get_instances().index(instance),
                        "percent_done":percent} }
        self.results_q.put(msg)

    def export_map_pack_complete(self,instance,replicate,ls,t):
        if replicate:
            instance=replicate.instance
        model = instance.experiment
        start, end = model.get_period()
        # bad bad t is a string, this should be fixed
        percent = float(int(t) - start) / (end - start)
        if replicate:
            msg = {'action': 'REPLICATE_MAP_PACK', 'model':model.get_name(),
                    'status': {
                        "active_instance": model.get_instances().index(instance),
                        "active_replicate": instance.replicates.index(replicate),
                        "percent_done":percent} }
        else:
            msg = {'action': 'OCCUPANCY_MAP_PACK', 'model':model.get_name(),
                    'status': {
                        "active_instance": model.get_instances().index(instance),
                        "percent_done":percent} }
        self.results_q.put(msg)


class MDiGWorker():

    def __init__(self, work_q, results_q):
        self.work_q = work_q
        self.results_q = results_q
        self.running = True
        self.log = logging.getLogger('mdig.worker')
        self.listener = Worker_InstanceListener(self.results_q)

    def run_model(self, m_name, rerun=False):
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        if rerun:
            dm.reset_instances()
        for instance in dm.get_instances():
            instance.listeners.append(self.listener)
        msg = {'model': m_name,'action': "RUN",
                'status':{ 'started': datetime.datetime.now() } }
        self.results_q.put(msg)
        dm.run()
        msg = {'model': m_name,'action': "RUN",
                'status':{ 'complete': datetime.datetime.now() } }
        self.results_q.put(msg)

    def create_occupancy_gif(self, m_name, instance_idx=None, ls=None):
        action = "OCCUPANCY_GIF"
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        instance = dm.get_instances()[instance_idx]
        # Tell web interface we've started
        msg = {'model': m_name,'action': action,
                'status':{ 'started': datetime.datetime.now() } }
        self.results_q.put(msg)
        self.log.debug("Checking/creating envelopes")
        # Tell web interface what we're doing
        msg = {'model': m_name,'action': action,
                'status':{ 'active_instance': instance_idx, 'description':"Creating occupancy envelopes"} }
        self.results_q.put(msg)
        # Add listener so that we have progress updates
        instance.listeners.append(self.listener)
        # Now actually create the envelopes if necessary
        instance.update_occupancy_envelope(ls_list=[ls])
        # also convert occupancy envelopes into images
        # via ExportAction
        from Actions import ExportAction
        ea=ExportAction()
        ea.parse_options([])
        ea.options.output_gif = True
        ea.options.output_image = True
        ea.options.output_lifestage = ls
        ea.listeners.append(self.listener)
        self.log.debug("Generating images")
        msg = {'model': m_name,'action': action,
                'status':{ 'active_instance': instance_idx,
                    'description':"Generating images"} }
        self.results_q.put(msg)
        try: ea.do_instance_images(instance)
        except: raise
        msg = {'model': m_name,'action': action, 'status':{
            'complete':datetime.datetime.now() } }
        self.results_q.put(msg)

    def create_occupancy_map_pack(self, m_name, instance_idx=None, ls=None):
        action = "OCCUPANCY_MAP_PACK"
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        instance = dm.get_instances()[instance_idx]
        # Tell web interface we've started
        msg = {'model': m_name,'action': action,
                'status':{ 'started': datetime.datetime.now() } }
        self.results_q.put(msg)
        self.log.debug("Checking/creating envelopes")
        # Tell web interface what we're doing
        msg = {'model': m_name,'action': action,
                'status':{ 'active_instance': instance_idx, 'description':"Creating occupancy envelopes"} }
        self.results_q.put(msg)
        # Add listener so that we have progress updates
        instance.listeners.append(self.listener)
        # Now actually create the envelopes if necessary
        instance.update_occupancy_envelope(ls_list=[ls])
        # also convert occupancy envelopes into images
        # via ExportAction
        from Actions import ExportAction
        ea=ExportAction()
        ea.parse_options([])
        ea.options.output_map_pack = True
        ea.options.output_lifestage = ls
        ea.listeners.append(self.listener)
        self.log.debug("Exporting maps")
        msg = {'model': m_name,'action': action,
                'status':{ 'active_instance': instance_idx,
                    'description':"Exporting maps"} }
        self.results_q.put(msg)
        try: ea.do_instance_map_pack(instance)
        except: raise
        msg = {'model': m_name,'action': action, 'status':{
            'complete':datetime.datetime.now() } }
        self.results_q.put(msg)

    def create_replicate_gif(self, m_name, instance_idx, replicate, ls):
        action = "REPLICATE_GIF"
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        instance = dm.get_instances()[instance_idx]
        # Tell web interface we've started
        msg = {'model': m_name,'action': action,
                'status':{ 'started': datetime.datetime.now(),
                'active_instance': instance_idx,
                'description':"Generating images",
                'active_replicate': replicate} }
        self.results_q.put(msg)
        # Add listener so that we have progress updates
        instance.listeners.append(self.listener)
        # also convert replicate maps into images
        # via ExportAction
        from Actions import ExportAction
        ea=ExportAction()
        ea.parse_options([])
        ea.options.output_gif = True
        ea.options.output_image = True
        ea.options.output_lifestage = ls
        ea.options.reps = [ replicate ]
        try: ea.do_instance_images(instance)
        except: raise
        msg = {'model': m_name,'action': action,
                'status':{ 'started': datetime.datetime.now(),
                'active_instance': instance_idx,
                'description':"Generating images",
                'active_replicate': replicate,
                'complete':datetime.datetime.now() } }
        self.results_q.put(msg)

    def run(self):
        # NOTE: To add a pdb statement to this process you need to use:
        #import pdb;
        #pdb.Pdb(stdin=open('/dev/stdin', 'r+'), stdout=open('/dev/stdout', 'r+')).set_trace()
        while self.running:
            s = None
            try:
                s = self.work_q.get(timeout=1)
                action = s['action'] # the action to perform
                if 'model' in s: m_name = s['model'] # the model it applies to
                if action == "SHUTDOWN":
                    self.running = False
                elif action == "RUN":
                    rerun = s['parameters']['rerun']
                    self.run_model(m_name, rerun=rerun)
                elif action == "OCCUPANCY_GIF":
                    # format of s[2]:
                    # { "instance_idx": idx, "lifestage": ls_id }
                    ls_id = s['parameters']['lifestage']
                    instance_idx = s['parameters']['instance_idx']
                    self.create_occupancy_gif(m_name,instance_idx,ls_id)
                elif action == "REPLICATE_GIF":
                    ls_id = s['parameters']['lifestage']
                    instance_idx = s['parameters']['instance_idx']
                    rep = s['parameters']['replicate']
                    self.create_replicate_gif(m_name,instance_idx,rep,ls_id)
                elif action == "OCCUPANCY_MAP_PACK":
                    ls_id = s['parameters']['lifestage']
                    instance_idx = s['parameters']['instance_idx']
                    self.create_occupancy_map_pack(m_name,instance_idx,ls_id)
                elif action == "REPLICATE_MAP_PACK":
                    ls_id = s['parameters']['lifestage']
                    instance_idx = s['parameters']['instance_idx']
                    rep = s['parameters']['replicate']
                    self.create_replicate_map_pack(m_name,instance_idx,rep,ls_id)
                else:
                    self.log.error("Unknown task: %s" % str(s))
                self.work_q.task_done()
            except q.Empty:
                pass
            except Exception, e:
                import traceback
                self.log.error("Unexpected exception in worker process: %s" % str(e))
                traceback.print_exc()
                # Send error notice back to web interface
                s = s.copy()
                if 'status' not in s: s['status'] = {}
                s['status']['error'] = str(e)
                self.results_q.put(s)

def mdig_worker_start(work_q,results_q):
    # Have to replace some of the environment variables, otherwise they get
    # remembered and will confuse original Web server process
    g = GRASSInterface.get_g()
    g.init_pid_specific_files()
    g.grass_vars["MAPSET"] = "PERMANENT"
    g.set_gis_env()

    worker = MDiGWorker(work_q,results_q)
    worker.run()

class ResultMonitor(Thread):
    def __init__ (self, result_q):
        Thread.__init__(self)
        self.result_q = result_q
        self.running = False

    def run(self):
        self.running = True
        global models_in_queue
        while self.running:
            try:
                s = self.result_q.get(timeout=1)
                print "resultmonitor received" + str(s)
                print "before: " + str(models_in_queue)
                m_action = s['action']
                if 'model' in s:
                    m_name = s['model']
                    models_in_queue[m_name][m_action].update(s['status'])
                    models_in_queue[m_name][m_action]['last_update'] = datetime.datetime.now()
                    print models_in_queue
            except q.Empty:
                pass
            except Exception, e:
                import traceback
                self.log.error("Unexpected exception in result monitor process: %s" % str(e))
                traceback.print_exc()

        
# This thread monitors the results_q and updates the local process status (since
# there is no easy other way except processing the queues on HTTP requests, and
# this would potentially lead to slow responsiveness).
rt = ResultMonitor(results_q)
# spawn a thread with mdig.py and use a multiprocessing queue
mdig_worker_process = Process(target=mdig_worker_start, args=(work_q,results_q))

def start_web_service():
    change_to_web_mapset()
    rt.start()
    mdig_worker_process.start()

    # setup and run webapp
    global app; app = bottle.app()
    app.catchall = False
    import paste.evalexception
    myapp = paste.evalexception.middleware.EvalException(app)
    c = MDiGConfig.get_config()
    bottle.run(app=myapp, host=c["WEB"]["host"], port=c["WEB"]["port"], reloader=reloader)

# Store the web mapsets that have been created so that we can tidy up afterwards
mapsets = {} # indexed by location
def change_to_web_mapset():
    g = GRASSInterface.get_g(create=False)
    ms = "mdig_webservice"
    if not g.check_mapset(ms):
        g.change_mapset(ms, create=True)
        mapsets[g.grass_vars["LOCATION_NAME"]] = ms
    else: g.change_mapset(ms)

def shutdown_webapp():
    if app is None: return
    rt.running = False
    work_q.put({'action':"SHUTDOWN"})
    if mdig_worker_process.pid: mdig_worker_process.join()
    print "TODO: delete temporary webservice files"

