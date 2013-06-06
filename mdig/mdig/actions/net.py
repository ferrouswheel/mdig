import sys

from optparse import OptionParser

import mdig
from mdig.actions.base import Action


class WebAction(Action):
    description = "Run a webserver that allows interaction with MDiG"

    def __init__(self):
        super(WebAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description = self.description,
                usage = "%prog web [options] <model_name>")
        self.preload = False
        self.add_options()
        
    def add_options(self):
        Action.add_options(self)

    def do_me(self,mdig_model):
        # initialise web system - needs to create new mapset
        from webui import start_web_service
        # start web monitoring loop
        start_web_service()
    
class ClientAction(Action):
    description = "Runs MDiG as a node in a distributed instance of MDiG"

    def __init__(self):
        super(ClientAction, self).__init__()

    def get_usage(self):
        usage_str = mdig.version_string
    
        usage_str += '''
        "client" action : Runs MDiG as a node in a distributed instance of MDiG
        
        NOT IMPLEMENTED
        '''
        return usage_str
            
    def parse_options(self, argv):
        print self.get_usage()
        sys.exit(mdig.mdig_exit_codes["not_implemented"])


