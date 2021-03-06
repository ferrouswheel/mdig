#
#  Copyright (C) 2006,2008 Joel Pitt, Fruition Technology
#
#  This file is part of Modular Dispersal In GIS.
#
#  Modular Dispersal In GIS is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your
#  option) any later version.
#
#  Modular Dispersal In GIS is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
#  Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with Modular Dispersal In GIS.  If not, see <http://www.gnu.org/licenses/>.
#
import logging

import mdig.grass as grass

from mdig.instance import DispersalInstance
from mdig.replicate import Replicate


def create_filename(rep):
    if isinstance(rep, Replicate):
        fn = rep.get_map_name_base()
    elif isinstance(rep, DispersalInstance):
        i = rep
        fn = i.get_map_name_base()
    else:
        logging.getLogger('mdig').error("Unknown object to create filename for.")
        fn = None
    return fn
        

class BaseOutput(object):

    def replicate_update(self, rep, t):
        return NotImplemented

    def create_filename(self, rep):
        return create_filename(rep)


class PngOutput(BaseOutput):

    def __init__(self, node):
        self.interval = 1
        self.show_year = False
        self.show_grid = False
        self.log = logging.getLogger("mdig.pngOutput")
        
        self.log.debug("Initialised pngOutput")
        
        for child in node:
            if child.tag == "interval":
                self.interval = int(child.text)
            elif child.tag == "showTime":
                if child.text.lower() == "true":
                    self.show_year = True
            elif child.tag == "showGrid":
                if child.text.lower() == "true":
                    self.show_year = True
        
        self.listeningTo = []
        
    def replicate_update(self, rep, t):
        g = grass.get_g()
        
        fn = None
        
        if rep.instance.experiment.interval_modulus(self.interval, t) == 0:
            fn = self.create_filename(rep)
            fn += "_" + repr(t) + ".png"
            self.log.debug("Writing PNG %s" % fn)
            
            g.set_output(fn, display=None)
            g.clear_monitor()
            
            current_region = rep.instance.experiment.get_region(rep.instance.r_id)
            
            if current_region.getBackgroundMap():
                g.paint_map(current_region.getBackgroundMap().get_map_filename())
            
            for l in rep.temp_map_names.keys():
                g.paint_map(rep.temp_map_names[l][0])
            
            if self.show_grid:
                g.paint_grid(5)
            if self.show_year:
                g.paint_year(t)
                
            self.last_output = t
            g.close_output()
            
        return [None, fn]
        

class RasterOutput(BaseOutput):
    _tag="RasterOutput"
    
    def __init__(self, node):
        self.interval = 1
        self.lifestage = None
        self.log = logging.getLogger("mdig.RasterOutput")
        
        for child in node:
            if child.tag == "interval":
                self.interval = int(child.text)
            elif child.tag == "lifestage":
                self.lifestage = child.text
        
        self.listeningTo = []
        
    def replicate_update(self, rep, t):
        g = grass.get_g()
        fn = None

        if rep.instance.experiment.interval_modulus(self.interval, t) == 0:
            for l in rep.temp_map_names.keys():
                if self.lifestage == l:
                    fn = self.create_filename(rep)
                    fn += "_ls_" + l + "_" + repr(t)
                    self.log.debug("Writing raster %s" % fn)
                    g.copy_map(rep.temp_map_names[l][0], fn, True)
            self.last_output = t
            
        return [self.lifestage, fn]
