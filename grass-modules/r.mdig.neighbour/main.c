/****************************************************************************
 *
 * MODULE:       r.mdig.neighbour
 * AUTHOR(S):    Joel Pitt
 * PURPOSE:      Spreads present cells to neighbours. 
 *
 * COPYRIGHT:    2004 Bioprotection Centre, Lincoln University
 *
 *               This program is free software under the GNU General Public
 *   	    	 License (>=v2). Read the file COPYING that comes with GRASS
 *   	    	 for details.
 *
 *****************************************************************************/


#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "grass/gis.h"

#include "is_present.h"

int nrows, ncols;
void* inrast;

int is_boolean;

unsigned int num_spread_cells;
unsigned int radius, diameter, shape;
double spread_proportion;
int check_zero = -1;

// Defines the smallest fractional individual
// count to spread - to prevent entire map filling with zeros.
// TODO: Make small_limit an commandline option
double small_limit = 0.001;

void c_calc(CELL* x, CELL** out, int col)
{
	CELL c;
	CELL *out_row = NULL;
	unsigned int i, j;
	unsigned int individuals;
	unsigned int mean_individuals;
	unsigned int extra_individuals;
	int position;
	
	c = ((CELL *) x)[col];
	
	if (is_boolean)
	{
		mean_individuals = 1;
		c = 1;
		individuals	= 0;
	}
	else
	{
		// How to spread c individuals?
		// Try and do it evenly, but some will no doubt get
		// more than others since we are dealing with integers.
		// Alternative - for the moment extra_individuals
		// will be assigned to center cell
		individuals = c * spread_proportion;
		c -= individuals;
		mean_individuals = individuals / num_spread_cells;
		extra_individuals = individuals % num_spread_cells;
	}
	
	if (mean_individuals)
	{
		
	/* Traverse through the neighbourhood */
	for (i=0; i < diameter; i++ )
	{
		for (j=0; j < diameter; j++)
		{
			/* If relevent bit in the shape integer is set then
			 * spread there */
			if (shape & 1 << ( (i * diameter) + j ) )
			{
				position = col - radius + j;
				
				/* Check we are not outside the boundary of the region */
				if ((position >= 0 ) &&
					(position < ncols ))
				{
					out_row = ((CELL *) out[i]);
					/* Boolean spread or cumulative? */
					if (is_boolean)
						out_row[position] = (CELL) 1;
					else
						if (G_is_c_null_value(out_row + position))
							out_row[position] = mean_individuals;
						else
							out_row[position] += mean_individuals;
				}
			}
			
		}
	}
	out_row = ((CELL *) out[ (diameter / 2 )]);
	position = col;
	
	if (is_boolean)
		out_row[position] = (CELL) 1;
	else
		if (G_is_c_null_value(out_row + position))
			out_row[position] = c + extra_individuals;
		else
			out_row[position] += c + extra_individuals;
	}
	else
	{
		out_row = ((CELL *) out[ (diameter / 2 )]);
		position = col;
		
		if (is_boolean)
			out_row[position] = (CELL) 1;
		else
			if (G_is_c_null_value(out_row + position))
				out_row[position] = c + individuals;
			else
				out_row[position] += c + individuals;
	}
	
}

void d_calc(void* x, DCELL** out, int col)
{
	DCELL d;
	DCELL *out_row = NULL;
	unsigned int i, j;
	int position;
	double mean_individuals;
	double individuals;
	
	d = ((DCELL *) inrast)[col];

	if (is_boolean)
	{
		mean_individuals = 1.0;
		d = 1.0;
		individuals	= 0.0;
	}
	else
	{
		individuals = d * spread_proportion;
		d -= individuals;
		mean_individuals = individuals / num_spread_cells;
	}
	
	if (mean_individuals > small_limit)
	{
		/* Traverse through the neighbourhood */
		for (i=0; i < diameter; i++ )
		{
			for (j=0; j < diameter; j++)
			{
				/* If relevent bit in the shape integer is set then
				 * spread there */
				if (shape & 1 << ( (i * diameter) + j ) )
				{
					position = col - radius + j;
					/* Check we are not outside the boundary of the region */
					if ((position >= 0 ) &&
						(position < ncols ))
					{
						out_row = ((DCELL *) out[i]);
						/* Boolean spread or cumulative? */
						if (is_boolean)
							out_row[position] = 1.0;
						else
							if (G_is_d_null_value(out_row + position))
								out_row[position] = mean_individuals;
							else
								out_row[position] += mean_individuals;
							
					}
				}
				
			}
		}
		
		position = col;
		if ((position >= 0 ) &&	(position < ncols ))
		{
			out_row = ((DCELL *) out[(diameter/2)]);
			if (is_boolean)
				out_row[position] = 1.0;
			else
				if (G_is_d_null_value(out_row + position))
					out_row[position] = d;
				else
					out_row[position] += d;
		}
	} else 
	{
		position = col;
		out_row = ((DCELL *) out[(diameter/2)]);
		
		if (G_is_d_null_value(out_row + position))
			out_row[position] = (d + individuals);
		else
			out_row[position] += (d + individuals);

	}
}

