/****************************************************************************
 *
 * MODULE:       r.mdig.stats
 * AUTHOR(S):    Joel Pitt
 * PURPOSE:      Find distances between present cells in two raster maps,
 * skewness of distance (and variance of skew).
 *
 * COPYRIGHT:    2004 Bioprotection Centre, Lincoln University
 *
 *               This program is free software under the GNU General Public
 *   	    	 License (>=v2). Read the file COPYING that comes with GRASS
 *   	    	 for details.
 *
 *****************************************************************************/

// For NAN define
#define _GNU_SOURCE

//#define DEBUG

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "grass/gis.h"

#include "is_present.h"

#define ARRAY_INC 1024

#ifdef DEBUG
	#define TILE_SIZE 6
#else
	#define TILE_SIZE 32
#endif
#define TILE_DEPTH_INC 128

void parse_options(int argc, char* argv[]);
int make_past_sites_list();
void calc_stats(char* name);
void add_distance(double d);
int init();

void moment(double data[], int n, double *ave, double *adev, double *sdev,
    double *var, double *skew, double *curt, double *max);

// Various option flags
int is_boolean, is_overwrite, is_verbose, is_summary;

// Whether we need to explicitly check for non-null zero cells
// which may happen if the null bitmap has been removed.
int past_check_zero = -1, present_check_zero = -1;

char *past, *present, *mask, *past_mapset, *present_mapset, *mask_mapset;
char *output, *output_mapset;

RASTER_MAP_TYPE past_datatype, present_datatype, mask_datatype;

int sites_count = 0, sites_max = 0;
int* sites_rows = NULL;
int* sites_cols = NULL;
void* sites_value;

double* distances = NULL;
int distances_count = 0, distances_max=0;

int*** tiles = NULL;
int** tile_sizes = NULL;
int** tile_max = NULL;
int tiles_rows = 0;
int tiles_cols = 0;

char** tiles_searched = NULL;

int
main(int argc, char *argv[])
{
		
	struct GModule *module;

	G_gisinit(argv[0]);

	module = G_define_module();
	module->description =
		"Output stats of present cells in two maps";

	parse_options(argc, argv);

	init();
	
	make_past_sites_list();
	if (sites_count == 0)
		G_fatal_error("No sites present in past raster");

	calc_stats(present);
	
	sites_count = 0;
	G_free(sites_cols);
	G_free(sites_rows);
	G_free(sites_value);
	
	return 0;
}

#ifdef DEBUG
void dump_tiles()
{
	int i,j;
	
	for (i=0; i < tiles_rows; i++)
	{
		for (j=0; j < tiles_cols; j++)
		{
			int k;
			fprintf(stderr,"r%dc%d: ",i,j);
			for (k=0; k < tile_sizes[i][j]; k++)
			{
				fprintf(stderr, "%d,%d; ", tiles[i][j][2*k], tiles[i][j][(2*k) + 1]);
			}
			fprintf(stderr,"\n");
		}
	}
	
}
#endif

