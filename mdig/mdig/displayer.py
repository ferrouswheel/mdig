#!/usr/bin/env python2.4
#
#  Copyright (C) 2008 Joel Pitt, Fruition Technology
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
from mdig import grass
from mdig import config

class Displayer:
    """ Displayer class

    Displays the latest maps for each lifestage in a Grass display window.
    """
    
    def __init__(self):
        self.listeningTo = []
        
    def replicate_update(self, rep, t):
        g = grass.get_g()
        
        g.set_output()
        g.clear_monitor()
        
        bm=config.get_config()['OUTPUT']['background_map']
        if bm is not None:
            try:
                g.paint_map(bm)
            except grass.GRASSCommandException:
                pass
        
        layer_index = 0
        for l in rep.temp_map_names:
            g.paint_map(rep.temp_map_names[l][0], layer=layer_index)
            layer_index += 1
        g.close_output()
