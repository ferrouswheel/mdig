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

import DispersalFit

import pdb
import csv
from scipy import *
import numpy
from pylab import *
import dateutil.parser
from pyproj import Proj

class Occurrences(object):

    # for calculating lat long distances
    EARTH_RADIUS = 6371; # earth radius in km

    # default delimiter to use when loading occurrences
    _delimiter="|"

    # default percentile is used by percentile and exponential
    # distance calculations
    _percentile = 20 
    # used by random and exponential distance calculations
    _sample_size = 100 

    # Columns with None are optional
    columns = { 'country':0, 'x':1, 'y':2, 'year':3, 'survival': None,
            'precision': None}

    def __init__ (self, filename=None, latlong=False, columns=None,
            limiter={}):
        """
        @filename is the file to load occurrences from
        @latlong is whether the x,y coordinates are latitude,longitude rather
        than easting/westing
        @columns a dictionary indicating the column numbers of inputs
        """
        self.delimiter=Occurrences._delimiter
        self.occurrences=[]
        self.distances = {}
        self.distances_type=None  
        self.latlong = latlong
        self.filename = filename 
        self.noise = False
        self.columns = Occurrences.columns
        if columns is not None:
            self.columns.update(columns)
        # Set this before calculating distances to scale by this factor
        self.scale_factor = 1
        if self.latlong:
            # this projection is for europe
            self.p = Proj('+proj=utm +zone=30U +ellps=WGS84 +units=m')
            self.scale_factor = .001
        if self.filename:
            self.load_file(self.filename,limiter=limiter,**self.columns)

    def dist_ll(lat1,lon1,lat2,lon2): 
        if lat1 == lat2 and lon1 == lon2:
            return 0
        val = (math.sin(lat1)*math.sin(lat2)) + \
              (math.cos(lat1)*math.cos(lat2) * \
              math.cos(lon2-lon1));
        if val > 1: val = 1
        elif val < -1: val = -1
        ret= math.acos(val) * Occurrences.EARTH_RADIUS
        #if ret and ret < 1:
        #    pdb.set_trace()
        return ret
    dist_ll = staticmethod(dist_ll)

    def dist_xy(x1,y1,x2,y2):
        return sqrt( ((x1-x2)*(x2-x2)) + ((y1-y2)*(y1-y2)) )
    dist_xy = staticmethod(dist_xy)

    def degrees_to_rad(x):
        return ((pi*x/180)+pi) % (2*pi)
    degrees_to_rad = staticmethod(degrees_to_rad)

    def load_file(self, _filename, header=True, limiter={}, x=1, y=2, year=3, survival=4,
            precision=5,country=1):
        """ load occurrence data from file, automatically filters sites
            with missing data.
        """
        self.filename = _filename
        reader = csv.reader(open(self.filename, "rb"), delimiter=self.delimiter)
        self.occurrences=[]
        for r in reader:
            if header:
                header = False
                continue
            easting=0
            northing=0
            year_value=0
            # extract location
            #if self.latlong:
                ## don't convert to radians anymore
                #if len(r[x]) > 0: easting = float(r[x]) # Occurrences.degrees_to_rad(float(r[x]))
                #if len(r[y]) > 0: northing = float(r[y]) # Occurrences.degrees_to_rad(float(r[y]))
            #else:
            skip_this_one = False
            for f in limiter:
                if f == 'country':
                    if limiter[f] != r[country]:
                        skip_this_one = True
                        break
            if skip_this_one: continue
            if len(r[x]) > 0: easting = float(r[x])
            if len(r[y]) > 0: northing = float(r[y])
            # extract year
            if len(r[year]) > 0:
                site_date = dateutil.parser.parse(r[year])
                year_value = site_date.year
            # extract survival
            survival_percent = 100;
            if survival is not None:
                if len(r[survival]) > 0:
                    survival_percent = float(r[survival])
                    # survival zero, and yet there is a site here?
                    # just make 1 to avoid divide by zero errors.
                    if survival_percent == 0: survival_percent = 100;
            # extract precision
            precision_value = 0
            if precision is not None:
                if len(r[precision]) > 0: precision_value = float(r[precision])

            if (easting or northing) and year_value:
                self.occurrences.append([year_value,easting,northing,survival,precision_value])
                # used to store in a dict...
                #if year in occurrences:
                #    occurrences[year].append([easting,northing])
                #else:
                #    occurrences[year] = [easting,northing]
        init_occ_count = len(self.occurrences)
        self.filter_duplicate_years()
        print repr(init_occ_count) + " sites before removing dupes, " + \
            repr(len(self.occurrences)) + " unique sites after."
        # return data  sorted by year
        self.occurrences.sort(key=lambda x: x[0])
        return self.occurrences

    def filter_duplicate_years(self):
        """ Remove subsequent occurrences that are at location of earlier
            sites. e.g. if 1,1 is a location first found in 1990, then remove
            occurrences that are at 1,1 in subsequent years.
        """
        self.occurrences.sort(key=lambda x: (x[1],x[2],x[3]))
        r=[self.occurrences[0]]
        for x in range(1,len(self.occurrences)):
            cur = self.occurrences[x]
            if r[-1][1] != cur[1] or r[-1][2] != cur[2]:
                r.append(cur)
        self.occurrences = r

    def save_occurrences(self, to_file):
        writer = csv.writer(open(to_file, "wb"),delimiter=self.delimiter)
        writer.writerows(self.occurrences)

    def get_site_distances(self):
        if not len(self.distances) or self.noise:
            self.calc_distances(self.calc_distance_nn)
        return self.distances

    def get_distances(self):
        d = self.get_site_distances()
        return [x for x in d if x]

    def add_noise(self,sites):
        result = []
        for s in sites:
            # what to do about sites with no precision info?
            if s[4] == 0: pass
            precision = 5000#s[4]
            r_x = numpy.random.uniform(-precision,precision)
            r_y = numpy.random.uniform(-precision,precision)
            temp_site = s[1],s[2]
            if self.latlong: temp_site = self.p(s[1],s[2])
            temp_site = temp_site[0] + r_x, temp_site[1] + r_y
            result.append((s[0],temp_site[0],temp_site[1],s[3],s[4]))
        return result

    def calc_distances(self,distance_method):
        print "Calc distances for " + repr(len(self.occurrences)) + " sites "
        self.distances = []
        self.distances_type = None
        # add jiggle to site position if required
        old_latlong = self.latlong
        if self.noise:
            print "adding noise"
            sites_temp = self.add_noise(self.occurrences)
            self.latlong=False
        else:
            sites_temp = self.occurrences
        # calculate distance to existing sites for each site
        for site in range(0,len(sites_temp)):
            if site % 100 == 0:
                print ".",
                sys.stdout.flush()
            d = distance_method(sites_temp,site)
            if d is not None:
                self.distances.append(d*self.scale_factor)
            else:
                self.distances.append(None)
        print ""
        self.latlong=old_latlong
        self.distances_type = distance_method.__doc__
        return self.distances

    def calc_all_distances(self,sites,index):
        """ Distances to all pre-existing """
        pos = sites[index][1:3]
        if self.latlong: pos = self.p(pos[0],pos[1])
        t = sites[index][0]
        dists = []
        for i in range(0,index):
            if sites[i][0] >= t:
                break
            if self.latlong:
                # now we use proj4
                xy = self.p(sites[i][1],sites[i][2])
                dist = Occurrences.dist_xy(pos[0],pos[1],xy[0],xy[1])
                #dist = Occurrences.dist_ll(pos[0],pos[1],sites[i][1],sites[i][2])
            else:
                dist = Occurrences.dist_xy(pos[0],pos[1],sites[i][1],sites[i][2])
            dists.append(dist)
        return dists

    def calc_distance_origin(self,sites,index):
        """ Distance from origin """
        pos = sites[index][0:2]
        if self.latlong: pos = self.p(pos[0],pos[1])
        t = sites[index][2]
        dist = inf
        arrival_year = sites[0][0]
        if t > arrival_year:
            for i in range(0,index):
                if sites[i][0] > arrival_year:
                    break
                if self.latlong:
                    # now we use proj4
                    xy = self.p(sites[i][1],sites[i][2])
                    dist = Occurrences.dist_xy(pos[0],pos[1],xy[0],xy[1]) / 1000.0
                else:
                    diff = Occurrences.dist_xy(pos[0],pos[1],sites[i][1],sites[i][2])
                if diff < dist:
                    dist = diff
        if dist is inf:
            return None
        else:
            return dist

    def calc_distance_nn(self,sites,index):
        """ Nearest Neighbour distance """