int init()
{
    char rname[256], rmapset[256];
    char buff[1024];
    int is_reclass;
	
	/* find past map in mapset */
	past_mapset = G_find_cell2 (past, "");
    if (past_mapset == NULL)
        G_fatal_error ("cell file [%s] not found", past);
    /* find present map in mapset */
	present_mapset = G_find_cell2 (present, "");
    if (present_mapset == NULL)
        G_fatal_error ("cell file [%s] not found", present);

    /* find mask map in mapset */
    if (mask != NULL)
    {
    	mask_mapset = G_find_cell2 (mask, "");
	    if (mask_mapset == NULL)
     	   G_fatal_error ("cell file [%s] not found", mask);
    }
    
    past_check_zero=0;
    is_reclass = (G_is_reclass (past, past_mapset, rname, rmapset) > 0);
    sprintf(buff, "cell_misc/%s", past);
    if (past_check_zero==-1 && (!G_find_file(buff, "null", past_mapset) || is_reclass))
        past_check_zero=1;

	present_check_zero=0;
    is_reclass = (G_is_reclass (present, present_mapset, rname, rmapset) > 0);
    sprintf(buff, "cell_misc/%s", present);
    if (present_check_zero==-1 && (!G_find_file(buff, "null", present_mapset) || is_reclass))
	    present_check_zero=1;
    
    if (output != NULL)
    {
    	output_mapset = G_find_cell2 (output, G_mapset());
		if ( output_mapset != NULL )
		{
			if (is_overwrite == TRUE)
			{
				char buffer[512];
				sprintf(buffer, "g.remove rast=%s > /dev/null", output);
				system(buffer);
			
			} else {
				G_fatal_error ("Output map <%s> exists (use -o flag to force"
				" overwrite)",output);
			}
		}
	}
        
    /* determine the past inputmap type (CELL/FCELL/DCELL) */
	past_datatype = G_raster_map_type(past, past_mapset);
	
	/* (present) determine the present inputmap type (CELL/FCELL/DCELL) */
	present_datatype = G_raster_map_type(present, present_mapset);

	/* determine the mask inputmap type (CELL/FCELL/DCELL) */
	if (mask) mask_datatype = G_raster_map_type(mask, mask_mapset);

    return 0;
    
}

//void add_site(int row, int col)
//{
//	/* If we have run out of space for new jump events
//	 * then create some more
//	 */
//	if ((sites_count + 1) == sites_max || sites_cols == NULL)
//	{
//		int* tmp;
//		
//		sites_max += ARRAY_INC;
//		
//		tmp = sites_rows;
//		sites_rows = G_realloc(tmp, (unsigned int) sizeof(int) * sites_max);
//		
//		tmp = sites_cols;
//		sites_cols = G_realloc(tmp, (unsigned int) sizeof(int) * sites_max);
//		
//	}
//	
//	sites_cols[sites_count] = col;
//	sites_rows[sites_count] = row;
//	
//	sites_count++;
//}

void add_distance(double d)
{
	/* If we have run out of space for new jump events
	 * then create some more
	 */
	if ((distances_count + 1) ==  distances_max || distances == NULL)
	{
	
		distances_max += ARRAY_INC;
		
		distances = G_realloc(distances, (unsigned int) sizeof(double) * distances_max);
		
	}
	
	distances[distances_count] = d;
	distances_count++;
}

// Replaced by type and null existance specific functions in is_present.c
/*int is_present(void* inrast, int col, RASTER_MAP_TYPE data_type, int check_zero)
{
	char present = FALSE;
	// Have to check if null, but also whether the value is 0
	// This is due to uncertainty about how rasters without
	// null bitmap files are handled.
	switch (data_type) {
	case CELL_TYPE:
		if (!G_is_null_value(inrast + (col*sizeof(CELL)), data_type)
			((CELL *) inrast)[col] != 0 )
			present = TRUE;
		break;
	case FCELL_TYPE:
		if (!G_is_null_value(inrast + (col*sizeof(FCELL)), data_type) &&
			((FCELL *) inrast)[col] != 0.0f )
			present = TRUE;
		break;
	case DCELL_TYPE:
		if (!G_is_null_value(inrast + (col*sizeof(DCELL)), data_type) &&
			((DCELL *) inrast)[col] != 0.0 )
			present = TRUE;
		break;
	}
	
	return present;
}*/

