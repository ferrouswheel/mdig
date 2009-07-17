#!/usr/bin/env python
import os
import sys
import pdb
from numpy import *
from pylab import *
from subprocess import *
from IPython.numutils import frange
# Import details about each simulation
import model_definition as mdef

class ROCAnalysis:

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
        self.import_options(options)
        self.yearly_vectors = {}

        self.g = GRASSInterface.getG()
        self.log = logging.getLogger("mdig.roc")
        self.reps = []

    def import_options(self, options):
        # Sites vector is required
        self.sites_vector = options.sites_vector
        # Area mask is required
        # used for proportion cover calc and for generating absences
        self.area_mask = options.area_mask

        # Set up times
        self.start_time = ROCAnalysis.min_time
        self.end_time = ROCAnalysis.max_time
        if options.start_time is not None:
            self.start_time = options.start_time
        if options.start_time is not None:
            self.end_time = options.start_time
        # Bootstraps
        self.n_bootstraps = ROCAnalysis.n_bootstraps
        if options.bootstraps is not None:
            self.n_bootstraps = options.bootstraps

    def g_run(self,cmd):
        self.g.runCommand(cmd)

    def add_new_random_absences(self, source_map, presence_map):
        N = ( start_sites_N + (self.g.count_sites(presence_map) * \
                    multiplier_N) ) - self.g.count_sites(temp_vect_name)
        if N < 1:
            return
        self.log.debug("Adding %d random absences." % N)
        # find random points
        self.g_run("r.random --o input=%s vector_output=%s n=%d" %
            (source_map, temp_vect_name_new, N) )
        # set random points to have 0 value
        self.g_run("v.db.update map=%s column=value value=0" %
            temp_vect_name_new)
        # add column for distance
        self.g_run("v.db.addcol map=%s columns=\"dist double precision\"" %
            temp_vect_name_new)
        # join with existing random absences
        self.g_run("g.rename vect=%s,xxxxxxxxxx" % temp_vect_name )
        self.g_run("v.patch -e input=xxxxxxxxxx,%s output=%s" % 
            (temp_vect_name_new, temp_vect_name) )
        self.g_run("g.remove vect=xxxxxxxxxx")
        # remove any random points that are within certain distance of an actual
        # presence
        self.g_run("g.remove vect=%s" % temp_vect_name_new)
        self.g_run("v.distance from=%s to=%s upload=dist column=dist" %
                (temp_vect_name, presence_map) )
        self.g_run("v.extract input=%s output=%s where=\"dist>%d\"" %
                ( temp_vect_name, temp_vect_name_new, absence_min_dist ) )
        self.g_run("g.remove vect=%s" % temp_vect_name)
        self.g_run("g.rename vect=%s,%s" % (temp_vect_name_new,temp_vect_name) )

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

    def run_stats_across_models(self, models, t, class_map):
        self.g_run("r.mask " + class_map)
        cmd = "r.stats -1N input=" + class_map
        #header=[]
        absences=[]
        presences=[]
        for m in models:
            m_period = m["period"]
            if m_period[0] <= t and \
                    m_period[1] >=t:
                #header.append(m["name"])
                cmd += "," + m["base_map_name"] + repr(t) + "_prob" + \
                    "@" + m["mapset"] 
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
                if fields[0] != "*" and int(fields[0]) != 0 and \
                        models[j-1]["period"][0] > int(fields[0]):
                    fields[j] = None
            if fields[0] != "*" and int(fields[0]) > 0:
                # presences records contain year
                presences.append(fields[1:])
            elif fields[0] is "0":
                absences.append(fields[1:])
            # ignore sites NOT in the presence/absence map fields[0]="*"
        g_run("r.mask -r")
        return (presences, absences)

    def calculate_thresholded_areas(self,models,t,thresholds):
        g_run("r.mask " + self.area_mask)
        cmd = "r.stats -1N input=" + self.area_mask
        areas=[]
        #header_index=[]
        for m in models:
            m_period = m["period"]
            #header_index.append(m)
            if m_period[0] <= t and \
                    m_period[1] >=t:
                areas.append([0]*len(thresholds))
                cmd += ',' + m["base_map_name"] + repr(t) + "_prob" + \
                    "@" + m["mapset"] 
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
        max_potential_cells = float(get_cell_counts(self.area_mask))
        for i in range(0,len(areas)):
            areas[i] = [x / max_potential_cells for x in areas[i]]
        # remove mask
        g_run("r.mask -r")
        return areas

    def calc_pred_numbers(self, presences, absences, threshold):
        """
            format is
            [ [pred_model_1_site_1, pred_model_2_site_1, ... ]
              [pred_model_1_site_2, pred_model_2_site_2, ... ]
            ...
            ]
        """
        true_positives = array([0.0]*len(presences[0]))
        false_negatives = array([0.0]*len(presences[0]))
        true_negatives = []
        false_positives = [] 
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
        
        >>> sort_roc_points( [ [1995, 0.25, 0.5], [1996, 0.125, 0.5] ])
        [[1996, 0.125, 0.5], [1995, 0.25, 0.5]]
        """
        s.sort(key=lambda x:(x[1],x[self.roc_xaxis]))
        return s

    def process_roc_points(s):
        """ intersperse points of s with points that will make ROC 
            be a pessimistic graph.
        """
        s = sort_roc_points(s)
        s_pessimistic = []
        last_point = (0,0) # x,y order
        # note, s is in year, y, x order
        for row in s:
            if row[self.roc_xaxis] > last_point[0]:
                s_pessimistic.append( (row[0], last_point[1], row[2], row[3] ) )
            s_pessimistic.append( row )
            last_point = (row[self.roc_xaxis], row[1])
        return s_pessimistic

    def plot_and_save_rocs(S, basename="roc_", specificity_range=(0,1)):
        for t in S:
            linestyles = []
            headers=[]
            for m in mdef.models:
                if m["period"][0] <= t and m["period"][1] >= t:
                    linestyles.append(m["linestyle"])
                    headers.append(m["name"])
            f=figure()
            plot_roc(S[t],S_labels=headers,specificity_range=specificity_range,
                linestyles=linestyles,plot_null=True)
            title("Model ROC comparison for " + repr(t))
            f.savefig(basename+repr(t)+".png")
            close(f)

    def plot_roc(S, S_labels=[], scatter=False, \
            specificity_range=(0,1), linestyles=None, plot_null=False):
        """ Plot roc for single year
            S is array/list of triples (sensitivity, 1-specificity, area),
            one for each model
        """
        if specificity_range[0] > 0 or \
            specificity_range[1] < 1.0:  
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
            s_label += " (AUC " + str(round(calc_auc(s,specificity_range), 4)) + ")"
            if scatter:
                scatter([x[self.roc_xaxis] for x in s],[x[1] for x in s],label=s_label)
            else:
                s = process_roc_points(s)
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

    def plot_yearly_roc(r_S, index):
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

    def calc_auc_across_models(S,specificity_range=(0,1.0),method="pessimistic"):
        auc = []
        for s in S:
            a = calc_auc(s,specificity_range,method)
            auc.append(a)
        return auc

    def calc_auc(s,specificity_range=(0,1.0),method="pessimistic"):
        x_range = [1-x for x in specificity_range]
        x_range.reverse()
        assert(x_range[1] - x_range[0] > 0) 
        total_area=0.0
        s = sort_roc_points(s)
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

    def make_yearly_sites_maps(orig_name, self.start_time, self.end_time):
        #if self.start_time not in self.yearly_vectors:
        #    self.yearly_vectors[self.start_time] = {}
        # make yearly vector maps
        for t in range(self.start_time,self.end_time+1):
            self.yearly_vectors[t] = temp_yearly_basename + repr(t)
            g_run("v.extract --q input=" + orig_name + " output=" +
                    self.yearly_vectors[t] + " where=\"year>=" + repr(self.start_time)
                    + " and year<=" + repr(t) + "\"")
    def run(self):
        self.make_yearly_sites_maps(self.sites_vector, self.start_time, \
                self.end_time)
        self.reps=replicate_roc_calc(self.n_bootstraps)
        aucs=[]
        inv_x_range = (0.5,1.0) # High specificity, gets reversed in graphs etc.
        counter=0
        for r in reps:
            print "===============PLOTTING ROCS================"
            plot_and_save_rocs(r,"r" + repr(counter) + "roc_", \
                    inv_x_range)
            counter+=1
            print "===============CALC AUCs=================="
            auc=[]
            for t in r:
                auc.append([t] + calc_auc_across_models(r[t],inv_x_range))
            print "===============PLOT AUCs=================="
            figure()
            #for m_index in range(1,len(r[r.keys()[0]])+1):
            plot([x[0] for x in auc],
                [list(array(x)[1:]) for x in auc])
            show()
            aucs.append(auc)
            # plot 3d ROC
            #plot_3d_ROC(r_S)
            # volume under curve
            #vuc = calc_VUC(r_S)
        # TODO calculate average, s.d.

        # remove all temp maps:
        for t in self.yearly_vectors:
            g_run("g.remove vect=" + self.yearly_vectors[t])

        return (reps, aucs)


    def replicate_roc_calc(replications=1):
        reps = []
        for r in range(0,replications):
            r_S=calculate_roc_S()
            reps.append(r_S)
        return reps

    def compare_establishment_maps_with_roc(maps,sites_map):
        #### warning: not set up to calculate random absences.
        # i.e. it will only use area as x axis
        temp_file = "x_______compare_est_prob_w_sites_map"
        
        #### Calculate each maps prediction for each site
        g_run("v.to.rast input=" + sites_map + " output=" + \
                temp_file + " use=val")
        g_run("r.mask " + temp_file)
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
        g_run("r.mask -r")

        #### Calculate the total area for each map at each threshold
        thresholds = frange(-0.01,1.0,0.01)
        g_run("r.mask " + self.area_mask)
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
        max_potential_cells = float(get_cell_counts(self.area_mask))
        for i in range(0,len(areas)):
            areas[i] = [x / max_potential_cells for x in areas[i]]
        # remove mask
        g_run("r.mask -r")
        g_run("g.remove rast=" + temp_file)

        ####
        # init result S
        S = []
        for m in maps:
            S.append([])
        for t_index in range(0,len(thresholds)):
            threshold = thresholds[t_index]
            preds = calc_pred_numbers(presences, [], threshold)
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
        g_run( "r.random input=" + self.area_mask + 
            " vector_output=" + temp_vect_name + " n=1000" )
        # set random points to have 0 value
        g_run("v.db.update map=" + temp_vect_name + " column=value value=0")
        g_run("v.db.addcol map=%s columns=\"dist double precision\"" %
           temp_vect_name)
        for t in range(self.start_time,self.end_time+1):
            # make new random absences with r.random
            # (filtered by suitability > 0) and output vector map
            add_new_random_absences(self.area_mask, self.yearly_vectors[t])
            merge_sites(self.yearly_vectors[t],temp_vect_name,temp_vect_name_new)
            # convert joined vector to rast
            g_run("v.to.rast --o input=" + temp_vect_name_new +
                    " output=" + temp_rast_name + " column=year use=attr")

            (presences, absences) = \
                run_stats_across_models(mdef.models,t,temp_rast_name)
            thresholds = frange(-0.01,1.0,0.01)
            areas = calculate_thresholded_areas(mdef.models,t,thresholds)
            
            # init result S
            S = []
            for m_index in range(0,len(mdef.models)):
                S.append([])
            for t_index in range(0,len(thresholds)):
                threshold = thresholds[t_index]
                preds = calc_pred_numbers(presences, absences, threshold)
                # calculate sensitivity
                sensitivity = preds[0] / (preds[0]+preds[3])
                # calculate specificity
                specificity = preds[2] / (preds[2]+preds[1])
                # make area list for this threshold across models
                area = []
                for m in mdef.models:
                    if m["period"][0] <= t and m["period"][1] >= t:
                        area.append(areas[mdef.models.index(m)][t_index])
                val = zip([threshold]*len(sensitivity), sensitivity, 1-specificity,
                        area)
                for i in range(0,len(mdef.models)):
                    assert len(val[i]) == 4
                    S[i].append(val[i])
            r_S[t] = S

            if (save_to_star):
                # Dump predictions so we can put them into StAR web interface:
                # http://protein.bio.puc.cl/cardex/servers/roc/roc_analysis.php
                save_to_star_format("r" + repr(r) + "_" + star_output_base_name,
                        mdef.models, presences, absences, t)

        # remove temp maps
        g_run("g.remove vect=" + temp_vect_name)
        g_run("g.remove vect=" + temp_vect_name_new)
        g_run("g.remove rast=" + temp_rast_name)

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