#        pos = sites[index][0:2]
#        t = sites[index][2]
        dist = self.calc_all_distances(sites,index)
        if dist:
            return min(dist)
        else:
            return None

    def calc_distance_mean(self,sites,index):
        """ Mean distance to all existing """
#        pos = sites[index][0:2]
#        t = sites[index][2]
        dists = self.calc_all_distances(sites,index)
        if dists:
            return mean(dists)
        else:
            return None

    def calc_distance_percentile(self,sites,index):
        """ percentile distance to all existing """
        dists = self.calc_all_distances(sites,index)
        if dists:
            sorted = sort(dists)
            score = stats.stats.scoreatpercentile(sorted,self.percentile)
            return score
        else:
            return None

    def calc_distance_rand(self,sites,index):
        """ select random distance to all existing """
        dists = self.calc_all_distances(sites,index)
        if dists:
            r_dists = []
            for i in range(0,self.sample_size):
                r_dists.append(dists[int(r.uniform(0,1)*len(dists))])
            return mean(r_dists)
        else:
            return None

    def calc_distance_exp(self,sites,index):
        """ select exponentially random distance to all existing """
        dists = self.calc_all_distances(sites,index)
        if dists:
            for i in range(0,self.sample_size):
                r_index = min(int(r.expovariate(1.0/(len(current)*0.2))),len(current)-1)
                r_dists.append(dists[r_index])
            return mean(r_dists)
        else:
            return None

    def get_freqs_per_existing(self, start_from=None):
        """ Returns an array of tuples (total sites, freq).
            The total sites are needed because calculation of Poisson
            mean needs to be weighted by the number of source sites
            used to create the yearly freq.
        """
        freqs = self.get_freqs()
        freq_per_existing = []
        total = 0
        start_i = 0

        if start_from:
            t = start_from - 1
            i = 0
            while i >= 0:
                total += freqs[i][1]
                if freqs[i+1][0] >= t:
                    t = freqs[i][0]
                    start_i = i+1
                    i=-1
                    continue
                i+=1
        if not start_i:
            t = freqs[0][0] 
            total = freqs[0][1]
            start_i = 1

        for i in freqs[start_i:]:
            years = i[0] - t
            #increase = i[1] - total
            #print years, i[1], total
            # This isn't the true mean ( I think we
            # want to find an inverse moment, but I don't know how )
            # It's good enough though
            freq_per_existing.append( (total, float(i[2]) / (total * years)) )
            #freq_per_existing.append( pow(float(i[1]) / total, 1.0/years)  )
            total += i[1]
            t = i[0]
        return freq_per_existing

    def get_freqs(self):
        t = self.occurrences[0][0]
        freqs = []
        count = 0
        scaled_count = 0

        for i in range(0,len(self.occurrences)):
            if self.occurrences[i][0] > t:
                freqs.append((t,count,scaled_count))
                t = self.occurrences[i][0] 
                count = 0
                scaled_count = 0
            if self.columns['survival'] is not None:
                scaled_count += 1/(self.occurrences[i][3]/100.0)
            else:
                scaled_count += 1
            count += 1
        freqs.append((t,count,scaled_count))
        return freqs

    def generate_sites(self,pdf_func = DispersalFit.cauchy_pdf, years=20, freq=0.5, p=[1000]):
        """ Generate a bunch of 2D sites by sampling the probability distribution
            of distances. """
        self.occurrences=[]
        self.distances = []
        self.distances_type = None
        self.occurrences = [(0,0,0)]
        print "Generating sites ",
        for i in range(0,years):
            print ".",
            sys.stdout.flush()
            end_j = len(self.occurrences)
            for j in range(0,end_j):
                for k in range(0,stats.poisson.rvs(freq)):
                    dist = stats.cauchy.rvs(scale=p[0])
                    angle = stats.uniform.rvs(0,2*pi)
                    x = self.occurrences[j][0] + (dist * sin(angle))
                    y = self.occurrences[j][1] + (dist * cos(angle))
                    self.occurrences.append((x,y,i))
        print ""
        return self.occurrences

