MODULE_TOPDIR = ../../..

PGM = r.mdig.kernel
#ifneq (,$(findstring mingw,$(ARCH)))
ifeq ($(findstring mingw,$(shell gcc --version)), mingw)
	LIBES = -L/mingw/GnuWin32/lib/ $(DISPLAYLIB) $(RASTERLIB) $(GISLIB) -lm -lgsl
else
	LIBES = $(DISPLAYLIB) $(RASTERLIB) $(GISLIB) -lm -lgsl -lgslcblas
endif
DEPENDENCIES = $(DISPLAYDEP) $(RASTERDEP) $(GISDEP)

include $(MODULE_TOPDIR)/include/Make/Module.make

all: default

default: cmd
