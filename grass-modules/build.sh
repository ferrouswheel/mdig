#!/bin/bash
set -e
GRASS_SRC=$1
if [ ! -d "$GRASS_SRC" ]; then
    echo "Please specify correct GRASS source/build directory"
    exit 1
fi
make -S MODULE_TOPDIR=$GRASS_SRC
cd $GRASS_SRC
sudo make install
cd -
