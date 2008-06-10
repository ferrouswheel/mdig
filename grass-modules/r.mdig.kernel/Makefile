MODULE_TOPDIR = ../../..

PGM = r.mdig.kernel

LIBES = -L/mingw/GnuWin32/lib/ $(DISPLAYLIB) $(RASTERLIB) $(GISLIB) -lm -lgsl -lgslcblas
DEPENDENCIES = $(DISPLAYDEP) $(RASTERDEP) $(GISDEP)

include $(MODULE_TOPDIR)/include/Make/Module.make

all: default

default: cmd
