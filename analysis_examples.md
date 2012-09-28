# Analysis examples

The analysis command allows you to run GRASS/shell commands across all your maps
and then aggregate the results.

## Calculate area

To work area of simulations (also can be used to work out whether the population
dies out):

    ./mdig.py -f area -t # (not -c because this has to be per replicate)

    r.stats -c %0 | awk "BEGIN {notNULL = 0} /^[^*]/ {notNULL+=\$2} END {print notNULL}"