int is_surrounded(void* inrast[4], int col, int ncols, RASTER_MAP_TYPE datatype, int check_zero)
{
	int i,j;

	switch (datatype) {
	case CELL_TYPE:
		if (check_zero) {
			for (i = col-1; i <= col+1; i++){
				if (i > 0 && i < ncols) {
					for (j=0; j < 3; j++) {
						if (!is_present_CELL_nonull(inrast[j], i)) return FALSE;
					}
				}
			}
		} else {
			for (i = col-1; i <= col+1; i++){
				if (i > 0 && i < ncols) {
					for (j=0; j < 3; j++) {
						if (!is_present_CELL_null(inrast[j], i)) return FALSE;
					}
				}
			}
		}
		break;
	case FCELL_TYPE:
		if (check_zero) {
			for (i = col-1; i <= col+1; i++){
				if (i > 0 && i < ncols) {
					for (j=0; j < 3; j++) {
						if (!is_present_FCELL_nonull(inrast[j], i)) return FALSE;			
					}
				}
			}
		} else {
			for (i = col-1; i <= col+1; i++){
				if (i > 0 && i < ncols) {
					for (j=0; j < 3; j++) {
						if (!is_present_FCELL_null(inrast[j], i)) return FALSE;			
					}
				}
			}
		}
		break;
	case DCELL_TYPE:
		if (check_zero) {
			for (i = col-1; i <= col+1; i++){
				if (i > 0 && i < ncols) {
					for (j=0; j < 3; j++) {
							if (!is_present_DCELL_nonull(inrast[j], i)) return FALSE;			
					}
				}
			}
		} else {
			for (i = col-1; i <= col+1; i++){
				if (i > 0 && i < ncols) {
					for (j=0; j < 3; j++) {
							if (!is_present_DCELL_null(inrast[j], i)) return FALSE;			
					}
				}
			}
		}
		break;
	}

	return TRUE;
	
}

void init_tiles(int rows, int cols)
{
	int i,j;
	tiles_rows = (rows / TILE_SIZE) + 1;
	tiles_cols = (cols / TILE_SIZE) + 1;

	tiles = malloc(tiles_rows * sizeof(int**));
	tile_sizes = malloc(tiles_rows * sizeof(int*));
	tile_max = malloc(tiles_rows * sizeof(int*));
	tiles_searched = malloc(tiles_rows * sizeof(char*));
	
	if (!tiles || !tile_sizes || !tile_max ||!tiles_searched)
	{
		fprintf(stderr, "Error allocating tiles\n");
		exit(2);
	}
		
	
	for (i=0; i < tiles_rows; i++)
	{
		
		tiles[i] = malloc(tiles_cols * sizeof(int*));
		tile_sizes[i] = malloc(tiles_cols * sizeof(int));
		tile_max[i] = malloc(tiles_cols * sizeof(int));
		tiles_searched[i] = malloc(tiles_cols * sizeof(char));

		if (!tiles[i] || !tile_sizes[i] || !tile_max[i] ||!tiles_searched[i])
		{
			fprintf(stderr, "Error allocating tiles\n");
			exit(2);
		}

				
		for (j=0; j < tiles_cols; j++)
		{
			tile_sizes[i][j] = 0;
			tiles_searched[i][j] = 0;			
			tile_max[i][j] = TILE_DEPTH_INC;
			tiles[i][j] = malloc(tile_max[i][j] * 2 * sizeof(int));
			
			if (!tiles[i][j])
			{
				fprintf(stderr, "Error allocating tiles\n");
				exit(2);
			}
		}
		
	}
	
	
	
}

void add_site(int row, int col)
{
	int index;
	int i, j;
	
	i = row / TILE_SIZE;
	j = col / TILE_SIZE;
	
	if (tile_sizes[i][j] >= tile_max[i][j])
	{
		int step;
		step = tile_max[i][j] / TILE_DEPTH_INC;
		step++;
		tile_max[i][j] = step * TILE_DEPTH_INC;
		tiles[i][j] = realloc(tiles[i][j], tile_max[i][j] * 2 * sizeof(double));
	}
	
	index = tile_sizes[i][j] * 2;
	tiles[i][j][index] = row;
	tiles[i][j][index+1] = col;
	
	tile_sizes[i][j]++;
	sites_count++;
}

int* find_closest_site_in_tile(int row, int col, int trow, int tcol)
{
	int i;
	double min_distance = HUGE_VAL;
	int dr, dc;
	double distance = 0.0;
	int* return_p = NULL;
	
	if (tiles_searched[trow][tcol])
		return NULL;
	
	for (i=0; i < tile_sizes[trow][tcol]; i++)
	{
		distance = 0.0;
									
		dr = row - tiles[trow][tcol][2*i];
		dc = col - tiles[trow][tcol][(2*i)+1];
		distance = (double) (dr * dr) + (dc * dc);
		if (distance < min_distance)
		{
			min_distance = distance;
			return_p = tiles[trow][tcol] + 2*i;
		}
		
	}
	
	tiles_searched[trow][tcol] = 1;
	return return_p;
}

