rem -----------------------------------------------------------------------------------------------------------------------
rem Self Contained MDiG and GRASS Automated Packager for Windows
rem based off of GRASS-Packager.bat from GRASS src
rem -----------------------------------------------------------------------------------------------------------------------
rem Edited by: Marco Pasetti
rem Revised for OSGeo4W by: Colin Nielsen, Helmut Kudrnovsky, and Martin Landa
rem Last Update: $Id: GRASS-Packager.bat 40818 2010-02-04 09:36:07Z hamish $
rem -----------------------------------------------------------------------------------------------------------------------

@echo off

rem --------------------------------------------------------------------------------------------------------------------------
rem Set the script variables
rem --------------------------------------------------------------------------------------------------------------------------

set PACKAGE_DIR=.\mdig-0.3.2-w-GRASS-6.4.0svn-package

set OSGEO4W_DIR=c:\osgeo4w

set GRASS_PREFIX=%OSGEO4W_DIR%\apps\grass\grass-6.4.0svn

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Remove the previous Selected Package and create a new PACKAGE_DIR
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

if exist %PACKAGE_DIR% rmdir /S/Q %PACKAGE_DIR%
mkdir %PACKAGE_DIR%

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy %GRASS_PREFIX% content to PACKAGE_DIR
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

xcopy %GRASS_PREFIX% %PACKAGE_DIR% /S/V/F

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy Extralibs to PACKAGE_DIR\extralib
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

mkdir %PACKAGE_DIR%\extralib

copy %OSGEO4W_DIR%\bin\*.dll %PACKAGE_DIR%\extralib
del %PACKAGE_DIR%\extralib\libgrass_*6.4.0RC6*.dll
del %PACKAGE_DIR%\extralib\libgrass_*6.5*.dll
del %PACKAGE_DIR%\extralib\libgrass_*7.0*.dll
del %PACKAGE_DIR%\extralib\Qt*4.dll
rem copy %OSGEO4W_DIR%\pgsql\lib\libpq.dll %PACKAGE_DIR%\extralib

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy Extrabins to PACKAGE_DIR\extrabin
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

mkdir %PACKAGE_DIR%\extrabin

copy %OSGEO4W_DIR%\bin\*.exe %PACKAGE_DIR%\extrabin
del %PACKAGE_DIR%\extrabin\svn*.exe

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy SQLite content to PACKAGE_DIR\sqlite
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

mkdir %PACKAGE_DIR%\sqlite
mkdir %PACKAGE_DIR%\sqlite\bin
mkdir %PACKAGE_DIR%\sqlite\include
mkdir %PACKAGE_DIR%\sqlite\lib

xcopy %OSGEO4W_DIR%\bin\sqlite3.dll %PACKAGE_DIR%\sqlite\bin /S/V/F/I
copy %OSGEO4W_DIR%\include\btree.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\fts1*.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\hash.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\keywordhash.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\opcodes.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\os.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\os_common.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\pager.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\parse.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\sqlite*.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\vdbe.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\include\vdbeInt.h %PACKAGE_DIR%\sqlite\include
copy %OSGEO4W_DIR%\lib\sqlite3_i.lib %PACKAGE_DIR%\sqlite\lib

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy GPSBABEL executable and dll to PACKAGE_DIR\gpsbabel
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

mkdir %PACKAGE_DIR%\gpsbabel

copy %OSGEO4W_DIR%\gpsbabel.exe %PACKAGE_DIR%\gpsbabel
rem copy %OSGEO4W_DIR%\libexpat.dll %PACKAGE_DIR%\gpsbabel

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy shared PROJ.4 files to PACKAGE_DIR\proj
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

xcopy %OSGEO4W_DIR%\share\proj %PACKAGE_DIR%\proj /S/V/F/I

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy Tcl/Tk content to PACKAGE_DIR\tcl-tk
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

mkdir %PACKAGE_DIR%\tcl-tk
mkdir %PACKAGE_DIR%\tcl-tk\bin
mkdir %PACKAGE_DIR%\tcl-tk\include
mkdir %PACKAGE_DIR%\tcl-tk\lib
mkdir %PACKAGE_DIR%\tcl-tk\lib\tcl8.5
mkdir %PACKAGE_DIR%\tcl-tk\lib\tk8.5

