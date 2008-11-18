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
""" Displayer class

Displays the latest maps for each lifestage in a Grass display window.

Copyright 2006, Joel Pitt

"""

from mdig import GRASSInterface

class Displayer:
	
	def __init__(self):
		self.listeningTo = []
		
	def replicateUpdate(self,rep,t):
		g = GRASSInterface.getG()
		
		g.setOutput()
		g.clearMonitor()
		
		bm=rep.instance.experiment.getRegion(rep.instance.r_id).getBackgroundMap()
		if bm is not None:		
			g.paintMap(bm.getMapFilename())
		
		for l in rep.temp_map_names.keys():
			g.paintMap(rep.temp_map_names[l][0])
		g.closeOutput()