int* find_closest_site_r (int row, int col, int trow, int tcol, int r)
{
	// r is the radius from trow and tcol to check.
	double min_distance = HUGE_VAL;
	int dr, dc;
	double distance = 0.0;
	int* return_p = NULL;
	
	int i,j;
	
	static int** sites = NULL;
	static int last_nsites = 0;
	int nsites;
	int scount = 0;

	if (r==0)
		nsites = 1;
	else
		nsites = ((2*r)+1)*((2*r)+1) - (((2*r)-1)*((2*r)-1));	

	if (last_nsites == 0)
	{
		sites = malloc(nsites * sizeof(int*));
		last_nsites = nsites;
	}
	else if (last_nsites < nsites)
	{
		sites = realloc(sites, nsites * sizeof(int*));
		last_nsites = nsites;
	}
	memset(sites, 0, sizeof(int*) * last_nsites);
		
	for (i=trow-r; i <= trow+r; i++)
	{
		j = tcol-r;
		if (i >= 0 && j >= 0 &&
			i < tiles_rows && j < tiles_cols)
		{
			sites[scount] = find_closest_site_in_tile(row, col, i, j);
			scount++;
		}
		
		j = tcol+r;
		if (i >= 0 && j >= 0 &&
			i < tiles_rows && j < tiles_cols)
		{
			sites[scount] = find_closest_site_in_tile(row, col, i, j);
			scount++;
		}
	}

	for (j=tcol-(r-1); j <= tcol+(r-1); j++)
	{
		i = trow-r;
		if (i >= 0 && j >= 0 &&
			i < tiles_rows && j < tiles_cols)
		{
			sites[scount] = find_closest_site_in_tile(row, col, i, j);
			scount++;
		}
		
		i = trow+r;
		if (i >= 0 && j >= 0 &&
			i < tiles_rows && j < tiles_cols)
		{
			sites[scount] = find_closest_site_in_tile(row, col, i, j);
			scount++;
		}
	}

	for (i=0; i < nsites; i++)
	{
		if (sites[i])
		{
			distance = 0.0;
										
			dr = row - *(sites[i]);
			dc = col - *(sites[i] + 1);
			distance = (double) (dr * dr) + (dc * dc);
			if (distance < min_distance)
			{
				min_distance = distance;
				return_p = sites[i];
			}
		}
		
	}
		
	//free(sites);
	return return_p;
	
}

int* find_closest_site_to(int row, int col) 
{
	int tr, tc, i, j;
	int *site = NULL;
	double site_distance = HUGE_VAL;
	int r = 0;
	
	for (i = 0; i < tiles_rows; i++)
	{
		for (j = 0; j < tiles_cols; j++)
		{
			tiles_searched[i][j] = 0;
		}
	}
	
	tr = row / TILE_SIZE;
	tc = col / TILE_SIZE;
	
	while (!site || r <= 1)
	{
		int *tmpsite;
		double distance = 0.0;
		int dr, dc;

		tmpsite = find_closest_site_r (row,col,tr,tc,r);
		
		if (tmpsite)
		{
			dr = row - tmpsite[0];
			dc = col - tmpsite[1];
			distance = (double) (dr * dr) + (dc * dc);
			if (site == NULL || distance < site_distance)
			{
				site = tmpsite;
				site_distance = distance;
			}
		}

		r++;
	}
	return site;
}