xcopy %OSGEO4W_DIR%\bin\tclpip85.dll %PACKAGE_DIR%\tcl-tk\bin /S/V/F/I
xcopy %OSGEO4W_DIR%\bin\tcl85.dll %PACKAGE_DIR%\tcl-tk\bin /S/V/F/I
xcopy %OSGEO4W_DIR%\bin\tclsh.exe %PACKAGE_DIR%\tcl-tk\bin /S/V/F/I
xcopy %OSGEO4W_DIR%\bin\tclsh85.exe %PACKAGE_DIR%\tcl-tk\bin /S/V/F/I
xcopy %OSGEO4W_DIR%\bin\tk85.dll %PACKAGE_DIR%\tcl-tk\bin /S/V/F/I
xcopy %OSGEO4W_DIR%\bin\wish.exe %PACKAGE_DIR%\tcl-tk\bin /S/V/F/I
xcopy %OSGEO4W_DIR%\bin\wish85.exe %PACKAGE_DIR%\tcl-tk\bin /S/V/F/I

copy %OSGEO4W_DIR%\include\tcl*.h %PACKAGE_DIR%\tcl-tk\include
copy %OSGEO4W_DIR%\include\tk*.h %PACKAGE_DIR%\tcl-tk\include
copy %OSGEO4W_DIR%\include\tommath_class.h %PACKAGE_DIR%\tcl-tk\include
copy %OSGEO4W_DIR%\include\tommath_superclass.h %PACKAGE_DIR%\tcl-tk\include
copy %OSGEO4W_DIR%\include\ttkDecls.h %PACKAGE_DIR%\tcl-tk\include

copy %OSGEO4W_DIR%\lib\tcl8.5\*.tcl %PACKAGE_DIR%\tcl-tk\lib\tcl8.5
copy %OSGEO4W_DIR%\lib\tcl8.5\tclIndex %PACKAGE_DIR%\tcl-tk\lib\tcl8.5

copy %OSGEO4W_DIR%\lib\tk8.5\*.tcl %PACKAGE_DIR%\tcl-tk\lib\tk8.5
copy %OSGEO4W_DIR%\lib\tk8.5\tclIndex %PACKAGE_DIR%\tcl-tk\lib\tk8.5

xcopy %OSGEO4W_DIR%\lib\tk8.5\ttk %PACKAGE_DIR%\tcl-tk\lib\tk8.5\ttk /S/V/F/I

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy MSYS files to PACKAGE_DIR\msys
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

mkdir %PACKAGE_DIR%\msys

copy %OSGEO4W_DIR%\apps\msys\* %PACKAGE_DIR%\msys

xcopy %OSGEO4W_DIR%\apps\msys\bin %PACKAGE_DIR%\msys\bin /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\msys\doc %PACKAGE_DIR%\msys\doc /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\msys\etc %PACKAGE_DIR%\msys\etc /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\msys\info %PACKAGE_DIR%\msys\info /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\msys\lib %PACKAGE_DIR%\msys\lib /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\msys\man %PACKAGE_DIR%\msys\man /S/V/F/I
del %PACKAGE_DIR%\msys\etc\fstab
rem delete msys.bat from osgeo4w because there is an adaption (for spaces in installation path) written by GRASS-Installer.nsi
del %PACKAGE_DIR%\msys\msys.bat


set PYVER=Python26
@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy Python content to PACKAGE_DIR\%PYVER%
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

mkdir %PACKAGE_DIR%\%PYVER%

copy %OSGEO4W_DIR%\apps\%PYVER%\* %PACKAGE_DIR%\%PYVER%

xcopy %OSGEO4W_DIR%\apps\%PYVER%\DLLs %PACKAGE_DIR%\%PYVER%\DLLs /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\%PYVER%\include %PACKAGE_DIR%\%PYVER%\include /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\%PYVER%\Lib %PACKAGE_DIR%\%PYVER%\Lib /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\%PYVER%\libs %PACKAGE_DIR%\%PYVER%\libs /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\%PYVER%\Scripts %PACKAGE_DIR%\%PYVER%\Scripts /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\%PYVER%\Scripts %PACKAGE_DIR%\%PYVER%\tcl /S/V/F/I
xcopy %OSGEO4W_DIR%\apps\%PYVER%\Scripts %PACKAGE_DIR%\%PYVER%\Tools /S/V/F/I

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Copy MDiG to PACKAGE_DIR\mdig
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.

xcopy %OSGEO4W_DIR%\apps\mdig %PACKAGE_DIR%\mdig /S/V/F/I/E

@echo.
@echo -----------------------------------------------------------------------------------------------------------------------
@echo Packaging Completed
@echo -----------------------------------------------------------------------------------------------------------------------
@echo.
