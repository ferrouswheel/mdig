# MDiG - Modular Dispersal in GIS

## Requirements

- [**GRASS 6.4RC5**](http://grass.itc.it/download/index.php) or later, hasn't been tested with the new GRASS 7.0.
  In particular, we recommend an SVN snapshot as RC5 has an annoying
  g.region issue that can be confusing for new users.
- [**GDAL 1.6.0**](http://trac.osgeo.org/gdal/wiki/DownloadingGdalBinaries) or later (earlier versions have bugs)
  Although it is a GRASS requirement instead of a direct MDiG one, stuff can
  break if you have earlier buggy versions.

- ImageMagick's convert utility (imagemagick)
- [lxml](http://codespeak.net/lxml/) and its dependency, the [Gnome XML library](http://xmlsoft.org/)
- GNU Scientific Library (libgsl, libgsl0-dev) http://www.gnu.org/software/gsl/

    sudo apt-get install \
       gsl-bin libgsl0-dev bc libxml2 libxml2-dev python-lxml python-imaging-tk \
       python-scipy python-matplotlib python-numpy python-configobj python-paste \
       python-simplejson imagemagick

- Python dependencies 

    pip install -r requirements.txt

## Compile modules

Change into MDiG's grass-module dir

    cd mdig/grass-modules

and run:

    export GRASS_SRC=~/src/grass63_release
    make -S MODULE_TOPDIR=$GRASS_SRC
    cd $GRASS_SRC
    make install

## Feature requests

These are the requests that I've had for MDiG to support:

* [PRIORITY] Keep track of area treated by management strategies.