void f_calc(FCELL* x, FCELL** out, int col)
{
	FCELL f;
	FCELL *out_row = NULL;
	unsigned int i, j;
	int position;
	float mean_individuals;
	float individuals;
	
	f = ((FCELL *) x)[col];
	
	individuals = f * spread_proportion;
	f -= individuals;
	mean_individuals = individuals / num_spread_cells;

	if (mean_individuals > small_limit)
	{
	
		/* Traverse through the neighbourhood */
		for (i=0; i < diameter; i++ )
		{
			for (j=0; j < diameter; j++)
			{
				/* If relevent bit in the shape integer is set then
				 * spread there */
				if (shape & 1 << ( (i * diameter) + j ) )
				{
					int position = col - radius + j;
					/* Check we are not outside the boundary of the region */
					if ((position >= 0 ) &&
						(position < ncols ))
					{
						out_row = ((FCELL *) out[i]);
						/* Boolean spread or cumulative? */
						if (is_boolean)
							out_row[position] = 1.0f;
						else
							if (G_is_f_null_value(out_row + position))
								out_row[position] = mean_individuals;
							else
								out_row[position] += mean_individuals;
					
					}
				}
				
			}
		}
		position = col;
		out_row = ((FCELL *) out[diameter / 2]);
		if (G_is_f_null_value(out_row + position))
			out_row[position] = f;
		else
			out_row[position] += f;
		
	} else {
		position = col;
		out_row = ((FCELL *) out[diameter / 2]);
		if (G_is_f_null_value(out_row + position))
			out_row[position] = f + individuals;
		else
			out_row[position] += f + individuals;
	}
	
	
}

int get_spread_squares(int diameter, int shape)
{
	int i, j;
	int count = 0;
	
	/* Traverse through the neighbourhood */
	for (i=0; i < diameter; i++ )
	{
		for (j=0; j < diameter; j++)
		{
			/* If relevent bit in the shape integer is set then
			 * spread there */
			if (shape & 1 << ( (i * diameter) + j ) )
				count++;
		}
	}
	return count;
}

