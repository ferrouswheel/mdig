#!/usr/bin/env python2.4
#
#  Copyright (C) 2009 Joel Pitt, Fruition Technology
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

import lxml.etree

import grass
from grassmap import GrassMap
from event import Event


class ManagementStrategyException(Exception):

    def __init__(self, *args, **kwargs):
        super(ManagementStrategyException, self).__init__(*args, **kwargs)


class ManagementStrategy(object):
    """
    ManagementStrategy is a class for representing the strategies taken
    by environmental authorities to control the dispersal of a species.

    In the XML model defition, each "strategy" element within the "management"
    element will create a ManagementStrategy instance.
    """

    def __init__(self, node, experiment, instance=None):
        self.log = logging.getLogger("mdig.strategy")

        self.grass_i = grass.get_g()

        self.temp_map_names = {}
        self.active = False
        self.treatments = None
        # We save the experiment instead of the instance
        # because instances are only temporarily associated with strategies
        self.experiment = experiment
        self.instance = instance

        if node is None:
            self.node = self.init_strategy(experiment)
        else:
            self.node = node

    def set_instance(self, instance):
        self.instance = instance

    def init_strategy(self, model):
        """ Initialise the xml structure that represents a ManagementStrategy. """
        raise NotImplementedError()

    def get_name(self):
        return self.node.attrib["name"]

    def set_name(self, name):
        self.node.attrib["name"] = name

    def get_region(self):
        return self.node.attrib["region"]

    def set_region(self, r_id):
        rs = self.experiment.get_regions()
        if r_id not in rs:
            raise grass.SetRegionException("Invalid region ID %s" % r_id)
        self.node.attrib["region"] = r_id

    def get_description(self):
        desc_node = self.node.xpath("description")
        return desc_node[0].text

    def set_description(self, desc):
        desc_node = self.node.xpath("description")
        desc_node[0].text = desc

    def get_delay(self):
        desc_node = self.node.xpath("delay")
        if len(desc_node) == 0:
            return 0
        return int(desc_node[0].text)

    def set_delay(self, delay):
        delay_node = self.node.xpath("delay")
        if len(delay_node) == 0:
            delay_node = [lxml.etree.SubElement(self.node, 'delay')]
        delay_node[0].text = repr(int(delay))  # ensure it's an int

    def get_map_resources(self):
        maps = []
        ts = self.get_treatments()
        for t in ts:
            maps.extend(t.get_map_resources())
        return maps

    def _load_treatments(self):
        """
        Initialise treatments list

        TODO: sort according to treatment index
        """
        self.treatments = []
        self.log.debug("Parsing management strategies")
        treatment_nodes = self.node.xpath("treatments/t")
        self.log.debug("%d treatments found for strategy %s (%s)" %
                      (len(treatment_nodes), self.get_name(), self.get_description()))
        index_counter = 0
        for t_node in treatment_nodes:
            self.treatments.append(Treatment(self, t_node, index_counter))
            index_counter += 1

    def get_treatments(self):
        """
        Get all treatments
        """
        if self.treatments is None:
            self._load_treatments()
        return self.treatments

    def get_treatments_for_param(self, var_key, timestep):
        """
        Get any treatments that affect the parameter specified by var_key
        """
        result = []
        if self.instance is None:
            self.log.error("No instance assigned to ManagementStrategy")
        if timestep < self.experiment.get_period()[0] + self.get_delay():
            return result
        for t in self.get_treatments():
            if t.affects_var(var_key):
                result.append(t)
        return result  # return an empty list if there are none

    def get_treatments_for_ls(self, ls_id, timestep):
        """
        Get any treatments that affect the lifestage specified by ls_id
        """
        result = []
        if timestep < self.experiment.get_period()[0] + self.get_delay():
            return result
        for t in self.get_treatments():
            if t.affects_ls(ls_id):
                result.append(t)
        return result  # return an empty list if there are none


class TreatmentEvent(Event):
    """
    TreatmentEvent differs from a normal MDiG event in that it
    records the population size before and after.
    """

    def run(self, in_name, out_name, rep, is_pop):
        stats_before = grass.get_g().get_univariate_stats({0: in_name})
        metrics = super(TreatmentEvent, self).run(in_name, out_name, rep, is_pop)
        stats_after = grass.get_g().get_univariate_stats({0: out_name})
        metrics['AREA_REMOVED'] = stats_before[0].get('n', 0) - stats_after[0].get('n', 0)
        return metrics


