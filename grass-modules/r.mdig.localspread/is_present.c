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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "grass/gis.h"

#include "is_present.h"

/* Various streamlined functions for checking the presence of a cell,
 * depending on whether a null bitmap exists and what the raster cell
 * type is
 * */

int is_present_CELL_null(void* inrast, int col)
{
	char present = FALSE;
	if (!G_is_null_value(inrast + (col*sizeof(CELL)), CELL_TYPE))
		present = TRUE;
	return present;
}
int is_present_CELL_nonull(void* inrast, int col)
{
	char present = FALSE;
	if (!G_is_null_value(inrast + (col*sizeof(CELL)), CELL_TYPE) &&
		((CELL *) inrast)[col] != 0 )
		present = TRUE;
	return present;
}
int is_present_FCELL_null(void* inrast, int col)
{
	char present = FALSE;
	if (!G_is_null_value(inrast + (col*sizeof(FCELL)), FCELL_TYPE ))
		present = TRUE;
	return present;
}
int is_present_FCELL_nonull(void* inrast, int col)
{
	char present = FALSE;
	if (!G_is_null_value(inrast + (col*sizeof(FCELL)), FCELL_TYPE ) &&
		((FCELL *) inrast)[col] != 0.0f )
		present = TRUE;
	return present;
}
int is_present_DCELL_null(void* inrast, int col)
{
	char present = FALSE;
	if (!G_is_null_value(inrast + (col*sizeof(DCELL)), DCELL_TYPE))
		present = TRUE;
	return present;
}
int is_present_DCELL_nonull(void* inrast, int col)
{
	char present = FALSE;
	if (!G_is_null_value(inrast + (col*sizeof(DCELL)), DCELL_TYPE) &&
		((DCELL *) inrast)[col] != 0.0 )
		present = TRUE;
	return present;
}