int make_past_sites_list()
{
	struct Cell_head past_cellhd;
	int nrows, ncols;
	int past_infd;
	int i;
	int (*is_present_ptr)(void*, int) = NULL;
		
	void* past_inrast[4];
	
	int row,col;

	// Open past map
	if ( (past_infd = G_open_cell_old (past, past_mapset)) < 0)
		G_fatal_error ("Cannot open cell file [%s]", past);

	if (G_get_cellhd (past, past_mapset, &past_cellhd) < 0)
		G_fatal_error ("Cannot read file header of [%s]", past);
		
	/* Allocate input buffers */
	for (i=0; i < 3; i++)
		past_inrast[i] = G_allocate_raster_buf(past_datatype);
	
	/* Get region size */
	nrows = G_window_rows();
	ncols = G_window_cols();
	
	init_tiles(nrows,ncols);
	
	// Fill buffers
	for (i=0; i < 3; i++)
	{
		if (G_get_raster_row (past_infd, past_inrast[i], i, past_datatype) < 0)
			G_fatal_error ("Could not read from <%s>",past);
	}
	
	is_present_ptr = IS_PRESENT(past_datatype, past_check_zero);
	
	// Process first row
	for (col=0; col < ncols; col++)
	{
		if (is_present_ptr(past_inrast[0], col))
		{
			add_site(0,col);
		}
	}

	// Process all apart from last
	for (row = 1; row < nrows-1; row++)
	{
		if (is_verbose) G_percent (row, 2 * nrows, 2);
		
		/* read input map */
		if (G_get_raster_row (past_infd, past_inrast[2], row+1, past_datatype) < 0)
			G_fatal_error ("Could not read from <%s>",past);
		
		/*process the data */
		for (col=0; col < ncols; col++)
		{
			if (is_present_ptr(past_inrast[1], col)
			&& !is_surrounded(past_inrast, col, ncols, past_datatype, past_check_zero))
			{
				add_site(row,col);
			}
		}
		
		past_inrast[3] = past_inrast[0];
		for ( i=0; i < 2; i++)
		{
			past_inrast[i] = past_inrast[i+1];
		}
		past_inrast[2] = past_inrast[3];
		past_inrast[3] = NULL;

	}
	
	// Process last row
	for (col=0; col < ncols; col++)
	{
		if (is_present_ptr(past_inrast[1], col))
		{
			add_site(nrows-1,col);
		}
	}
	
	G_close_cell (past_infd);

	G_free(past_inrast[0]);
	G_free(past_inrast[1]);
	G_free(past_inrast[2]);

	#ifdef DEBUG
	dump_tiles();
	#endif

	return sites_count;
}