class Treatment(object):

    def __init__(self, strategy, node, t_index):
        self.strategy = strategy
        self.log = logging.getLogger("mdig.treatment")
        self.treatment_type = None

        self.area_ls = None
        self.areas = None

        self.event = None

        if node is None:
            self.node = self.init_treatment()
        else:
            # if node is provided then create treatment from xml
            self.node = node
        self.index = t_index
        # temporary map name
        self.area_temp = None
        # temporary map name
        self.var_temp = "x_t___strategy_" + \
            self.strategy.get_name() + "_var_t_" + str(self.index)

    def __del__(self):
        if 'area_temp' in dir(self):
            grass.get_g().remove_map(self.area_temp)
        if 'var_temp' in dir(self):
            grass.get_g().remove_map(self.var_temp)

    def init_treatment(self):
        # Create the required elements with a default global area and a dummy action
        raise NotImplementedError()

    def affects_var(self, var_key):
        """ True if the treatment modifies the variable specified by var_key """
        av_node = self.node.xpath("affectVariable")
        if len(av_node) > 0:
            assert len(av_node) == 1
            self.treatment_type = "affectVariable"
            if av_node[0].attrib["var"] == var_key:
                return True
        return False

    def affects_ls(self, ls_id):
        """ True if this treatment affects a particular lifestage.

        Note, this doesn't check whether a treatment that affects a variable, has
        that variable within the lifestage specified by ls_id.

        Event variable parameters should be checked individually using
        affects_var()
        """
        if ls_id == self.get_ls():
            return True
        return False

    def get_ls(self):
        """
        Return the lifestage the treatment affects or None if there
        is no lifestage specified
        """
        ls_node = self.node.xpath("event")
        if len(ls_node) > 0:
            assert len(ls_node) == 1
            self.treatment_type = "event"
            return ls_node[0].attrib["ls"]
        return None

    def load_areas(self):
        if self.areas is None:
            self.areas = []
            self.area_node = self.node.xpath("area")
            if len(self.area_node) == 0:
                return self.areas
            assert(len(self.area_node) == 1)
            self.area_node = self.area_node[0]
            self.area_ls = self.area_node.attrib['ls']
            for a in self.area_node:
                # Ignore comment nodes
                if isinstance(a.tag, basestring):
                    self.areas.append(TreatmentArea(a, self, len(self.areas)))
        return self.areas

    def get_treatment_area_map(self, replicate):
        """ Ensure all TreatmentAreas are initialised and return a merged map.

        Returns None if there is no area specified. This would mean the treatment
        is for the whole region.
        """
        areas = self.load_areas()
        if len(areas) == 0:
            return None
        return self._merge_areas(replicate)

    def _merge_areas(self, replicate):
        """
        Merge all the TreatmentArea maps based on the combine attribute
        ("and" or "or" them)
        """
        # Check whether the component Areas change between calls
        if self.area_temp is not None:
            # Whether we need to regenerate the merged area map
            generate = False
            for a in self.areas:
                if a.is_dynamic():
                    # if just one component area is dynamic, we have to regenerate
                    # the merged treatment area.
                    generate = True
                    break
            if not generate:
                # We can just return the last area map we generated if it's not dynamic
                return self.area_temp
        else:
            self.area_temp = "x_t___strategy_"  + self.strategy.get_name() + \
                "_area_t_" + str(self.index)

        g = grass.get_g()
        # remove previous map
        g.remove_map(self.area_temp)
        component_areas = self._get_component_area_maps(replicate)
        if len(component_areas) > 1:
            merge_str = self._get_area_merge_mapcalc_expression(component_areas)
            g.mapcalc(self.area_temp, merge_str)
        else:
            g.copy_map(component_areas[0], self.area_temp)
        return self.area_temp

    def _get_component_area_maps(self, replicate):
        area_maps = []
        last_area = None
        for a in self.areas:
            if self.operator == 'sequence':
                m = a.get_treatment_area(replicate, last_area)
                last_area = m
                area_maps = [last_area]
            else:
                area_maps.append(a.get_treatment_area(replicate))
        return area_maps

    @property
    def operator(self):
        """ The operation used to merge maps """
        operation = self.area_node.attrib.get('combine', 'and')
        assert(operation in ("and", "or", "sequence"))
        return operation

    def _get_area_merge_mapcalc_expression(self, component_areas):
        # build the mapcalc expression to merge the treatment areas
        merge_str = "if("
        for area_map in component_areas:
            if self.operator == "and":
                merge_str += "!isnull(%s)" % area_map
                merge_str += " && "
            elif self.operator == "or":
                merge_str += "!isnull(%s)" % area_map
                merge_str += " || "
            else:
                assert False, "Bad merge operator for mapcalc merge"
        # remove trailing operator
        merge_str = merge_str[:-4] + ",1,null())"
        return merge_str

    def get_event(self):
        """
        If the treatment runs an event at the end of the lifestage, create and
        return it. Otherwise return None.
        """
        if self.event is not None:
            return self.event
        e_node = self.node.xpath("event")
        if len(e_node) > 0:
            assert len(e_node) == 1
            self.treatment_type = "event"
            self.event = TreatmentEvent(e_node[0])
        return self.event

    def get_map_resources(self):
        # get maps from within treatment event
        m = self.strategy.experiment
        e = self.get_event()
        maps = []
        if e:
            maps.extend(e.get_map_resources(m))
        # get maps from within area specification
        if self.areas is None:
            self.load_areas()
        for a in self.areas:
            maps.extend(a.get_map_resources())
        return maps

    def get_variable_map(self, var_key, var_val, replicate):
        """
        Get the map that represents a variable that is impacted by
        affectsVarable, for the specific regions within get_treatment_area.

        Returns None if this treatment does not affect var_key.
        """
        if not self.affects_var(var_key):
            return None
        area_mask_map = self.get_treatment_area_map(replicate)
        if area_mask_map is None:
            # This means the treatment is applied globally, no need to return
            # a map
            return None
        altered_value = self.get_altered_variable_value(var_key, var_val)
        if altered_value is None:
            altered_value = "null()"
        orig_value = var_val
        if orig_value is None:
            orig_value = "null()"
        grass.get_g().mapcalc(self.var_temp,
                              "if(" + area_mask_map + "==1,"
                              + str(altered_value) + "," + str(orig_value) + ")")
        return self.var_temp

    def get_altered_variable_value(self, var_key, var_val):
        """
        Get the value of the variable after it is altered by affectVariable
        """
        if not self.affects_var(var_key):
            return None
        orig_value = var_val
        # handle decrease, increase, ratio
        av_node = self.node.xpath("affectVariable")
        # should only be one affectVariable element, and only one child indicating
        # effect
        effect = None
        # Find the first non-comment element
        for i in av_node[0]:
            if isinstance(i.tag, basestring):
                effect = i.tag
                effect_amount = i.text
                break
        assert(effect is not None)
        new_value = None
        try:
            effect_amount = float(effect_amount)
            if orig_value is not None:
                new_value = float(orig_value)
        except ValueError, e:
            raise ManagementStrategyException(
                'Invalid value for altering variable %s' % str(e))

        # if the variable is originally None
        # the only acceptable change is for exact value
        # to be specified
        if new_value is None:
            if effect == "value":
                new_value = effect_amount
            else:
                raise ManagementStrategyException(
                    'Invalid variable alteration')

        # the alternative is that the original value is altered
        if effect == "decrease":
            new_value -= effect_amount
        elif effect == "increase":
            new_value += effect_amount
        elif effect == "ratio":
            new_value *= effect_amount
        elif effect == "value":
            new_value = effect_amount
        else:
            raise ManagementStrategyException(
                "Unknown management effect: " + str(effect))
        return new_value


