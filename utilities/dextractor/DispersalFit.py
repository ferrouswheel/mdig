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


from scipy import *
from scipy import optimize
from scipy import stats
from pylab import *
from numpy import *
from numpy.linalg import *
#from LinearAlgebra import *
import pdb

cauchy_pdf = lambda p,x: [stats.cauchy.pdf(i,scale=p[0]) for i in x]
cauchy_cdf = lambda p,x: [stats.cauchy.cdf(i,scale=p[0]) for i in x]
cauchy_errfunc = lambda p,x,y: cauchy_pdf(p,x)-y
cauchy_dist = (cauchy_pdf, cauchy_cdf, cauchy_errfunc)

expon_pdf = lambda p,x: [stats.expon.pdf(i,scale=p[0]) for i in x]
expon_cdf = lambda p,x: [stats.expon.cdf(i,scale=p[0]) for i in x]
expon_errfunc = lambda p,x,y: expon_pdf(p,x)-y
expon_dist = (expon_pdf, expon_cdf, expon_errfunc)

weibull_pdf = lambda p,x: [stats.weibull_min.pdf(i,p[1],scale=p[0]) for i in x]
weibull_cdf = lambda p,x: [stats.weibull_min.cdf(i,p[1],scale=p[0]) for i in x]
weibull_errfunc = lambda p,x,y: weib_pdf(p,x)-y
weibull_dist = (weibull_pdf, weibull_cdf, weibull_errfunc)

class DispersalFit:

    def _my_formatter(self, x, pos):
        exponent=0
        if x == 0.0:
            return repr(x)
        if abs(x) < 0.01:
            while abs(x) < 0.1:
                exponent-=1
                x = x * 10.0
        elif abs(x) > 1000:
            while abs(x) > 10:
                exponent+=1
                x = x / 10.0
        if exponent:
            return '%.2fe%d'%(x,exponent)
        else:
            return '%.2f'%(x)

    def __init__(self, occurrences):
        # Site data to infer parameters from
        self.occurrences = occurrences
        # Mean of Poisson distribution generating events
        self.poisson_mean = None
        # Distribution to fit to distances
        self.distribution = cauchy_dist
        # Array for distribution parameters
        self.param = None
        self.kernel_p = None 
        self.verbose = True
        self.fit_info = None
        self.range = None

    def fit(self):
        """ Carry out all fits to occurrence data """
        if self.verbose:
            print "Fitting parameters to data ",
            if (self.occurrences.filename):
                print "from file " + self.occurrences.filename,
            print ""
        self.fit_poisson()
        self.fit_kernel()

    def fit_poisson(self):
        """ Work out the average number of new sites generated 
            each year per existing sites. Also weighted by existing sites.
        """
        if self.verbose:
            print "Finding Poisson mean... ",
        sum = 0
        n = 0
        for f in self.occurrences.get_freqs_per_existing():
            # f[0] is the total existing sites
            # f[1] is the frequency since the last.
            sum += f[0] * f[1]
            n += f[0]

        self.poisson_mean = float(sum) / n
        if self.verbose:
            print repr(self.poisson_mean)
        return self.poisson_mean 

    def _solve_poisson_root(self,existing,new_total,years):
        """
        When the there are more than one year between frequency counts
        we need to solve the polynomial of degree == num years
        """
        cm = zeros((years,years),Float)
        for i in range(0,years-1):
            cm[i,i+1] = 1.0
        cm[years-1,0] = -( 1 - (new_total/existing) )
        cm[years-1,1] = -years
        cm[years-1,years-1] = 1
        return eigenvalues(cm)

# From truncated:
#        sp=subplot(2,1,2)
#        p,val,patches=hist(cut_data,bins=nBins,normed=True,align='center')
#        plot(val,fitfunc(p1[0],val),'r-')
        