int
main(int argc, char *argv[])
{
	struct Cell_head cellhd;
	char *name, *result, *mapset;
	//void *inrast;
	
	char *out_mapset;
	void **outrast;
	
	char rname[256], rmapset[256];
    char buff[1024];
	int is_reclass;
	int (*is_present)(void*, int) = NULL;
		
	int row,col;
	int infd, outfd;
	int i;
	
	RASTER_MAP_TYPE data_type;
	struct GModule *module;
	struct Option *input, *output, *n_radius, *n_shape, *n_proportion;
	struct Flag *f_bool, *f_overwrite, *f_check_zero;

	G_gisinit(argv[0]);

	module = G_define_module();
	module->description =
		"Spread to neighbouring cells";
					        
	/* Define the different options */

	input = G_define_option() ;
	input->key        = "input";
	input->type       = TYPE_STRING;
	input->required   = YES;
	input->gisprompt  = "old,cell,raster" ;
	input->description= "Name of an input layer" ;

	output = G_define_option() ;
	output->key        = "output";
	output->type       = TYPE_STRING;
	output->required   = YES;
	output->gisprompt  = "cell,raster" ;
	output->description= "Name of an output layer";

	n_radius = G_define_option() ;
	n_radius->key        = "radius";
	n_radius->type       = TYPE_INTEGER;
	n_radius->required   = NO;
	n_radius->answer     = "1";
	n_radius->options    = "0-2";
	n_radius->description= "Size of local neighbourhood";
	
	n_shape = G_define_option() ;
	n_shape->key        = "shape";
	n_shape->type       = TYPE_INTEGER;
	n_shape->required   = NO;
	n_shape->answer     = "186";
	n_shape->description= "Shape of local neighbourhood";
	
	n_proportion = G_define_option() ;
	n_proportion->key        = "proportion";
	n_proportion->type       = TYPE_DOUBLE;
	n_proportion->required   = NO;
	n_proportion->answer     = "1.0";
	n_proportion->description= "Proportion of individuals to spread between cells.";
	
	/* Define the different flags */
	
	f_bool = G_define_flag() ;
	f_bool->key         = 'b' ;
	f_bool->description = "Boolean spread, cells are present/absent";
	f_bool->answer      = FALSE;
	
	f_overwrite = G_define_flag();
	f_overwrite->key    = 'o' ;
	f_overwrite->description = "Overwrite output file if it exists";
	f_overwrite->answer = FALSE;
	
	f_check_zero = G_define_flag();
	f_check_zero->key    = 'z' ;
	f_check_zero->description = "Explicitly check and ignore cell values that are zero.";
	f_check_zero->answer = FALSE;
	
	if (G_parser(argc, argv))
		exit (-1);
		
	name    = input->answer;
	result  = output->answer;
	radius  = atoi(n_radius->answer);
	diameter= (radius * 2) + 1;
	shape   = atoi(n_shape->answer);
	spread_proportion = atof(n_proportion->answer);
	is_boolean = (f_bool->answer);
	if (f_overwrite->answer) check_zero=1;

	/* find map in mapset */
	mapset = G_find_cell2 (name, "");
        if (mapset == NULL)
                G_fatal_error ("cell file [%s] not found", name);

        if (G_legal_filename (result) < 0)
                G_fatal_error ("[%s] is an illegal name", result);

	/* determine the inputmap type (CELL/FCELL/DCELL) */
	data_type = G_raster_map_type(name, mapset);

	if ( (infd = G_open_cell_old (name, mapset)) < 0)
		G_fatal_error ("Cannot open cell file [%s]", name);

	if (G_get_cellhd (name, mapset, &cellhd) < 0)
		G_fatal_error ("Cannot read file header of [%s]", name);

	/* Allocate input buffer */
	inrast = G_allocate_raster_buf(data_type);
	
	/* Allocate output buffer, using input map data_type */
	nrows = G_window_rows();
	ncols = G_window_cols();
	outrast = G_malloc((int) (sizeof(void*) * (diameter + 1))); // +1 to use when swapping rows.
	
	is_reclass = (G_is_reclass (name, mapset, rname, rmapset) > 0);
    sprintf(buff, "cell_misc/%s", name);
    // If check_zero is -1 then it hasn't been set through a command-line option
    if (check_zero == -1 && (!G_find_file(buff, "null", mapset) || is_reclass))
	    check_zero=1;
	else
	    check_zero=0;
	
	for (i=0; i < diameter; i++)
	{
		outrast[i]=G_allocate_raster_buf(data_type);
		G_set_null_value(outrast[i],ncols,data_type);
	}
	outrast[diameter] = NULL;
		
	/* Open output file */

	/* Check for existing map and remove if overwrite flag is on */
	out_mapset = G_find_cell2 (result, mapset);
	if ( out_mapset != NULL )
	{
		if (f_overwrite->answer == TRUE)
		{
			char buffer[512];
			sprintf(buffer, "g.remove rast=%s > /dev/null", result);
			system(buffer);
			
		} else {
			G_fatal_error ("Output map <%s> exists (use -o flag to force"
			" overwrite)",result);
		}
	}
	if ( (outfd = G_open_raster_new (result, data_type)) < 0)
			G_fatal_error ("Couldn't create new raster <%s>",result);
	
	num_spread_cells = get_spread_squares(diameter, shape);
	
	is_present = IS_PRESENT(data_type,check_zero);
	
	for (row = 0; row < nrows; row++)
	{
		G_percent (row, nrows, 2);
		
		/* read input map */
		if (G_get_raster_row (infd, inrast, row, data_type) < 0)
			G_fatal_error ("Could not read from <%s>",name);
		
		switch (data_type)
		{
		case CELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (is_present(inrast,col))
					c_calc((CELL *)inrast,(CELL **)outrast,col);
			}
			break;
					
		case FCELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (is_present(inrast,col))
					f_calc((FCELL *)inrast,(FCELL **)outrast,col);
			}
			break;
					
		case DCELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (is_present(inrast,col))
					d_calc((DCELL*)inrast,(DCELL **)outrast,col);
			}
			break;
				
		}	
			
		/* Once the output buffer row is no longer needed... */
		if (row > (radius - 1))
		{
			if (G_put_raster_row (outfd, outrast[0], data_type) < 0)
				G_fatal_error ("Cannot write to <%s>",result);
		}
		
		G_set_null_value(outrast[0],ncols,data_type);
		
		outrast[diameter] = outrast[0];
		
		for ( i=0; i < (diameter-1); i++)
		{
			outrast[i] = outrast[i+1];
		}
		outrast[diameter-1] = outrast[diameter];
		
	}
	for ( i=0; i < radius; i++)
	{
		if (G_put_raster_row (outfd, outrast[i], data_type) < 0)
			G_fatal_error ("Cannot write to <%s>",result);
	}
	
/* DIsabled because glibc throws a spaz	
	G_free(inrast);
	for ( i=0; i <= diameter; i++)
	{
		G_free(outrast[i]);
	}
	G_free(outrast);*/
	
	
	G_close_cell (infd);
	G_close_cell (outfd);

	return 0;
}
