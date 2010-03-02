#!/bin/bash

# to run from the test GRASS location "test/grass_location"
r.mapcalc "kernel_test=if(row()==10&col()==10,2,null())"

# check minimum distance
r.mdig.kernel input=kernel_test output=test d_b=5 freq=20 -o min=4
r.distance maps=kernel_test2,test --quiet | awk -F: '{if ($1 == 2 && $2 == 1) if  ($3 < 4) print "fail"; else print "pass"}'

g.remove rast=kernel_test
g.remove rast=test