#        sp.yaxis.set_major_formatter(formatter)
#        title("Truncated 95% lower distances",fontsize=12)
#        ylabel("Frequency")
#        xlim(xmin=0)

    def fit_kernel(self, p0=[10500,2], n_bins=0, min_distance=0,
            max_distance=None):
        """ Fit a probability distribution to a list of distances """
        # only Weibull uses p0[1] currently

        dist_pdf=self.distribution[0]
        dist_err=self.distribution[2]
        self.n_bins = n_bins
        self.fit_info=[]
        d = self.occurrences.get_distances()
        d = [x for x in d if x > min_distance]
        if max_distance is not None:
            d = [x for x in d if x < max_distance]
        else:
            max_distance = max(d)
        N = len(d)
        self.N = N
        if self.n_bins == 0:
            if N > 100:
                self.n_bins = N / 30
            else:
                self.n_bins = 10 
        if self.verbose:
            print "N = " + repr(N) + ", Number of bins = " + repr(self.n_bins)
            print "Binning data...",

        # plot histogram of distances without truncation
        p,orig_val=histogram(d,bins=self.n_bins,normed=True)
        if self.verbose:
            print "done."
        # calculate centres:
        val=[]
        for i in range(0,len(orig_val)-1):
            val.append((orig_val[i] + orig_val[i+1]) / 2.0)

        if self.verbose:
            print "Fitting distribution to data... ",
        p1=optimize.leastsq(dist_err, p0[:], args = (val,p), full_output=True)
        self.param = p1[0]
        if self.verbose:
            print "parameters are " + repr(p1[0])
        
        self.fit_info=[p1[0],self.calc_fit(N,p,orig_val)] 
        self.test_kernel_fit()
        return self.fit_info

    def calc_fit(self,N,p,edges):
        """ N is the total number of observations 
            p is the normalised histogram heights
            edges is the array of where the historgram edges are
        """
        # chi
        middle_of_edges=[]
        for i in range(0,len(edges)-1):
            middle_of_edges.append((edges[i] + edges[i+1]) / 2.0)

        observed=N*p*diff(edges)
        expected=N*diff(self.distribution[1](self.param,edges))
        return sum( (observed - expected)**2 / expected )

    def graph_fit(self,f_number,units="m",range_cutoff=None):
        if self.fit_info is None:
            print "run fit() first."
            return
        f = figure(f_number)
        title('Freq. distributions of dispersal distances')
        #f.text(.5, .95, 'Freq. distributions of dispersal distances', \
        #        horizontalalignment='center', fontsize=14)
        formatter = FuncFormatter(self._my_formatter)
        distances_to_graph = self.occurrences.get_distances()
        if (range_cutoff is not None):
            distances_to_graph = [x for x in distances_to_graph if \
                 x < range_cutoff[1] and x > range_cutoff[0]]
        p,val,patches=hist(distances_to_graph,bins=self.n_bins,normed=True,align='center',facecolor='none')
        plot(val,self.distribution[0](self.fit_info[0],val),'r-')
        gca().yaxis.set_major_formatter(formatter)
        ylabel("Frequency")
        xlim(xmin=0)
        xlabel("Distance (" + units + ")")
        text(0.7,0.85,"$s$ = %.3f" % self.fit_info[0][0],transform = gca().transAxes)
        #text(0.7,0.8,"$p$ = %.3f" % self.kernel_p,transform = gca().transAxes)
        #text(0.7,0.7,r'$\lambda = $' + "%.3f" % self.poisson_mean,transform = axes().transAxes)
        return f

    def test_kernel_fit(self):
        # return/print chi goodness of fit test
        print "Pearson Chi-Squared test with d.f. ",
        df =  self.n_bins - (len(self.param) + 1)
        print repr(df)
        print "Chi-Squared stat is " + repr(self.fit_info[1])
        chi_test = stats.chi2.cdf(self.fit_info[1],df)
        print "Chi-Squared CDF value " + repr(chi_test)
        print "p " + repr(1 - chi_test)
        print "(if p < 0.05 reject null hypothesis that data matches " \
            "fitted distribution)"
        self.kernel_p = 1 - chi_test

    def ks_test(self,range_cutoff=None,ks_label="",ks_line="-"):
        if self.fit_info is None:
            print "run fit() first."
            return
        D = self.occurrences.get_distances()
        if (range_cutoff is not None):
            D = [x for x in D if x < range_cutoff[1] and x > range_cutoff[0]]
        D.sort()
        X = []
        F = []
        for x in xrange(len(D)):
            X.append(float(x)/len(D))
        F.extend(self.distribution[1](self.param,D))
        X = array(X)
        F = array(F)
        # This transform is needed for pdfs that centre around 0.0
        F = (F - 0.5) * 2.0
        ks = max(abs(F-X))
        plot ((0,1),(0,1),color='0.5',linestyle=':',label="_nolegend_")
        plot (X,F,label=ks_label,color='0.0',linestyle=ks_line)
        xlabel("Data CDF")
        ylabel("Fitted Cauchy distribution CDF")
        title("P-P plot")
        print 'K-S Test =', ks

    def extractDispersal():
        data=loadData(filename,species) # returns data sorted by year
        dists,freqs = extractDistancesAndFrequency(data)
        # remember cut off sites, they could be important to the optimisation
        gamma,fitGoodness = fitDispersal(dist)
        l = fitFrequencies(freqs)
        optimised = false
        while not optimised:
            sites = generateSites()
            simDist,simFreq = extractDistancesAndFrequency(sites)
            simGamma,simFitGoodness = fitDispersal(dist)
            #if (simFitGoodness)

    def iterativeFit(iterations=0):
        # generate fake sites
        fake_sites = occurrences
        fake_sites.generate_sites(freq=self.poisson_mean, p=self.param)
        fake_sites.get_distances()
        fake_df = DispersalFit(fake_sites,_survival=false)
        fake_df.fit()
        fake_df.graph_fit()
        show()
        # compare distance distribution of fake sites to actual sites.
        return fake_df

