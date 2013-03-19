# mdig - Modular Dispersal in GIS

## Setup

    sudo apt-get install grass grass-dev
    sudo apt-get install libxml2 libxml2-dev gsl-bin libgsl0-dev imagemagick bc

    # Numpy and scipy are potentially finicky, so safest to install them separate
    # and in order:
    mkvirtualenv mdig
    pip install numpy
    pip install scipy
    # Rest of python dependencies should be fine, ensure you are in mdig root dir
    pip install -r requirements.txt

That's the core mdig simulation manager, but to install the custom GRASS
modules that are particularly useful for people modelling dispersal:

    cd grass-modules
    sudo make MODULE_TOPDIR=/usr/lib/grass64

Or if you installed GRASS from source, you can do something like:

    export GRASS_SRC=~/src/grass64_release
    make -S MODULE_TOPDIR=$GRASS_SRC
    cd $GRASS_SRC
    make install

## Feature requests

These are the requests that I've had for MDiG to support:

* [PRIORITY] Keep track of area treated by management strategies.

## Troubleshooting

Older versions of requirements have some bugs to be aware of:

* GRASS 6.4RC5 has an annoying g.region issue that can be confusing for new users.
* GDAL &lt;1.6.0 or later, earlier versions can run into segfaults.
