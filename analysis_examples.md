# Analysis examples

The analysis command allows you to run GRASS/shell commands across all your maps
and then aggregate the results. Since the syntax can be tricky, this file
documents some common use cases.

## Calculate area

To work out the area of simulations.

    ./mdig.py -f area -t # (not -c because this has to be per replicate)

    r.stats -c %0 | awk "BEGIN {notNULL = 0} /^[^*]/ {notNULL+=\$2} END {print notNULL}"

This can also be used to work out whether the population dies out, since you
can then just check for zero.
