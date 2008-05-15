#!/usr/bin/env python2.4
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
