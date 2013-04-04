# mdig - Modular Dispersal in GIS

mdig is simulation framework designed for people modelling dispersal processes.
In particular the focus in the past has been around modelling **invasive**
species. For example, I have used it to [model the spread of Argentine ant in New
Zealand, and compare it to the actual invasion dynamics][1].

It has also been used to [model Buddleia daviddi][2] spread in New Zealand.

mdig consists of two parts:

* The simulation manager - reads a dispersal model (in XML) and works out
  what to do. It is smart enough to:
   * manage the running of many replications, which are important if your simulation
     is stochastic;
   * aggregate results;
   * run analysis across the aggregate maps or the individual replicates;
* The GRASS dispersal modules - these take an input distribution map, some
  parameters, and output a new distribution map. See `grass-modules/README` for
  more details.

## Setup

### Setup GRASS

Ideally you'd just go:

    sudo apt-get install grass grass-dev

But due to this bug: http://trac.osgeo.org/grass/ticket/800 the ubuntu release
is broken. You'll need to build latest GRASS 6 development branch manually,
until the fix for this bug propagates into Ubuntu. While there are full details
on the GRASS GIS website, if you use Ubuntu 12.04 you should be able to get
away with:

    # Get the source code for grass 6.4.3 (development)
    sudo apt-get install subversion
    svn checkout https://svn.osgeo.org/grass/grass/branches/develbranch_6 grass6_devel
    cd grass6_devel/

    # Get the dependencies
    sudo apt-get install build-essential zlib1g-dev libreadline6-dev \
      flex bison libncurses5-dev proj libgdal-dev gdal-bin \
      tcl8.4-dev tk8.4-dev freeglut3-dev ffmpeg libpq-dev libavcodec-dev \
      libjpeg-dev libtiff-dev libpng12-dev postgresql libpq-dev libstdc++6 \
      libdap-dev libgeos-dev libmysqlclient-dev libspatialite-dev \
      libdapserver7 libgif-dev libsvn1 libjasper-dev gdal-bin uuid-dev \
      libxerces-c2-dev libhdf5-serial-dev libgdal-dev libdb4.8 \
      libproj-dev python-opengl unixodbc-dev fftw-dev lesstif2-dev libfreetype6-dev \
      sqlite3 libsqlite3-dev libavcodec-dev libavformat-dev make g++ swig libxmu-dev \
      python-dev libavutil-dev libavutil50 libswscale-dev libwxgtk2.8-dev libcairo-dev \
      python-wxversion

    # Configure
    CHOST="x86_64-pc-linux-gnu" CFLAGS="-march=k8 -O2 -pipe -Wall" \
    ./configure \
         --with-tcltk-includes=/usr/include/tcl8.4 \
         --with-motif --with-motif-includes=/usr/include/X11 \
         --with-readline --with-cxx --with-odbc --with-sqlite \
         --with-freetype --with-freetype-includes=/usr/include/freetype2 \
         --without-postgres --with-proj-share=/usr/share/proj \
         --with-ffmpeg \
         --with-ffmpeg-includes="/usr/include/libavcodec /usr/include/libavformat /usr/include/libavutil /usr/include/libswscale" \
         --with-wxwidgets --with-cairo --with-geos \
         --with-python --with-postgres --with-postgres-includes=/usr/include/postgresql/ \
         --enable-64bit 2>&1 | tee config_log.txt

    # Build and install
    make -j4 
    sudo make install

### Setup mdig simulation manager

    sudo apt-get install libxml2 libxml2-dev gsl-bin libgsl0-dev imagemagick bc

    # Numpy and scipy are potentially finicky, so safest to install them separate
    # and in order:
    mkvirtualenv mdig
    pip install numpy
    pip install scipy
    # Rest of python dependencies should be fine, ensure you are in mdig root dir
    pip install -r requirements.txt

That's the core mdig simulation manager, but to install the custom GRASS
modules:

    cd grass-modules
    sudo make MODULE_TOPDIR=/usr/lib/grass64

Or if you installed GRASS from source, you can do something like:

    export GRASS_SRC=~/src/grass64_release
    make -S MODULE_TOPDIR=$GRASS_SRC
    cd $GRASS_SRC
    make install

## Troubleshooting

Older versions of requirements have some bugs to be aware of:

* GRASS 6.4RC5 has an annoying g.region issue that can be confusing for new users.
* GRASS 6.4.2 (default in Ubuntu 12.04) has a broken r.reclass that segfaults with
  long map names.
* GDAL &lt;1.6.0 or later, earlier versions can run into segfaults.

## Testing

If you wish to run the unit tests for MDiG while developing code, then go to
the mdig program directory ('mdig/' from the root of the source) and run:

    nosetests -v

Or to run with code coverage analysis:

    nosetests -v --with-coverage

You'll run a bunch of tests to check everything's working correctly.

Note - currently only basic tests are run, more rigorous tests are needed
(although this has been greatly improved over the last year):

* Additional model files that more thoroughly test the potential model types.
* More coverage in unit tests for components within MDiG.
* Comparison of the output maps from various models versus what the expected map
  should look like. For modules, create before and after maps and make sure they
  have no difference,implement as a shell script to be run within GRASS.

## References

[1]: http://dx.doi.org/10.1890/08-1777.1       "Predicting Argentine ant spread over the heterogeneous landscape using a spatially explicit stochastic model"
[1]: http://dx.doi.org/10.1016/j.ecolmodel.2011.03.023      "Temporal limits to simulating the future spread pattern of invasive species: Buddleja davidii in Europe and New Zealand"