void calc_stats(char* name)
{
	struct Cell_head cellhd, past_cellhd, mask_cellhd;
	
	int row,col;
	int infd, past_infd, mask_infd, outfd;
	void *inrast, *past_inrast, *mask_inrast, *outrast;
	int nrows, ncols;
	
	int (*is_p_cur)(void*, int), (*is_p_past)(void*, int),
		(*is_p_mask)(void*, int);
	
	double ave, adev, sdev, var, skew, curt, max;
	
	if ( (infd = G_open_cell_old (name, present_mapset)) < 0)
		G_fatal_error ("Cannot open cell file [%s]", name);

	if (G_get_cellhd (name, present_mapset, &cellhd) < 0)
		G_fatal_error ("Cannot read file header of [%s]", name);

	// Open past map
	if ( (past_infd = G_open_cell_old (past, past_mapset)) < 0)
		G_fatal_error ("Cannot open cell file [%s]", past);

	if (G_get_cellhd (past, past_mapset, &past_cellhd) < 0)
		G_fatal_error ("Cannot read file header of [%s]", past);
		
	// Open Mask
	if (mask)
	{
		if ( (mask_infd = G_open_cell_old (mask, mask_mapset)) < 0)
			G_fatal_error ("Cannot open cell file [%s]", mask);

		if (G_get_cellhd (mask, mask_mapset, &mask_cellhd) < 0)
			G_fatal_error ("Cannot read file header of [%s]", mask);
	}
	
	// Open output map
	if (output != NULL)
    {
		if ( (outfd = G_open_raster_new (output, DCELL_TYPE)) < 0)
			G_fatal_error ("Couldn't create new raster <%s>",output);
	    outrast = G_allocate_raster_buf(DCELL_TYPE);
    }

	/* Allocate input buffer */
	inrast = G_allocate_raster_buf(present_datatype);
	past_inrast = G_allocate_raster_buf(past_datatype);
	if (mask)
		mask_inrast = G_allocate_raster_buf(mask_datatype);
	
	/* Get region size */
	nrows = G_window_rows();
	ncols = G_window_cols();
	
	is_p_cur = IS_PRESENT(present_datatype, present_check_zero);
	is_p_past = IS_PRESENT(past_datatype, past_check_zero);
	is_p_mask = IS_PRESENT(mask_datatype, 0);
	
	for (row = 0; row < nrows; row++)
	{	
		if (is_verbose) G_percent (nrows + row, 2 * nrows, 2);
		
		/* read input map */
		if (G_get_raster_row (infd, inrast, row, present_datatype) < 0)
			G_fatal_error ("Could not read from <%s>",name);
			
		if (G_get_raster_row (past_infd, past_inrast, row, past_datatype) < 0)
			G_fatal_error ("Could not read from <%s>",past);
			
		if (mask && G_get_raster_row (mask_infd, mask_inrast, row, mask_datatype) < 0)
			G_fatal_error ("Could not read from <%s>",mask);
		
		
		/*process the data */
		for (col=0; col < ncols; col++)
		{
			if (is_p_cur(inrast, col)
			&& !is_p_past(past_inrast, col)
			&& (!mask || !is_p_mask(mask_inrast, col)))
			{
				double min_distance = HUGE_VAL;
				double mint;//r, minc, mint;
				int dr, dc;
				
				int* site = NULL;
				
				site = find_closest_site_to(row,col);
				
				//dr = row - site[i];
				//dc = col - site[i+1];
				dr = row - site[0];
				dc = col - site[1];
				
				min_distance = (double) (dr * dr) + (dc * dc);
				mint = atan2((double)dc, (double)dr);

				if (min_distance != 0.0)
				{
					//sumsqr += min_distance;
				
					min_distance = sqrt(min_distance);
					add_distance(min_distance);
					
					#ifdef DEBUG
					fprintf(stderr,"closest to %d,%d, is %d,%d at dist. %f\n",row,col,site[0],site[1],min_distance);
					#endif

					if (!is_summary)
						fprintf(stdout, "%.2f, %.4f\n", min_distance, mint);
	
					if (output != NULL)
						((DCELL*)outrast)[col] = (DCELL) min_distance;
					//sum += min_distance;
					//t_sum += mint; t_sumsqr += (mint * mint);
					
					//n++;
				}
				else if (output != NULL)
    			{
					G_set_null_value(((DCELL*) outrast)+col, 1, DCELL_TYPE);
    			}
			} else {
				if (output != NULL)
					G_set_null_value(((DCELL*) outrast)+col, 1, DCELL_TYPE);
			}
		}
		if (output)
			if (G_put_raster_row (outfd, outrast, DCELL_TYPE) < 0)
				G_fatal_error ("Cannot write to <%s>",output);

	}
	if (output) 
	{	
		G_close_cell (outfd);
		G_free(outrast);
	}
	G_close_cell (infd);
	G_free(inrast);
	
	moment(distances, distances_count, &ave, &adev, &sdev, &var, &skew, &curt, &max);
	
	if (!is_summary)
/*		fprintf(stderr, "\tmean,\tvariance\n"
			"Distance\t%f,%f\ntheta\t%f,%f\n",
			sum / n, (sumsqr - (sum*sum / n)) / (n - 1),
			t_sum / n, (t_sumsqr - (t_sum*t_sum / n)) / (n - 1));*/
		fprintf(stderr,"%f %f %f %f %f %f %f\n",ave, adev, sdev, var, skew, curt, max);
		
	else
		fprintf(stdout,"%f %f %f %f %f %f %f\n",ave, adev, sdev, var, skew, curt, max);
		/*fprintf(stdout,"%f %f %f %f\n", sum / n, (sumsqr - (sum*sum / n)) / (n - 1),
			t_sum / n, (t_sumsqr - (t_sum*t_sum / n)) / (n - 1));*/
	
}

