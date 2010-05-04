from bottle import route, validate, run, request
from bottle import view
import bottle
import sys
import re

import pdb

import mdig
from mdig.DispersalModel import DispersalModel

reloader = False
if True:
    bottle.debug(True)
    sys.path.insert(0, './mdig/')
    reloader = True
# TODO - make this based on where mdig executable is
bottle.TEMPLATE_PATH = ['./mdig/views/', './mdig/' ]
# needed for error template to find bottle

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
            print m
            dm = DispersalModel(models[m],setup=False)
            desc = dm.get_description()
            desc = re.sub("[\\s\\t]+"," ",desc)
            m_list.append((m,desc))
        except mdig.DispersalModel.ValidationError, e:
            print str(e)
            pass
    return dict(name=mdig.version_string, models=m_list,
            repo_location=mdig.repository.location)

def validate_model_name(mname):
    # Get existing models in repository
    models = mdig.repository.get_models()
    if mname not in models.keys():
        raise ValueError()
    try:
        dm = DispersalModel(models[mname],setup=False)
    except mdig.DispersalModel.ValidationError, e:
        return "Model %s is badly formed" % mname
    return dm 

@route('/models/:model',method='GET')
@route('/models/:model',method='POST')
@view('model.tpl')
@validate(model=validate_model_name)
def show_model(model):
    dm=model
    if request.method=="POST":
        to_enable = [int(x) for x in request.POST.getall('enabled')]
        print to_enable
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

    return dict(model=dm, name=mdig.version_string,
            repo_location=mdig.repository.location)

@route('/models/:model/instances/:instance',method='GET')
@route('/models/:model/instances/:instance',method='POST')
@view('instance.tpl')
@validate(instance=int, model=validate_model_name)
def show_instance(model,instance):
    dm=model
    idx = int(instance)
    instance = dm.get_instances()[idx]
    if request.method=="POST":
        #to_enable = [int(x) for x in request.POST.getall('enabled')]
        pass

    return dict(idx=idx, instance=instance, name=mdig.version_string,
            repo_location=mdig.repository.location)

def start_web_service():
    run(host='192.168.1.100', port=1444, reloader=reloader)