class TreatmentArea:

    def __init__(self, node, treatment, a_index):
        """
        node is the xml node defining the TreatmentArea.
        treatment is the parent Treatment this area is for.
        a_index is the area index used to create the temp map name.
        """
        self.treatment = treatment
        self.node = node
        self.area = None
        self.area_filter_output = None
        self.index = a_index
        # temporary map name
        self.area_temp = "x_t___strategy_"  + self.treatment.strategy.get_name() + \
            "_area_t_" + str(self.treatment.index) + "_" + str(self.index)
        self.init_from_xml()

    def __del__(self):
        if self.area_filter_output is not None:
            grass.get_g().remove_map(self.area_filter_output)

    def init_from_xml(self):
        if self.node.tag == "mfilter":
            self.area = Event(self.node)
        else:
            # If it's not an mfilter it must be a map
            self.area = GrassMap(self.node)

    def is_dynamic(self):
        """
        Return whether this TreatmentArea changes each timestep or not. An area
        if dynamic if it uses an event/mfilter or a GrassMap with refresh==True.
        An example of the latter case is using r.mapcalc.
        """
        if isinstance(self.area, Event):
            return True
        elif isinstance(self.area, GrassMap):
            return self.area.refresh
        else:
            raise Exception("Unknown area type")

    def get_map_resources(self):
        maps = []
        if isinstance(self.area, Event):
            m = self.treatment.strategy.experiment
            maps.extend(self.area.get_map_resources(m))
        elif isinstance(self.area, GrassMap):
            if self.area.xml_map_type == "name":
                g = grass.get_g()
                maps.append((self.area.filename, g.find_mapset(
                    self.area.filename)))
        return maps

    def get_treatment_area(self, replicate, last_area=None):
        """
        Get the map name representing the treatment area, generating it
        dynamically if necessary.
        """
        if isinstance(self.area, Event):
            if self.area_filter_output is not None:
                grass.get_g().remove_map(self.area_filter_output)

            if last_area:
                dist_map = last_area
            else:
                dist_map = replicate.temp_map_names[self.treatment.area_ls][0]

            self.area.run(dist_map, self.area_temp, replicate, False)

            self.area_filter_output = self.area_temp
            return self.area_filter_output
        elif isinstance(self.area, GrassMap):
            replacements = {
                "POP_MAP": replicate.temp_map_names[self.treatment.area_ls][0],
                "START_MAP": replicate.initial_maps[self.treatment.area_ls].get_map_filename()
            }
            return self.area.get_map_filename(replacements)