void parse_options(int argc, char* argv[])
{
	struct Option *opast, *opresent, *omask, *oout;
	struct Flag *f_bool, *f_overwrite, *f_verbose, *f_summary, *f_check_zero;
	
	/* Define the different options */

	opast = G_define_option() ;
	opast->key        = "past";
	opast->type       = TYPE_STRING;
	opast->required   = YES;
	opast->gisprompt  = "old,cell,raster" ;
	opast->description= "Name of past layer" ;

	opresent = G_define_option() ;
	opresent->key        = "present";
	opresent->type       = TYPE_STRING;
	opresent->required   = YES;
	opresent->gisprompt  = "old,cell,raster" ;
	opresent->description= "Name of present layer";

	oout = G_define_option() ;
	oout->key        = "output";
	oout->type       = TYPE_STRING;
	oout->required   = NO;
	oout->gisprompt  = "cell,raster" ;
	oout->description= "Output map with distances at cells";

	omask = G_define_option() ;
	omask->key        = "mask";
	omask->type       = TYPE_STRING;
	omask->required   = NO;
	omask->gisprompt  = "old,cell,raster" ;
	omask->description= "Name of mask layer";

	/* Define the different flags */
	
	f_bool = G_define_flag() ;
	f_bool->key         = 'b' ;
	f_bool->description = "Boolean spread, cells are present/absent";
	f_bool->answer      = FALSE;
	
	f_verbose = G_define_flag();
	f_verbose->key    = 'q' ;
	f_verbose->description = "Quiet";
	f_verbose->answer = FALSE;
	
	f_summary = G_define_flag();
	f_summary->key    = 's' ;
	f_summary->description = "Summary stats only, not individual distances.";
	f_summary->answer = FALSE;

	f_check_zero = G_define_flag();
	f_check_zero->key    = 'z' ;
	f_check_zero->description = "Explicitly check and ignore cell values that are zero.";
	f_check_zero->answer = FALSE;

	f_overwrite = G_define_flag();
	f_overwrite->key    = 'o' ;
	f_overwrite->description = "Overwrite output map";
	f_overwrite->answer = FALSE;
	
	if (G_parser(argc, argv))
		exit (-1);
		
	past    =  opast->answer;
	present = opresent->answer;
	mask    = omask->answer;
	output  = oout->answer;
	is_boolean = f_bool->answer;
	is_overwrite = f_overwrite->answer;
	is_verbose = !(f_verbose->answer);
	is_summary = f_summary->answer;
	if (f_check_zero->answer) {
		past_check_zero=1;
		present_check_zero=1;
	}
	
}


void moment(double data[], int n, double *ave, double *adev, double *sdev,
    double *var, double *skew, double *curt, double *max)
//Given an array of data[1..n], this routine returns its mean ave, average deviation adev,
//standard deviation sdev, variance var, skewness skew, and kurtosis curt.
{
    int j;
    double ep=0.0,s,p;
    if (n <= 1) {
    	*ave = NAN; *adev = NAN; *sdev = NAN; *var = NAN; *skew = NAN; *curt = NAN;
    	*max = NAN;
    }

	*max=0.0;
    s=0.0;
    for (j=0;j<n;j++) s += data[j];
    *ave=s/n;

    *adev=(*var)=(*skew)=(*curt)=0.0;

    for (j=0;j<n;j++) {
    	if (data[j] > *max) *max = data[j];
         *adev += fabs(s=(data[j] - (*ave)));
         ep += s;
         *var += (p=s*s);
         *skew += (p *= s);
         *curt += (p *= s);
    }
    *adev /= n;

    *var=(*var-ep*ep/n)/(n-1);

    *sdev=sqrt(*var);

    if (*var) {
         *skew /= (n*(*var)*(*sdev));
         *curt=(*curt)/(n*(*var)*(*var))-3.0;
    } else
    {
    	*skew = NAN;
    	*curt = NAN;
    }
}

