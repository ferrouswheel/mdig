# This file contains a sequential list of instructions for recreating all the
# outputs needed for the homogeneous landscape B. daviddi model. Including:
# fits against occurrence data

import sys
sys.path.append("/home/joel/network/projects/beatingweeds/utilities")
from dextractor import Occurrences
from dextractor import DispersalFit

# data file for NZ occurrences:
nz_occ_file = "/home/joel/network/projects/beatingweeds/bdavidii/bdavidii_sites_nz_w_est_prob.csv"
eu_occ_file = "/home/joel/network/projects/beatingweeds/bdavidii/bdavidii_sites_europe_w_est_prob.csv" 

# _survival = False is important because this a the homogeneous
# landscape model
print "Loading occurrences"
nz_o = Occurrences.Occurrences(nz_occ_file,_survival=False)
europe_o = Occurrences.Occurrences(eu_occ_file,_latlong=True,_survival=False)
# make sure NZ is in km like EU
nz_o.scale_factor = 0.001

# Set up fit objects
df_nz_cauchy = DispersalFit.DispersalFit(nz_o)
df_eu_cauchy = DispersalFit.DispersalFit(europe_o)

# The following functions are to be run in the order;
# extract_parameters
# make_graphs
# --- then run some simulations in mdig
# analysis

def extract_parameters():
    df_nz_cauchy.fit_poisson()
    df_nz_cauchy.fit_kernel(min_distance=1,n_bins=30,max_distance=500)
    df_eu_cauchy.fit()


def make_graphs():
    # NZ freqs vs EU freqs
    figure()
    plot(array(europe_o.get_freqs())[1:,0],array(europe_o.get_freqs_per_existing())[:,1],color="blue",linestyle="solid")
    plot(array(nz_o.get_freqs())[1:,0],array(nz_o.get_freqs_per_existing())[:,1],color="green",linestyle="dashed")
    hlines(df_nz_cauchy.fit_poisson(),1920,2010,colors='green',linestyle='-.')
    hlines(df_eu_cauchy.fit_poisson(),1920,2010,colors='blue',linestyle='dotted')
    yscale('linear')
    yscale('log')
    xlim(1930,2010)
    xlabel("Year")
    ylabel("Frequency per existing sites")
#legend(("Europe","New Zealand"), loc="lower left")
    text(1931,df_nz_cauchy.poisson_mean * 1.2, "NZ")
    text(1931,df_eu_cauchy.poisson_mean * .7, "EU")
#title("Frequency of long distance dispersal events")
    savefig("freq_per_existing.png")

# PP plots
    figure()
    df_eu_cauchy.ks_test(range_cutoff=(0,100000),ks_line="-",ks_label="EU")
    df_nz_cauchy.ks_test(range_cutoff=(1,100000),ks_line="-.",ks_label="NZ")
    #grid()
    #legend(loc='lower right')
    savefig("pp-plot.png")

# distance distribution
    figure(2)
    subplot(211)
    # NZ kernel
    df_nz_cauchy.graph_fit(2,units="km",range_cutoff=(0.5,100))
    xlabel("")
    title("New Zealand")
    subplot(212)
    # EU kernel
    df_eu_cauchy.graph_fit(2,units="km",range_cutoff=(0,400))
    ylim(0,0.2)
    title("Europe")

    figure(2).text(0.5,0.95,"Probability distribution of nearest neighbour distances",horizontalalignment='center',size='large')

    figure(2).text(0.05,0.9,"a)")
    figure(2).text(0.05,0.48,"b)")
    show()
    savefig("distance_distribution.png")


def analysis():
    pass




