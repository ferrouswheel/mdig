/*
 *  Copyright 2004      Bioprotection Centre, Lincoln University
 *  Copyright 2006,2008 Joel Pitt, Fruition Technology
 *
 *  This file is part of Modular Dispersal In GIS.
 *
 *  Modular Dispersal In GIS is free software: you can redistribute it and/or
 *  modify it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or (at your
 *  option) any later version.
 *
 *  Modular Dispersal In GIS is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
 *  Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License along
 *  with Modular Dispersal In GIS.  If not, see <http://www.gnu.org/licenses/>.
 */

/* Various streamlined functions for checking the presence of a cell,
 * depending on whether a null bitmap exists and what the raster cell
 * type is
 * */


#define ___IS_PRESENT(x,y) is_present_##x##_##y
#define __IS_PRESENT(x,y) (x == FCELL_TYPE ? ___IS_PRESENT(FCELL,y) : ___IS_PRESENT(DCELL,y) )
#define _IS_PRESENT(x,y) (x == CELL_TYPE ? ___IS_PRESENT(CELL,y) : __IS_PRESENT(x,y) )
#define IS_PRESENT(x,y) (y == 1 ? _IS_PRESENT(x,nonull) : _IS_PRESENT(x,null) )

int is_present_CELL_null(void* inrast, int col);
int is_present_CELL_nonull(void* inrast, int col);
int is_present_FCELL_null(void* inrast, int col);
int is_present_FCELL_nonull(void* inrast, int col);
int is_present_DCELL_null(void* inrast, int col);
int is_present_DCELL_nonull(void* inrast, int col);
