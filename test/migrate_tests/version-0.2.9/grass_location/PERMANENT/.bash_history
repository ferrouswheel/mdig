g.list
g.region -p
g.region --help
g.region n=20 s=-20 e=20 w=-20 res=2
g.region save="test_region"
g.mapset --help
g.mapset -c test_named_region
mkdir test/grass_location/test_named_region/mdig
cp test/grass_location/variables/mdig/model.xml test/grass_location/test_named_region/mdig/.
vim test/grass_location/variables/mdig/model.xml
r.mapcalc initial_map="if(rand(100)<20,1,null())"
r.mapcalc initial_map="if(rand(0,100)<20,1,null())"
d.mon x0
d.rast initial_map
r.mapcalc spread_map="if(rand(0,100)<20,4,null())"
g.mapset PERMANENT
r.mapcalc spread_map2="if(rand(0,100)<20,4,null())"
r.mdig.kernel --help
r.mdig.kernel --help
man make
gcc --version
g.list
g.list rast
g.mapsets -p
g.mapsets -l
g.mapset variables
g.list rast
