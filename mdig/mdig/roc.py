#!/usr/bin/env python
import os
import sys
import pdb
import logging
import shelve
from numpy import *
from pylab import *
from subprocess import *
#from IPython.numutils import frange

import mdig
from mdig import grass
from mdig import model

import random

class IncompleteModelException(Exception):
    pass

class ROCanalysis:
    """ Carries out ROC analysis.

    Works out ROC curves for occupancy envelopes, calculates AUC for each
    year. Does bootstrapping and statistical analysis

    The results of the ROC analysis are stored in the self.reps list.

    The AUCs are not explicitly stored in this object, but when the results are
    shelved, then AUCs are saved in the key 'AUCs' and the reps object is in
    'ROCs'.

    The format of the reps list is:

    [ rep1, rep2, ... repN ]

    Each rep is a dictionary with the format:

    [ t0: S_0, t1: S_1, ... T: S_T ]

    where the keys and indices are the time step and T is the last time step.
    Each S has the format:

    [ m1, m2, ... mM ]

    where each entry are the ROC results for the given model, with M being the
    total models being assessed. Each M has the format:
    
    [ threshold_0,    sensitivity, 1-specificity, proportion of area 
      threshold_0.01, ..                                             
      ..
      threshold_1, ..                                               ]

    Where the threshold are a range from -0.01 to 1.0, and for each threshold
    the occupancy map is assessed for sensitivity, 1-specificity, and the
    proportion of the total area the envelope covers (at that threshold).

    """


    # Number of bootstraps to carry out
    n_bootstraps = 1
    absence_min_dist = 1000

    min_time=1951
    max_time=2008

    #area_mask="null_est_prob_no_zero_ei@bdavidii"

    # temporary map names
    # TODO make these specific to the class instance, or better yet, register
    # them with the GRASS interface
    temp_vect_name_new = "x__temp_random_new"
    temp_vect_name = "x__temp_random"
    temp_rast_name = "x__temp_rast_combo"

    temp_yearly_basename = "x__temp_vector_t_"

    start_sites_N = 0 #10000
    multiplier_N = 1 #10

    def __init__(self, model_names, options):
        # 2 for 1-specificity, 3 for area
        self.roc_xaxis=3

        self.model_names = model_names
        self.yearly_vectors = {}
        self.save_to_star = False

        self.g = grass.get_g()
        self.log = logging.getLogger("mdig.roc")
        self.reps = []

        self.import_options(options)
        self.models = {}
        self.load_models(self.model_names,options.model_tags)

    def import_options(self, options):
        # Sites vector is required
        self.sites_vector = options.sites_vector
        # Area mask is required
        # used for proportion cover calc and for generating absences
        self.area_mask = options.area_mask
        # Lifestage to create ROC curves for
        self.lifestage = options.lifestage
        # Dir to output results to
        self.output_dir = options.output_dir
        # file to store results as a python shelf
        self.output_shelf_fn = os.path.join(self.output_dir,"roc_results.pyshelve")
        self.output_shelf = None
        # Whether to graph ROC curves
        self.graph_roc = options.graph_roc
        # Whether to calculate and output AUC
        self.do_auc = options.calc_auc
        # Whether to graph AUC values through time
        self.graph_auc = options.graph_auc
        # Whether to calculate VUC
        self.do_vuc = options.calc_vuc

        # Set up times
        self.start_time = ROCanalysis.min_time
        self.end_time = ROCanalysis.max_time
        if options.start_time is not None:
            self.start_time = options.start_time
        if options.start_time is not None:
            self.end_time = options.start_time
        # Bootstraps
        self.n_bootstraps = ROCanalysis.n_bootstraps
        if options.bootstraps is not None:
            self.n_bootstraps = int(options.bootstraps)

    def load_models(self, m_names, tags=None):
        """ Load models and ensure that all occupancy envelopes are generated
        """
        earliest_model_t = 1e+16
        latest_model_t = -1
        for m_name in m_names:
            all_models = mdig.repository.get_models()
            m_file = all_models[m_name]
            m = model.DispersalModel(m_file, setup=False)
            if m.get_period()[0] < earliest_model_t:
                earliest_model_t = m.get_period()[0] 
            if m.get_period()[1] > latest_model_t:
                latest_model_t = m.get_period()[1] 
            if tags is not None:
                m_index = m_names.index(m_name)
                self.models[tags[m_index]] = m
            else:
                self.models[m_name] = m
        # Replace the model names with the tags passed by command line
        if tags is not None:
            self.model_names = tags
            m_names = tags
        # Trim time range to extents of models if necessary
        if earliest_model_t > self.start_time:
            self.start_time = earliest_model_t
        if latest_model_t < self.end_time:
            self.end_time = latest_model_t

        for m_name in m_names:
            self.log.info("Loading model: " + m_name)
            self.models[m_name].init_mapset()
            if not self.models[m_name].is_complete():
                raise IncompleteModelException()
            self.models[m_name].update_occupancy_envelope()

    def g_run(self,cmd):
        self.g.run_command(cmd)

    def add_new_random_absences(self, source_map, presence_map):
        N = ( ROCanalysis.start_sites_N + (self.g.count_sites(presence_map) * \
                    ROCanalysis.multiplier_N) ) - self.g.count_sites(ROCanalysis.temp_vect_name)
        if N < 1:
            return
        self.log.debug("Adding %d random absences." % N)
        # find random points
        self.g_run("r.random --o input=%s vector_output=%s n=%d" %
            (source_map, ROCanalysis.temp_vect_name_new, N) )
        # set random points to have 0 value
        self.g_run("v.db.update map=%s column=value value=0" %
            ROCanalysis.temp_vect_name_new)
        # add column for distance
        self.g_run("v.db.addcol map=%s columns=\"dist double precision\"" %
            ROCanalysis.temp_vect_name_new)
        # join with existing random absences
        self.g_run("g.rename vect=%s,xxxxxxxxxx" % ROCanalysis.temp_vect_name )
        self.g_run("v.patch -e input=xxxxxxxxxx,%s output=%s" % 
            (ROCanalysis.temp_vect_name_new, ROCanalysis.temp_vect_name) )
        self.g_run("g.remove vect=xxxxxxxxxx")
        # remove any random points that are within certain distance of an actual
        # presence
        self.g_run("g.remove vect=%s" % ROCanalysis.temp_vect_name_new)
        self.g_run("v.distance from=%s to=%s upload=dist column=dist" %
                (ROCanalysis.temp_vect_name, presence_map) )
        self.g_run("v.extract input=%s output=%s where=\"dist>%d\"" %
                ( ROCanalysis.temp_vect_name, ROCanalysis.temp_vect_name_new, \
                ROCanalysis.absence_min_dist ) )
        self.g_run("g.remove vect=%s" % ROCanalysis.temp_vect_name)
        self.g_run("g.rename vect=%s,%s" % (ROCanalysis.temp_vect_name_new,ROCanalysis.temp_vect_name) )

    def merge_sites(self, presences, absences, result):
        # join vectors and then assess envelope values
        # for both actual points and random absences
        # first make sure their columns are the same:
        self.log.debug("Merging presences!")
        temp_merge_name = "x__merge_sites"
        self.g_run("g.copy vect=%s,%s" % (absences,temp_merge_name) )
        self.g_run("v.db.addcol map=" + temp_merge_name + " columns=\"year integer, x"
                " double precision, y double precision, est_prob double precision\"")
        # Give absences a fake year 0
        self.g_run("v.db.update map=" + temp_merge_name + " column=year value=0")
        self.g_run("v.db.dropcol map=" + temp_merge_name + " column=dist")
        self.g_run("v.db.addcol map=" + presences + " columns=\"value integer\"")
        self.g_run("v.db.update map=" + presences + " column=value value=1")
        self.g_run("v.db.dropcol map=" + temp_merge_name + " column=value")
        self.g_run("v.db.addcol map=" + temp_merge_name + " columns=\"value integer\"")
        self.g_run("v.db.update map=" + temp_merge_name + " column=value value=0")
        self.g_run("v.patch input=" + presences + "," + temp_merge_name + " output=" + result +
                " --o -e")
        self.g_run("g.remove vect=%s" % temp_merge_name)

    def run_stats(self, envelope_map, class_map):
        # r.stats with occupancy envelope and points rast
        output = Popen("r.stats -c nsteps=200 input=" + envelope_map + "," + class_map,
                shell=True, bufsize=1024, stdout=PIPE).stdout
        # parse output into dict for area
        # first key is the prediction, second is the prob
        cell_areas={}
        for i in output.readlines():
            fields = i.split(" ")
            occ_range = tuple(fields[0].split("-"))
            if fields[1] not in cell_areas:
                cell_areas[fields[1]] = {}
            cell_areas[fields[1]][occ_range] = int(fields[2])
        output.close()
        return cell_areas

    def get_envelopes_across_models(self, t):
        envelopes = []
        for m_name in self.model_names:
            m_period = self.models[m_name].get_period()
            if m_period[0] <= t and m_period[1] >=t:
                envelopes.extend( self.get_envelopes_across_instances(self.models[m_name],t) )
        return envelopes

    def get_envelopes_across_instances(self, model, t):
        envelopes = []
        # TODO handle multiple instances within a model
        # for i in model.get_instances():
        i = model.get_instances()[0]
        x = i.get_occupancy_envelopes()[self.lifestage][str(t)]
        if self.g.no_mapset_component(x):
            x += "@" + model.get_mapset()
        envelopes.append(x)
        return envelopes

    def run_stats_across_models(self, t, class_map):
        self.g_run("r.mask " + class_map)
        cmd = "r.stats -1N input=" + class_map
        #header=[]
        absences=[]
        presences=[]
        for env in self.get_envelopes_across_models(t):
            cmd += "," + env
        print cmd
        # r.stats with occupancy envelopes and points rast
        output = Popen(cmd, shell=True, bufsize=1024, stdout=PIPE).stdout
        # parse output into absences and presences 
        for i in output.readlines():
            fields = i.split(" ")
            for j in range(1,len(fields)):
                fields[j] = fields[j].strip()
                if fields[j] == "*":
                    fields[j] = 0.0
                else:
                    fields[j] = float(fields[j])
                m_name = self.model_names[j-1]
                if fields[0] != "*" and int(fields[0]) != 0 and \
                        self.models[m_name].get_period()[0] > int(fields[0]):
                    fields[j] = None
            if fields[0] != "*" and int(fields[0]) > 0:
                # presences records contain year
                presences.append(fields[1:])
            elif fields[0] is "0":
                absences.append(fields[1:])
            # ignore sites NOT in the presence/absence map fields[0]="*"
        self.g_run("r.mask -r")
        return (presences, absences)

    def calculate_thresholded_areas(self,t,thresholds):
        self.g_run("r.mask " + self.area_mask)
        cmd = "r.stats -1N input=" + self.area_mask
        areas=[]
        for env in self.get_envelopes_across_models(t):
            cmd += "," + env
            areas.append([0]*len(thresholds))
        print cmd
        # r.stats with occupancy envelopes and points rast
        output = Popen(cmd, shell=True, bufsize=1024, stdout=PIPE).stdout
        # parse output into absences and presences 
        for i in output.readlines():
            fields = i.split(" ")
            for j in range(1,len(fields)):
                fields[j] = fields[j].strip()
                if fields[j] == "*":
                    fields[j] = 0.0
                else:
                    fields[j] = float(fields[j])
                t_index=0
                while (t_index < len(thresholds) and thresholds[t_index] < fields[j]):
                    areas[j-1][t_index] += 1
                    t_index += 1
        # convert cell counts to proportion of cells possibly occupied
        max_potential_cells = float(self.g.count_cells(self.area_mask))
        for i in range(0,len(areas)):
            areas[i] = [x / max_potential_cells for x in areas[i]]
        # remove mask
        self.g_run("r.mask -r")
        return areas

    def calc_pred_numbers(self, presences, absences, threshold):
        """
            format is
            [ [pred_model_1_site_1, pred_model_2_site_1, ... ]
              [pred_model_1_site_2, pred_model_2_site_2, ... ]
            ...
            ]
        """
        true_positives = array([])
        false_negatives = array([])
        true_negatives = array([])
        false_positives = array([])
        if len(presences) > 0:
            true_positives = array([0.0]*len(presences[0]))
            false_negatives = array([0.0]*len(presences[0]))
        if len(absences) > 0:
            true_negatives = array([0.0]*len(absences[0]))
            false_positives = array([0.0]*len(absences[0]))
        
        for row in presences:
            for i in range(0,len(row)):
                if row[i] is None:
                    continue
                if row[i] > threshold:
                    true_positives[i] += 1
                else:
                    false_negatives[i] += 1
        for row in absences:
            for i in range(0,len(row)):
                if row[i] > threshold:
                    false_positives[i] += 1
                else:
                    true_negatives[i] += 1
        return (true_positives, false_positives, true_negatives, false_negatives)

    def sort_roc_points(self,s):
        """
        Sort sensitivity/specificity points so that they can be plotted
        """
        s.sort(key=lambda x:(x[1],x[self.roc_xaxis]))
        return s

    def process_roc_points(self, s, add_pessimistic_points=True):
        """ intersperse points of s with points that will make ROC 
            be a pessimistic graph.
        @param The ROC time replicate to process
        @param Whether to interpolate points with pessimistic values
        @return sorted points
        """
        s = self.sort_roc_points(s)
        if add_pessimistic_points:
            s_pessimistic = []
            last_point = (0,0) # x,y order
            # note, s is in year, y, x order
            for row in s:
                if row[self.roc_xaxis] > last_point[0]:
                    s_pessimistic.append( (row[0], last_point[1], row[2], row[3] ) )
                s_pessimistic.append( row )
                last_point = (row[self.roc_xaxis], row[1])
            s = s_pessimistic
        return s

    def plot_and_save_rocs(self, S, basename="roc_", specificity_range=(0,1)):
        for t in S:
