from bottle import route, validate, run, request, redirect
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
        pdb.set_trace()
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
                del models_in_queue[m_name][task_name]
    last_notice = new_last_notice
    k = time_index.keys()
    k.sort(key=lambda x: time_index[x])
    print "updates:" + str(k)
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
            work_q.put(['RUN',model.get_name(),{"rerun": rerun}])
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
            if 'active' in models_in_queue[m]['RUN']:
                active_instances = models_in_queue[m]['RUN']['active']
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
    instance = dm.get_instances()[idx]
    envelope = None
    error = None
    m_name = dm.get_name()
    if request.method=="POST":
        if "envelope" not in request.POST:
            # we only know about post request to create an envelope at the
            # moment
            print "poo"
            pass
        # submit a job to generate the occupancy envelope
        elif dm.is_complete():
            if m_name not in models_in_queue:
                models_in_queue[m_name] = {}
            else:
                print models_in_queue
            if 'OCCUPANCY' in models_in_queue[m_name] and \
                    'complete' not in models_in_queue[m_name]['OCCUPANCY']:
                exists = True
            else:
                qsize=work_q.qsize()
                models_in_queue[m_name]['OCCUPANCY'] = {"approx_q_pos":qsize,
                        "last_update":datetime.datetime.now()}
                work_q.put(['OCCUPANCY',dm.get_name(),idx])
            #started = 'started' in models_in_queue[m_name]['OCCUPANCY']
        else:
            # if instance isn't complete, then we can't create an
            # occupancy envelope
            error="The model isn't complete, please run the model first"
    else:
        # if there is an envelope generated then display it
        pass

    envelopes_present=[]
    for ls_id in instance.experiment.get_lifestage_ids():
        if os.path.isfile(instance.get_occ_envelope_img_filenames(ls=ls_id,gif=True)):
            envelopes_present.append((ls_id, True))
        else:
            envelopes_present.append((ls_id, False))
    task_order, task_updates = process_tasks()
    return dict(idx=idx, instance=instance, name=mdig.version_string,
            envelopes_present = envelopes_present, repo_location=mdig.repository.db,
            task_order=task_order, task_updates = task_updates, error=error)

from bottle import send_file
from mdig import OutputFormats

@route('/models/:model/instances/:instance/:ls_id/envelope.gif')
@validate(instance=int, model=validate_model_name)
def occ_envelope(model, instance, ls_id):
    dm=model
    idx = int(instance)
    instance = dm.get_instances()[idx]
    # do per lifestage!
    fn = instance.get_occ_envelope_img_filenames(ls=ls_id, gif=True)
    print fn
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
        msg = ['RUN',model.get_name(), {
                    "active": model.get_instances().index(instance),
                    "percent_complete":percent} ]
        self.results_q.put(msg)

class MDiGWorker():

    def __init__(self, work_q, results_q):
        self.work_q = work_q
        self.results_q = results_q
        self.running = True
        self.log = logging.getLogger('mdig.worker')

    def run_model(self, m_name, rerun=False):
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        if rerun:
            dm.reset_instances()
        for instance in dm.get_instances():
            instance.listeners.append(Worker_InstanceListener(self.results_q))
        msg = [action,m_name,{"started": True}]
        self.results_q.put(msg)
        dm.run()
        msg = [action,m_name,{"complete": True}]
        self.results_q.put(msg)

    def create_occupancy(self, m_name, instance=None, ls=None):
        # TODO generate maps/envelopes/images for all lifestages
        action = action
        m_name = s[1]
        model_file = mdig.repository.get_models()[m_name]
        dm = DispersalModel(model_file)
        instance = dm.get_instances()[s[2]]
        s = [action,m_name,{"started": True}]
        self.results_q.put(s)
        self.log.debug("Checking/creating envelopes")
        s = [action,m_name,{"status": "Creating occupancy envelopes"}]
        self.results_q.put(s)
        #instance.update_occupancy_envelope()
        s = [action,m_name,{"percent_complete": 50}]
        self.results_q.put(s)
        # also convert occupancy envelopes into images
        # setup ExportAction
        from Actions import ExportAction
        ea=ExportAction()
        ea.parse_options([])
        ea.options.output_gif = True
        self.log.debug("Generating images")
        s = [action,m_name,{"status": "Generating images"}]
        self.results_q.put(s)
        ea.do_instance(instance)
        s = [action,m_name,{"complete": True}]
        self.results_q.put(s)

    def run(self):
        # NOTE: To add a pdb statement to this process you need to use:
        #import pdb;
        #pdb.Pdb(stdin=open('/dev/stdin', 'r+'), stdout=open('/dev/stdout', 'r+')).set_trace()
        while self.running:
            s = None
            try:
                s = self.work_q.get(timeout=1)
                action = s[0] # the action to perform
                m_name = s[1] # the model it applies to
                if action == "SHUTDOWN":
                    running = False
                elif action == "RUN":
                    rerun = s[2]["rerun"]
                    self.run(m_name, rerun=rerun)
                elif action == "OCCUPANCY":
                    instance_idx = s[2]["instance"]
                    ls_id = None
                    if "ls" in s[2]: ls_id = s[2]["ls"]
                    self.create_occupancy(m_name,instance_idx,ls_id)
                else:
                    self.log.error("Unknown task: %s" % str(s))
                self.work_q.task_done()
            except q.Empty:
                pass
            except Exception, e:
                import traceback
                log.error("Unexpected exception in worker process: %s" % str(e))
                traceback.print_exc()
                # Send error notice back to web interface
                s = [s[0],s[1],{"error": str(e)}]
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
                m_action = s[0]
                m_name = s[1]
                m_status = s[2]
                if "started" in m_status:
                    models_in_queue[m_name][m_action]["started"] = datetime.datetime.now()
                    models_in_queue[m_name][m_action]["active"] = []
                elif "complete" in m_status:
                    models_in_queue[m_name][m_action]["complete"] = datetime.datetime.now()
                    models_in_queue[m_name][m_action]["active"] = []
                elif "active" in m_status:
                    models_in_queue[m_name][m_action]["active"] = [m_status["active"]]
                    models_in_queue[m_name][m_action]["percent_complete"] = m_status["percent_complete"]
                elif "error" in m_status:
                    models_in_queue[m_name][m_action]["active"] = []
                    models_in_queue[m_name][m_action].update(m_status)
                elif "status" in m_status:
                    models_in_queue[m_name][m_action].update(m_status)
                else:
                    print "Unknown status update received from worker process:" \
                        + str(m_status)
                models_in_queue[m_name][m_action]['last_update'] = datetime.datetime.now()
                print models_in_queue
            except q.Empty:
                pass
        
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
    run(app=myapp, host=c["WEB"]["host"], port=c["WEB"]["port"], reloader=reloader)

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
    work_q.put(["SHUTDOWN","now please"])
    mdig_worker_process.join()
    print "TODO: delete temporary webservice files"

