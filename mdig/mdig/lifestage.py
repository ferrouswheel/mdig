#!/usr/bin/env python2.4
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
""" 
Lifestage module. Part of MDiG - Modular Dispersal in GIS
Copyright 2006, Joel Pitt
"""

import logging
import pdb

from grassmap import GrassMap
from analysis import Analysis
from event import Event
import grass

class Lifestage:
    
    def __init__(self, node):
        # Get the logger object
        self.log = logging.getLogger("mdig.lifestage")
        # Set the XML node if one exists
        self.xml_node = node
        
        self.initial_maps={} # Initial maps keyed by region
        self.events=[] # List of events
        self.analysis_list=[] # List of analyses to perform
        
        self.bins = None
        self.bin_masks = {}
        self.p_map_names = {}
        self.phenology_delay = 0

        self.name = None # Name/id of the lifestage
        self.populationBased = False # Population based or presence/absence?

        # Load details from XML if lifestage is associated with an XML node
        if self.xml_node is not None:
            self._loadLifestage() 
    
    def _loadLifestage(self):
        """
        Loads details from XML into class
        """

        # Load name
        if "name" in self.xml_node.attrib.keys():
            self.name = self.xml_node.attrib["name"]
            self.log = logging.getLogger("mdig.lifestage."+self.name)
        else:
            raise Exception("Can't find name of lifestage")

        # Load whether population based or not
        if "populationBased" in self.xml_node.attrib.keys():
            if self.xml_node.attrib["populationBased"].upper().find("TRUE") != -1:
                self.populationBased = True 

        # Load and construct event objects
        event_nodes = self.xml_node.xpath("event")
        for e_node in event_nodes:
            e=Event(e_node)
            self.events.append(e)

        # Load the initial distribution maps
        init_map_nodes=self.xml_node.xpath('initialDistribution')
        for i_node in init_map_nodes:
            r_id=i_node.attrib["region"]
            # This should never happen:
            #if r_id not in self.initial_maps.keys():
            self.initial_maps[r_id]=GrassMap(i_node[0])
        
        # Init phenology bins
        self.initPhenologyBins()

    def initPhenologyBins(self):
        """
        Initialise the bins with their range and mean values.

        Bins are dictionaries, with the bin range as a tuple key and
        the value is the mean value within that bin (which may not be directly
        in the middle depending on the frequency distribution of values
        for that bin.
        """ 
        self.bins = {}
        n_bins=10
        p_nodes=self.xml_node.xpath('phenology')
        for nodes in p_nodes:
            if "region" in nodes.attrib.keys():
                # If there is a region specified for the phenology settings
                self.bins[nodes.attrib["region"]] = {}
                current_bins = self.bins[nodes.attrib["region"]]
            else:
                # otherwise the setting is for all regions
                if "__default" in self.bins.keys():
                    self.log.error("Default region phenology map already defined")
                    current_bins = None
                    break
                else:
                    self.bins["__default"] = {}
                    current_bins = self.bins["__default"]
            
            for n in nodes:
                if n.tag == "delay":
                    # Unsure what delay does, it might be the delay before
                    # new individuals can be processed by the next lifestage
                    self.phenology_delay = int(n.text.strip())
                elif n.tag == "value":
                    # If phenology is simply a value then it occurs at the same
                    # time everywhere
                    interval = int(n.text)
                    current_bins[(interval,interval)] = interval
                elif n.tag == "map":
                    # If it's a map we have to process it to work out the bin
                    # ranges and their means
                    p_mapname=n.text.strip()
                    
                    self.p_map_names[region_id] = GrassMap(p_mapname)
                
                    sums=[0]*n_bins
                    bin_counts=[0]*n_bins
                    freqs=grass.get_g().raster_value_freq(p_mapname)
                    
                    min_cell=int(freqs[0][0])
                    max_cell=int(freqs[-1][0])
                    bin_size=float((max_cell-(min_cell-1)))/n_bins
                    
                    i=1
                    for value,freq in freqs:
                        value=int(value)
                        freq=int(freq)
                        # if we have gone beyond the range of the current bin
                        while value > (min_cell-1+(bin_size * i)):
                            i+=1
                        # add value freq times to the sum
                        sums[i-1]+=(freq * value)
                        bin_counts[i-1]+=freq
                        
                    for i in range(1,n_bins+1):
                        bin_range = (min_cell+((i-1)*bin_size),min_cell-1+((i)*bin_size))
                        if bin_counts[i-1] != 0:
                            current_bins[bin_range]=float(sums[i-1]/bin_counts[i-1])
                        else:
                            current_bins[bin_range]=None
        # end for nodes in p_nodes
        self.log.debug("Phenology bins are: %s" % (repr(self.bins)))
        
    def getPhenologyBins(self,region_id):
        if region_id in self.bins.keys():
            return self.bins[region_id]
        elif "__default" in self.bins.keys():
            return self.bins["__default"]
        
        self.log.error("No phenology intervals found for region %s" % region_id)
        return None 

    def getPhenologyIntervals(self, region_id):
        bins = self.getPhenologyBins(region_id)
        if bins is not None:
            return bins.values()
        else:
            return None
        
    def getPhenologyMask(self,interval,r_id):
        """
        Get the phenology masks for "interval" and region "r_id". Generates as needed.
        """
        if r_id not in self.bin_masks.keys():
            self.bin_masks[r_id]={}
            
        if interval not in self.bin_masks[r_id].keys():
            self.bin_masks[r_id][interval] = self._generateMask(interval,r_id)
        
        return self.bin_masks[r_id][interval]
        
    def _generateMask(self,interval,r_id):
        """
        Actually generates a mask for a given interval and region (r_id)
        """
        # Get GRASS interface instance
        g = grass.get_g()
        # Generate a random map name
        mapname = g.generate_map_name("mask")
                
        if r_id in self.bins.keys():
            bins = self.bins[r_id]
        elif "__default" in self.bin.keys():
            bins = self.bins["__default"]
        else:
            self.log.error("Could not find any phenology bins for generating mask")
        
        # Find what bin the interval lies within
        for d_range, mean in bins.items():
            if interval >= d_range[0] and interval <= d_range[1]:
                g.mapcalc(mapname,"if(%s>=%f,if(%s<=%f,1,0),0)" % (self.p_map_names[r_id], d_range[0], self.p_map_names[r_id], d_range[1]))
                grassmap_mask = GrassMap(mapname)
                grassmap_mask.temporary = True
                return grassmap_mask
        
        self.log.debug("No appropriate interval range found for interval %d" % interval )

    def get_map_resources(self,model):
        """ We need the model to get instances and resolve variables """
        maps = []
        # get initial_maps
        for r_id in self.initial_maps:
            im = self.initial_maps[r_id]
            if not im.temporary: maps.append(im.filename)
        maps_w_mapset = grass.get_g().find_mapsets(maps)
        # get maps in events
        for e in self.events:
            maps_w_mapset.extend(e.get_map_resources(model))
        maps_w_mapset = set(maps_w_mapset) # remove duplicate maps
        return maps_w_mapset
        
    def run(self, interval, rep, temp_map_names, strategy = None):
        grass_i = grass.get_g()
        # Run through events for this lifestage
        for e in self.events:
            mask = ""
            p_intervals = self.getPhenologyIntervals(rep.instance.r_id)
            if len(p_intervals) > 1:
                mask = self.getPhenologyMask(interval,rep.instance.r_id)
                grass_i.make_mask(mask)
            
            e.run(temp_map_names[0], temp_map_names[1], rep, self.populationBased)
            
            if len(p_intervals) > 1:
                # Remove mask because we can't access anythin outside of it using mapcalc
                grass_i.make_mask(None)
                
                # Join Maps
                grass_i.mapcalc(temp_map_names[0],"if(isnull(%s),%s,%s)" % (mask, temp_map_names[0], temp_map_names[1]))
                
                # Merge value outside of original mask, e.g. long distance jumps
                if self.populationBased:
                    grass_i.mapcalc(temp_map_names[1],"if(isnull(%s) && isnull(%s),%s,%s+%s)" % (mask,temp_map_names[1],temp_map_names[0],temp_map_names[0],temp_map_names[1]) )
                else:
                    grass_i.mapcalc(temp_map_names[1],"if(isnull(%s) && isnull(%s),%s,%s)" % (mask,temp_map_names[1],temp_map_names[0],temp_map_names[1]) )
                    
            temp_map_names.reverse()

        # Get management strategy treatments that affect
        # this lifestage.
        treatments = []
        if strategy is not None:
            treatments = strategy.get_treatments_for_ls(self.name,rep.current_t)
        for t in treatments:
            self.log.debug("Applying treatment %d for strategy %s" % \
                    (t.index, strategy.get_name()))
            t_area = t.get_treatment_area_map(rep)
            self.log.debug("Treatment area map is %s" % t_area)
            # Mask so that only treatment area is affected
            grass_i.make_mask(t_area)
            t.get_event().run(temp_map_names[0], temp_map_names[1], rep, False)
            # Remove mask when done
            grass_i.make_mask(None)
            # Now we have to combine the unmasked region from the original map with the
            # the alteration made by the treatment on the masked area.
            if t_area is not None:
                self.tempmap = "wibble_foss"
                grass_i.mapcalc(self.tempmap,'if(isnull("%s"),"%s","%s")' %
                        (t_area, temp_map_names[0], temp_map_names[1]))
                grass_i.copy_map(self.tempmap, temp_map_names[1], overwrite=True)
            temp_map_names.reverse()
    
#   def setPopulationBased(self,value):
#       if value == 0:
#           self.xml_node.attrib["populationBased"] = "True"
#       elif value == 1:
#           self.xml_node.attrib["populationBased"] = "False"
#       else:
#           self.log.warning("Invalid value for lifestage attribute 'population based'")
#       return value
        
#   def isPopulationBased(self):
#       if "populationBased" in self.xml_node.attrib.keys():
#           if self.xml_node.attrib["populationBased"].lower() == "true":
#               return True
#       return False
    
    def analyses(self):
        if len(self.analysis_list) == 0:
            nodes = self.xml_node.xpath("analyses/analysis")
            #pdb.set_trace()
            for node in nodes:
                a=analysis(node)
                self.analysis_list.append(a)
        return self.analysis_list

    def clean_up_maps(self):
        for grassmap in self.initial_maps.values():
            del grassmap
            #grass.get_g().destruct_map(grassmap)
            
    def update_xml(self):
        self.xml_node.attrib["name"] = self.name
        self.xml_node.attrib["populationBased"] = str(self.populationBased)