#linestyles = []
            headers=[]
            for m_name in self.model_names:
                m = self.models[m_name]
                if m.get_period()[0] <= t and m.get_period()[1] >= t:
                    # TODO give each model instance a customisable linestyle
#                    linestyles.append('-') #m["linestyle"])
                    headers.append(m.get_name())
            f=figure()
            self.plot_roc(S[t],S_labels=headers,specificity_range=specificity_range,
                plot_null=True) #linestyles=linestyles,
            title("Model ROC comparison for " + repr(t))
            f.savefig(os.path.join(self.output_dir,basename+repr(t)+".png"))
            close(f)

    def plot_roc(self, S, S_labels=[], scatter=False, \
            specificity_range=(0,1), linestyles=None, plot_null=False):
        """ Plot roc for single year
            S is array/list of triples (sensitivity, 1-specificity, area),
            one for each model
        """
        legend_prefix = " (AUC "
        if specificity_range[0] > 0 or \
            specificity_range[1] < 1.0:  
            legend_prefix = " (pAUC "
            # Highlight the range of specifity of interest
            bar(0,1.0,1-specificity_range[1],fc="0.9",ec="0.8")
            bar(1-specificity_range[0],1.0,1-((1-specificity_range[1])+\
                        (1-specificity_range[0])),fc="0.9",ec="0.8")
        if plot_null:
            plot((0,1),(0,1),linestyle='--')
        for i in range(0,len(S)):
            s_label=""
            s = S[i]
            if i < len(S_labels):
                s_label = S_labels[i]
            s_label += legend_prefix + str(round(self.calc_auc(s,specificity_range), 4)) + ")"
            if scatter:
                scatter([x[self.roc_xaxis] for x in s],[x[1] for x in s],label=s_label)
            else:
                s = self.process_roc_points(s)
                if linestyles is not None:
                    plot([x[self.roc_xaxis] for x in s], [x[1] for x in s], \
                            label=s_label,linestyle=linestyles[i],color="0.3")
                else:
                    plot([x[self.roc_xaxis] for x in s], [x[1] for x in s],label=s_label)
        xlim(0,1)
        ylim(0,1)
        if self.roc_xaxis == 3:
            xlabel("Proportion of area")
        else:
            xlabel("1-Specificity")
        ylabel("Sensitivity")
        legend(loc='lower right')

    def plot_yearly_roc(self, r_S, index):
        for t in r_S:
            plot_roc(r_S[t][index],S_label=repr(t))
        plot([0,1],[0,1],'--',color='0.5')
        xlim(0.0,1.0)
        if self.roc_xaxis == 3:
            xlabel("Proportion of area")
        else:
            xlabel("1-Specificity")
        ylim(0.0,1.0)
        ylabel("Sensitivity")
        legend()

    def calc_auc_across_models(self, S,specificity_range=(0,1.0),method="pessimistic"):
        auc = []
        for s in S:
            a = self.calc_auc(s,specificity_range,method)
            auc.append(a)
        return auc

    def calc_auc(self, s,specificity_range=(0,1.0),method="pessimistic"):
        x_range = [1-x for x in specificity_range]
        x_range.reverse()
        assert(x_range[1] - x_range[0] > 0) 
        total_area=0.0
        s = self.sort_roc_points(s)
        last_s_pair = (0.0, 0.0, x_range[0])
        for row in s:
            # reminder... row is in [thres,y,x] order
            if row[self.roc_xaxis] >= last_s_pair[2]:
                if row[self.roc_xaxis] <= x_range[1]:
                    # first rectangle
                    total_area += last_s_pair[1] * \
                        (row[self.roc_xaxis] - last_s_pair[2])
                    if method == "trapezoid":
                        # calculate trapezoid area
                        # triangle on top
                        # TODO, use angle to work out height for when min
                        # range is in middle of triangle
                        total_area += (row[1] - last_s_pair[1]) * \
                            (row[self.roc_xaxis] - last_s_pair[2]) / 2.0
                    elif method == "optimistic":
                        # calculate rect area on top
                        total_area += (row[1] - last_s_pair[1]) * \
                            (row[self.roc_xaxis] - last_s_pair[2])
                elif last_s_pair[2] < x_range[1]:
                    # only part of shape to consider
                    # first rectangle
                    total_area += last_s_pair[1] * \
                        (x_range[1] - last_s_pair[2])
                    if method == "trapezoid":
                        # calculate trapezoid area
                        # find angle, and then height at spec_x
                        print "Warning, trapezoid method for AUC not implemented"
                        return -1
                        # TODO, use angle to work out height
                        total_area += (row[1] - last_s_pair[1]) * \
                            (row[self.roc_xaxis] - last_s_pair[2]) / 2.0
                    elif method == "optimistic":
                        # calculate rect area on top
                        total_area += (row[1] - last_s_pair[1]) * \
                            (x_range[1] - last_s_pair[2])
            last_s_pair = (row[0], row[1], row[self.roc_xaxis])
        return total_area

    def make_yearly_sites_maps(self, orig_name):
        # make yearly vector maps
        temp_rep_vector="x__sites_rep"
        # Keep track of the mapset this are being made in...
        current_mapset = self.g.get_mapset()
        output = Popen("v.out.ascii --q input=" +orig_name + " columns=year,est_prob", \
                shell=True, stdout=PIPE).communicate()[0]
        output = output.split('\n')
        sites_to_use = []
        num_sites = 0
        for i in range(0,len(output)):
            if random.random() < 0.9:
                x = output[i].split("|")
                if (len(x) < 5):
                    print "line doesn't have 5 fields: " + repr(x)
                else:
                    sites_to_use.append("|".join((x[2],x[3],x[0],x[1],x[4])))
                    num_sites += 1
        self.log.info("Randomly sampled " + str(num_sites) + " sites for " + \
                "next replicate comparison map.")
        p = Popen("v.in.ascii -n --q output=" + temp_rep_vector + \
                " columns='cat int, year int, x double precision, y double precision," +\
                " est_prob double precision' cat=1 x=3 y=4 --o", \
                shell=True, stdin=PIPE, stdout=PIPE)
        p.communicate('\n'.join(sites_to_use))
        for t in range(self.start_time,self.end_time+1):
            self.log.info("Creating vector comparison map for year " + str(t))
            self.yearly_vectors[t] = ROCanalysis.temp_yearly_basename + repr(t) \
                + "@" + current_mapset
            self.g_run("v.extract --q input=" + temp_rep_vector + " output=" +
                    self.yearly_vectors[t] + " where=\"year>=" + repr(self.start_time)
                    + " and year<=" + repr(t) + "\"")
        self.yearly_vectors_mapset = current_mapset
