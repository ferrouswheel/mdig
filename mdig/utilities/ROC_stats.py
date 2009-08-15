#### graph the AUCs ####

# calculate the first date with non-zero
times = (mean(array(aucs),0)[:,0])
data = (mean(array(aucs),0)[:,1:])
start_index = []
for col in data.T:
    row_index = -1
    for i in range(0,len(col)):
        if i is not NaN and col[i] > 0:
            row_index = i
            break
    start_index.append(row_index)

# first graph reps
lines = []
for m_index in range(0,len(start_index)):
    for rep_index in range(0,size(array(aucs)[:,:,m_index+1],0)):
        si = start_index[m_index]
        a_line = plot(array(aucs)[rep_index,si:,0],array(aucs)[rep_index,si:,m_index+1])
        lines.extend(a_line)
for l in lines:
    l.set_color("0.3")
    l.set_alpha(0.2)

## one can skip plotting reps, and just plot means
f=figure()
ax1=subplot(311)
null_model_auc=0.125
hlines(0.125,times[0],times[-1]+10,color='0.0',alpha=1.0,linewidth=0.5,linestyle=':')

# graph the mean
mean_styles=["-","--","-.",":","dashes"]
mean_lines=[]
for col_i in range(0,len(start_index)):
    print times[start_index[col_i]:]
    mean_lines.extend(plot(times[start_index[col_i]:],data.T[col_i][start_index[col_i]:],color='0.0',alpha='1.0'))
    if mean_styles[col_i] == "dashes":
        mean_lines[-1].set_linestyle("--")
        mean_lines[-1].set_dashes([3,1])
    else:
        mean_lines[-1].set_linestyle(mean_styles[col_i])

#xlabel("Year")
setp( ax1.get_xticklabels(), visible=False)
ylabel("Partial AUC")
xlim(1965,2010)
ylim(0,0.5)
legend(('1951','1968','1978','1988','1998'))
title("AUC for $\mathit{B. davidii}$ spread models with different starting years")

# graph the number of sites too
cd /home/joel/network/projects/beatingweeds/bdavidii/utilities
from dextractor import Occurrences
o = Occurrences.Occurrences("../bdavidii/bdavidii_sites_nz_w_est_prob.csv")
cd -
ax2a = subplot(312,sharex=ax1)
bar(array(o.get_freqs())[:,0],array(o.get_freqs())[:,1],width=1,color="1.0")
xlim(1965,2010)
ylabel("Number of sites")
ax2b = twinx()
cumcdf=[]
numyears = len(o.get_freqs())
for i in arange(numyears):
    cumcdf.append(sum(array(o.get_freqs())[0:i,1]))

plot(array(o.get_freqs())[:,0],cumcdf,color="0.0")
ylabel("Cumulative # of sites")
xlim(1965,2010)
xlabel("Year")

#########################
# Plot distribution of AUC values from resampling and then
# calculate t-test whether average pAUC is better than null model

# calculate average AUC through time
average_auc = []
# for each model
for m_index in range(0,len(start_index)):
    m_av_auc=[]
    # for each rep, calculate average AUC through time
    for rep_index in range(0,size(array(aucs)[:,:,m_index+1],0)):
        si = start_index[m_index]
        si = max(si,list(times).index(1972))
        m_av_auc.append(mean(array(aucs)[rep_index,si:,m_index+1]))
    average_auc.append(m_av_auc)

# plot as box and whiskers
ax3=subplot(313)
my_years = ('1951','1968','1978','1988','1998')
my_pos = (1966,1968,1978,1988,1998)
boxplot(average_auc,positions=my_pos,widths=1.5)
xticks(my_pos, my_years)
hlines(0.125,1965,2010,linestyle=":")
xlabel("Model")
ylabel("Mean of average pAUC through time")
boxplot_labels = ax3.get_xticklabels()
setp(boxplot_labels, rotation=45)
#title("Mean partial AUC through time")

# formatting
ax_left=0.1
ax_width=0.8
ax1.set_position([ax_left,0.55,ax_width,0.35])
ax2a.set_position([ax_left,0.40,ax_width,0.15])
ax2b.set_position([ax_left,0.40,ax_width,0.15])
ax2a.set_yticks(range(0,150,25))
ax2b.set_yticks(range(0,1400,200))
ax3.set_position([ax_left,0.08,ax_width,0.28])
show()

# work out the statistical likelihood that the AUC is significantly different
# from the null model
for aa in average_auc:
    scipy.stats.ttest_1samp(aa,null_model_auc)

#########################
# Make a graph for explaining the pAUC concept, and one to compare against.

x=frange(0.0,1.0,0.01)

# graph explaining peterson's AUC
figure()
subplot(211)
px=0.555; py=0.8
plot(x,1-(x-1)**2,color="0.0",linestyle="-")
fill_between(x,1-(x-1)**2,where=x>=px,color="0.9",linestyle=":")
plot((0,1),(0,1),color="0.0",linestyle=":")
fill_between(x,x,where=x>=px,color="0.8",linestyle=":")
hlines(py,0,px,linestyle="--")
vlines(px,0,py,linestyle="--")
text(0.7,0.83,"$\mathrm{AUC}_{\mathrm{1-E}}$")
text(0.7,0.4,"$\mathrm{AUC}_{\mathrm{null}}$")
yticks( (0,py,1), ("0","1-E","1.0"))
xticks( (0,px,1), ("","$x$","1.0"))
xlim(0,1)
ylim(0,1)
ylabel("Sensitivity")

#graph for partial AUC with high specificity
subplot(212)
px=0.5; py=0.747
#bar(0.5,1.0,0.5,fc="0.9",ec="0.8")
plot(x,1-(x-1)**2,color="0.0",linestyle="-")
fill_between(x,1-(x-1)**2,where=x<=px,color="0.9",linestyle=":")
plot((0,1),(0,1),color="0.0",linestyle=":")
fill_between(x,x,where=x<=px,color="0.8",linestyle=":")
hlines(py,0,px,linestyle="--")
vlines(px,0,py,linestyle="--")
text(0.3,0.4,"$\mathrm{AUC}_{\mathrm{A}}$")
text(0.3,0.1,"$\mathrm{AUC}_{\mathrm{null}}$")
yticks( (0,py,1), ("0","$y$","1.0"))
xticks( (0,px,1), ("","A","1.0"))
xlim(0,1)
ylim(0,1)
xlabel("Proportion of area")
ylabel("Sensitivity")

####
# Plot the pAUC roc for 2008

run occupancy_roc_auc.py
plot_roc(rocs[1][2008],('1951','1968','1978','1988','1998'),specificity_range=(0.5,1),plot_null=True,linestyles=mean_styles,dashes=[None,None,None,None,(3,1)])
title("ROC curve for year 2008 across different simulation start years")

