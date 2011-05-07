# Script to run dispersal curve fitting multiple times with noise on the input sites

import dextractor.Occurrences as docc
reload(docc)
import dextractor.DispersalFit as DispersalFit
reload(DispersalFit)
from scipy import stats

reps=100

occ = docc.Occurrences('/home/joel/GBIF_buddleja_eur.csv',columns={'x':2,'y':3,'year':5,'precision':4},latlong=True)
occ.noise=True
df_eu = DispersalFit.DispersalFit(occ)
quartile_point = []
for i in range(0,reps):
    print "===== rep %d =====" % i
    ans = df_eu.fit_kernel(min_distance=0,p0=[9,10],max_distance=1000)
    quartile_point.append(stats.cauchy.ppf(0.75,scale=ans[0][0]))

# details:
# using max_distance=1000km
#
# United Kingdom: 3073 sites before removing dupes, 366 unique sites after.
# scale parameter 22.85km
#
# All: 6519 sites before removing dupes, 1438 unique sites after.
# scale parameter 9.8km +- 0.004 km (100 reps)