#self.g_run("g.remove vect=" + temp_rep_vector)

    def run(self):
        # TODO
        #r = ROCReplicate(self.yearly_vectors,models)
        self.log.info("=============CALCULATING ROCs==============")
        self.reps=self.replicate_roc_calc(self.n_bootstraps)
        # Save ROC reps
        self.output_shelf = shelve.open(self.output_shelf_fn)
        self.output_shelf["ROCs"] = self.reps
        self.output_shelf.close()
        self.aucs=[]
        self.vucs=[]
        inv_x_range = (0.5,1.0) # High specificity, gets reversed in graphs etc.
        null_auc = 0.125 # this is dependent on the above range, TODO make function
        if self.graph_roc:
            self.log.info("=============PLOTTING ROCs==============")
            counter=0
            for r in self.reps:
                self.plot_and_save_rocs(r,"r" + repr(counter) + "_roc_", \
                        inv_x_range)
                counter+=1
        if self.graph_auc or self.do_auc or self.do_vuc:
            self.log.info("============CALCULATING AUCs============")
            for r in self.reps:
                auc=[]
                for t in r:
                    auc.append([t] + self.calc_auc_across_models(r[t],inv_x_range))
                self.aucs.append(auc)
        # Save AUCs
        self.output_shelf = shelve.open(self.output_shelf_fn)
        self.output_shelf["AUCs"] = self.aucs
        self.output_shelf.close()
        if self.graph_auc:
            counter=0
            self.log.info("============PLOTTING AUCs============")
            for auc in self.aucs:
                self.plot_auc(auc,'r'+str(counter),null_auc)
                counter+=1
        # plot 3d ROC
        #plot_3d_ROC(r_S)
        # volume under curve
        if self.do_vuc:
            self.vucs = calc_vucs(self.aucs)
        # TODO calculate average, s.d. and save data
        self.output_shelf = shelve.open(self.output_shelf_fn)
        self.output_shelf["VUCs"] = self.vucs
        self.output_shelf.close()

        return (self.reps, self.aucs)

    def calc_average_auc(self, aucs):
        pass

    def plot_auc(self, auc, basename="",null_auc=None):
        f=figure()
        legend_names = []
        if null_auc is not None:
            hlines(null_auc,self.start_time,self.end_time)
            legend_names.append("Null")
        years = [x[0] for x in auc] 
        for x in array(auc)[:,1:].T:
            start_index = 0
            while x[start_index] == 0:
                start_index+=1
            plot(years[start_index:],x[start_index:])
        legend_names.extend(self.model_names)
        xlim(self.start_time,self.end_time)
        title("AUC comparison")
        if null_auc == 0.5:
            xlabel("AUC")
        else:
            xlabel("Partial AUC")
        ylabel("Year")
        legend(legend_names)
        grid()
        f.savefig(os.path.join(self.output_dir,"auc_"+basename+".png"))
        close(f)

    def calc_vucs(self, aucs):
        vucs=[]
        for auc in aucs:
            x = array(auc)
            vuc = []
            # first dim is # of rows
            # second is # of models (+1 for time)
            # for each model (thru time)
            for i in x.T:
                vuc.append(sum(i) / float(len(i)))
            vucs.append(vuc)
        return vucs

    def replicate_roc_calc(self,replications=1):
        reps = []
        for r in range(0,replications):
            self.log.info("=========== Running ROC replicate %d =========" % N)
            self.make_yearly_sites_maps(self.sites_vector)

            r_S=self.calculate_roc_S()
            reps.append(r_S)

            # remove all temp maps:
            for t in self.yearly_vectors:
                self.g.change_mapset(self.yearly_vectors_mapset)
                self.g_run("g.remove vect=" + self.yearly_vectors[t])
        return reps

    def compare_establishment_maps_with_roc(maps,sites_map):
        #### warning: not set up to calculate random absences.
        # i.e. it will only use area as x axis
        temp_file = "x_______compare_est_prob_w_sites_map"
        
        #### Calculate each maps prediction for each site
        self.g_run("v.to.rast input=" + sites_map + " output=" + \
                temp_file + " use=val")
        self.g_run("r.mask " + temp_file)
        cmd = "r.stats -1N input="
        presences=[]
        for m in maps:
            cmd += m + ","
        cmd = cmd[0:-1]
        print cmd
        # r.stats with occupancy envelopes and points rast
        output = Popen(cmd, shell=True, bufsize=1024, stdout=PIPE).stdout
        # parse presence values
        for i in output.readlines():
            fields = i.split(" ")
            for j in range(0,len(fields)):
                fields[j] = fields[j].strip()
                if fields[j] == "*":
                    fields[j] = 0.0
                else:
                    fields[j] = float(fields[j])/100.0
            presences.append(fields)
        self.g_run("r.mask -r")

        #### Calculate the total area for each map at each threshold
        thresholds = [-0.01 + (i*0.01) for i in range(0,102)]
        self.g_run("r.mask " + self.area_mask)
        cmd = "r.stats -1N input=" + self.area_mask
        areas=[]
        #header_index=[]
        for m in maps:
            cmd += "," + m
            areas.append([0]*len(thresholds))
        print cmd
        # r.stats with occupancy envelopes and points rast
        output = Popen(cmd, shell=True, bufsize=1024, stdout=PIPE).stdout
        # parse output into absences and presences 
        for i in output.readlines():
            fields = i.split(" ")
            for j in range(1,len(fields)):
                fields[j] = fields[j].strip()
                if fields[j] == "*":
                    fields[j] = 0.0
                else:
                    fields[j] = float(fields[j])/100.0
                t_index=0
                while (t_index < len(thresholds) and thresholds[t_index] < fields[j]):
                    areas[j-1][t_index] += 1
                    t_index += 1
        # convert cell counts to proportion of cells possibly occupied
        max_potential_cells = float(self.g.count_cells(self.area_mask))
        for i in range(0,len(areas)):
            areas[i] = [x / max_potential_cells for x in areas[i]]
        # remove mask
        self.g_run("r.mask -r")
        self.g_run("g.remove rast=" + temp_file)

        ####
        # init result S
        S = []
        for m in maps:
            S.append([])
        for t_index in range(0,len(thresholds)):
            threshold = thresholds[t_index]
            preds = self.calc_pred_numbers(presences, [], threshold)
            # calculate sensitivity
            sensitivity = preds[0] / (preds[0]+preds[3])
            # make area list for this threshold across models
            area = []
            for m in maps:
                area.append(areas[maps.index(m)][t_index])
            val = zip([threshold]*len(sensitivity), sensitivity,
                    [0]*len(sensitivity), area)
            for i in range(0,len(val)):
                assert len(val[i]) == 4
                S[i].append(val[i])
        return S

    def calculate_roc_S(self, save_to_star=False):
        r_S = {}
        # make initial random points map to add to
        self.g_run( "r.random input=" + self.area_mask + 
            " vector_output=" + ROCanalysis.temp_vect_name + " n=1000" )
        # set random points to have 0 value
        self.g_run("v.db.update map=" + ROCanalysis.temp_vect_name + " column=value value=0")
        self.g_run("v.db.addcol map=%s columns=\"dist double precision\"" %
           ROCanalysis.temp_vect_name)
        for t in range(self.start_time,self.end_time+1):
            # make new random absences with r.random
            # (filtered by suitability > 0) and output vector map
            self.add_new_random_absences(self.area_mask, self.yearly_vectors[t])
            self.merge_sites(self.yearly_vectors[t],ROCanalysis.temp_vect_name,ROCanalysis.temp_vect_name_new)
            # convert joined vector to rast
            self.g_run("v.to.rast --o input=" + ROCanalysis.temp_vect_name_new +
                    " output=" + ROCanalysis.temp_rast_name + " column=year use=attr")

            (presences, absences) = \
                self.run_stats_across_models(t,ROCanalysis.temp_rast_name)
            thresholds =  [-0.01 + (i*0.01) for i in range(0,102)]
            areas = self.calculate_thresholded_areas(t,thresholds)
            
            # init result S
            S = []
            for m_index in range(0,len(self.models)):
                S.append([])
            for t_index in range(0,len(thresholds)):
                threshold = thresholds[t_index]
                preds = self.calc_pred_numbers(presences, absences, threshold)
                sensitivity = [0]*len(self.models)
                specificity = [0]*len(self.models)
                if len(preds[0]) > 0 and len(preds[3]) > 0:
                    # calculate sensitivity
                    sensitivity = preds[0] / (preds[0]+preds[3])
                if len(preds[2]) > 0 and len(preds[1]) > 0:
                    # calculate specificity
                    specificity = preds[2] / (preds[2]+preds[1])
                # make area list for this threshold across models
                area = []
                for m_name in self.model_names:
                    m = self.models[m_name]
                    if m.get_period()[0] <= t and m.get_period()[1] >= t:
                        area.append(areas[self.model_names.index(m_name)][t_index])
                val = zip([threshold]*len(sensitivity), sensitivity, 1-specificity,
                        area)
                for i in range(0,len(self.model_names)):
                    m_name = self.model_names[i]
                    m = self.models[m_name]
                    if m.get_period()[0] <= t and m.get_period()[1] >= t:
                        assert len(val[i]) == 4
                        S[i].append(val[i])
            r_S[t] = S

            if (self.save_to_star):
                # Dump predictions so we can put them into StAR web interface:
                # http://protein.bio.puc.cl/cardex/servers/roc/roc_analysis.php
                self.save_to_star_format("r" + repr(r) + "_" + star_output_base_name,
                        self.models, presences, absences, t)

        # remove temp maps
        self.g_run("g.remove vect=" + ROCanalysis.temp_vect_name)
        self.g_run("g.remove vect=" + ROCanalysis.temp_vect_name_new)
        self.g_run("g.remove rast=" + ROCanalysis.temp_rast_name)

        return r_S

    ###############
    # Will probably delete these STAR output functions as we've implemented more
    # advanced/appropriate statistical techniques here
    def create_star_format_row(self, row):
        row_str = ""
        for x in row:
            # convert predictions of sites that a guaranteed to exist into
            # predictions of 1.0 - since StAR requires paired data
            if x is None:
                x = 1.0
            row_str += ("%.3f" % x) + "\t"
        return row_str.strip()

    def save_to_star_format(self, base_name, models, presences, absences, t):
        # create header string
        header_line = ""
        for m in models: 
            header_line += "\"" + m["name"] + "\"\t" 
        header_line = header_line.strip()
        # Write presences
        f = open(base_name + "_presences_" + repr(t) + ".dat", 'w')
        f.write(header_line)
        f.write("\n")
        for row in presences:
            f.write(create_star_format_row(row))
            f.write("\n")
        f.close()
        # Write absences
        f = open(base_name + "_absences_" + repr(t) + ".dat", 'w')
        f.write(header_line)
        f.write("\n")
        for row in absences:
            f.write(create_star_format_row(row))
            f.write("\n")
        f.close()




