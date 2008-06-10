/****************************************************************************
 *
 * MODULE:       r.dispersal.ros
 * AUTHOR(S):    Joel Pitt
 * PURPOSE:      Calculate the rate of spread in radial arcs, or
 *               in a specified direction
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
//#define DEBUG2

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <limits.h>

#include "grass/gis.h"

#define ARC_INC 65536u
#define MAX_BC_WEIGHTS 10

typedef struct {
	double **best_cell;
	double *ffw;
	double *mean;
	double *sd;
	double *density;
	double *adev, *skew, *curt;
	// double *log

} Boundary, *BoundaryPtr;

/* function prototypes */
void parse_options(int argc, char* argv[]);
char process_answers (char **answers);
void parse_input_maps(char **answers);
int init();
int init_arcs();
int find_boundaries(char* map, BoundaryPtr b, int index);
int find_centre(char* map, char* mapset, int* x, int* y);
void reset_arcs();
void add_to_arc(int row, int col);
int cmp_distances(const void *a, const void *b);
BoundaryPtr new_boundary();
void dump_boundary(int i);
void delete_boundary(BoundaryPtr b);
void dump_spread_rate_stats();
void dump_spread_rate();

int is_boolean, is_overwrite, is_verbose, is_summary, is_rate, is_segments, is_center;
int uses_mean_centre;

struct Cell_head window;
char **input_maps = NULL, **input_mapsets = NULL;
int n_input_maps = 0;

char *output, *output_mapset;

int arcs;
int start_x, start_y;
int *mean_x, *mean_y;
double start_angle, direction;

// Weight parameters for bestcell boundary algorithm
int n_bestcell_weights = 0;
double bestcell_weights[10];

RASTER_MAP_TYPE datatype, mask_datatype;

unsigned int *arcs_count = NULL, *arcs_max = NULL;
double **arcs_distances = NULL;
double arc_width = 0.0;

BoundaryPtr *boundaries = NULL;
//int n_boundaries = 0;

int
main(int argc, char *argv[])
{
		
	struct GModule *module = NULL;
	int i = 0;
	
	G_gisinit(argv[0]);
	
	module = G_define_module();
	module->description =
		"Find rate of spread using different boundary estimation techniques";
		
	//find_boundaries(NULL, NULL,  i);

	parse_options(argc, argv);

	init_arcs();
	
	init();
	
	if (is_summary)
	{
		fprintf(stdout,"stat, arc, ");
		fprintf(stdout,"mean, sd, furthest_forward, ");
		for (i=0; i < n_bestcell_weights; i++)
			fprintf(stdout,"best_cell_%.1f, ",bestcell_weights[i]);
		fprintf(stdout,"density\n");
	} else {
		fprintf(stdout,"map, arc, ");
		if (is_center) 	fprintf(stdout,"center_x, center_y, ");
		fprintf(stdout,"mean, sd, adev, skew, kurtosis, furthest_forward, ");
		for (i=0; i < n_bestcell_weights; i++)
			fprintf(stdout,"best_cell_%.1f, ",bestcell_weights[i]);
		fprintf(stdout,"density\n");
	}
	
	for (i=0; i < n_input_maps; i++) 
	{
		find_boundaries(input_maps[i], boundaries[i],  i);
		if (!is_summary)
		{
			if (is_rate && i > 0) dump_spread_rate(i);
			else if (!is_rate) dump_boundary(i);
		}
		
	}
	
	if (is_summary)
		dump_spread_rate_stats();
	
	
	
//	calc_stats(present);
	
	
	return 0;
}

BoundaryPtr new_boundary()
{
	BoundaryPtr b = NULL;
	unsigned int b_size;
	int i;
	
	b_size = sizeof(double) * arcs;
	
	b = G_malloc((unsigned int) sizeof(Boundary));
	
	if (b)
	{
		
		b->density = G_malloc(b_size);
		b->ffw = G_malloc(b_size);
		b->mean = G_malloc(b_size);
		b->sd = G_malloc(b_size);
		b->adev = G_malloc(b_size);
		b->skew = G_malloc(b_size);
		b->curt = G_malloc(b_size);
		
		memset(b->density , 0, b_size);
		memset(b->ffw , 0, b_size);
		memset(b->mean , 0, b_size);
		memset(b->sd , 0, b_size);
		memset(b->adev , 0, b_size);
		memset(b->skew , 0, b_size);
		memset(b->curt , 0, b_size);

		b->best_cell = G_malloc(sizeof(double*) * arcs);
		memset(b->best_cell, 0, sizeof(double*) * arcs);
		for (i = 0; i < arcs; i++)
		{
			b->best_cell[i] = G_malloc(sizeof(double) * n_bestcell_weights);
			memset(b->best_cell[i], 0, sizeof(double) * n_bestcell_weights);
		}
	}
	
	return b;
}

void delete_boundary(BoundaryPtr b)
{
	int i;
	for (i = 0; i < arcs; i++)
	{
		G_free(b->best_cell[i]);
	}
	G_free(b->best_cell);
	G_free(b->density);
	G_free(b->ffw);
	G_free(b->mean);
	G_free(b->sd);
	G_free(b->adev);
	G_free(b->skew);
	G_free(b->curt);
	
	
	G_free(b);
}

#ifdef DEBUG
void dump_arcs()
{
	int i,j;
	
	for (i=0; i < arcs; i++)
	{
		fprintf(stderr,"a%d: ",i);
		for (j=0; j < arcs_count[i]; j++)
		{
			fprintf(stderr, "%f, ", arcs_distances[i][j]);

		}
		fprintf(stderr,"\n");
	}
	
}
#endif

void dump_boundary(int index)
{
	int i,j;
	BoundaryPtr b;
	
	b = boundaries[index];
	
	for (i=0; i < arcs; i++)
	{
		fprintf(stdout,"%s, %d, ",input_maps[index], i);
		if (is_center) fprintf(stdout,"%f, %f, ",(double)start_x,(double)start_y);
		fprintf(stdout,"%f, %f, %f, %f, %f, %f, ", b->mean[i], b->sd[i], b->adev[i], b->skew[i], b->curt[i], b->ffw[i]);
		for (j=0; j < n_bestcell_weights; j++)
			fprintf(stdout,"%f, ",b->best_cell[i][j]);
		fprintf(stdout,"%f", b->density[i]);
		fprintf(stdout,"\n");
	}
	
}

void dump_spread_rate(int index)
{
	int i,j;
	BoundaryPtr b,c;
	double diffx, diffy;
	
	if (index < 1) return;
	
	b = boundaries[index];
	c = boundaries[index-1];

	if (uses_mean_centre)
	{
		diffx = (double) mean_x[index] - mean_x[index-1];
		diffy = (double) mean_y[index] - mean_y[index-1];
	} else 
	{
		diffx=0.0; diffy=0.0;
	}

	
	for (i=0; i < arcs; i++)
	{
		double angle;
		double x, y, dist;
		
		if (arcs > 1)
		{
			angle = start_angle + ( i * arc_width );
			x = cos(angle) * diffx;
			y = sin(angle) * diffy;
			dist = sqrt( (x*x) + (y*y));
		} else 
		{
			dist = 0;
		}
		
		fprintf(stdout,"%s, %d, ",input_maps[index], i);
		if (is_center) fprintf(stdout,"%f, %f, ",(double)start_x,(double)start_y);
		fprintf(stdout,"%f, %f, %f, ", b->mean[i] - c->mean[i] + dist,
			b->sd[i] - c->sd[i] + dist, b->ffw[i] - c->ffw[i] + dist);
		for (j=0; j < n_bestcell_weights; j++)
			fprintf(stdout,"%f, ", b->best_cell[i][j] - c->best_cell[i][j] + dist);
		fprintf(stdout,"%f", b->density[i] - c->density[i] + dist);
		fprintf(stdout,"\n");
	}
}

void dump_spread_rate_stats()
{
	double *sum[4], *sumsq[4];
	double **bc_sum, **bc_sumsq;
	int i,j,k;
	
	for (j=0; j < 4; j++)
	{
		sum[j] = G_malloc((unsigned int) sizeof(double) * arcs);
		sumsq[j] = G_malloc((unsigned int) sizeof(double) * arcs);
		
		memset(sum[j], 0, sizeof(double) * arcs);
		memset(sumsq[j], 0, sizeof(double) * arcs);
	}
	
	// Initialise bestcell storage
	bc_sum = G_malloc((unsigned int) sizeof(double*) * arcs);
	bc_sumsq = G_malloc((unsigned int) sizeof(double*) * arcs);
	memset(bc_sum, 0, sizeof(double*) * arcs);
	memset(bc_sumsq, 0, sizeof(double*) * arcs);
	for (j=0; j < arcs; j++)
	{
		bc_sum[k] = G_malloc((unsigned int) sizeof(double) * n_bestcell_weights);
		bc_sumsq[k] = G_malloc((unsigned int) sizeof(double) * n_bestcell_weights);
		memset(bc_sum[k], 0, sizeof(double) * n_bestcell_weights);
		memset(bc_sumsq[k], 0, sizeof(double) * n_bestcell_weights);
	}
	///////////////////////////
	
	for (i=1; i < n_input_maps; i++)
	{
		for (j=0; j < arcs; j++)
		{
			double diff;
			
			diff = boundaries[i]->mean[j] - boundaries[i-1]->mean[j];
			sum[0][j] += diff;
			sumsq[0][j] += diff*diff;
			
			diff = boundaries[i]->sd[j] - boundaries[i-1]->sd[j];
			sum[1][j] += diff;
			sumsq[1][j] += diff*diff;
			
			diff = boundaries[i]->ffw[j] - boundaries[i-1]->ffw[j];
			sum[2][j] += diff;
			sumsq[2][j] += diff*diff;
			
			diff = boundaries[i]->density[j] - boundaries[i-1]->density[j];
			sum[3][j] += diff;
			sumsq[3][j] += diff*diff;
			
			for (k=0; k < n_bestcell_weights; k++)
			{
				diff = boundaries[i]->best_cell[j][k] - boundaries[i-1]->best_cell[j][k];
				bc_sum[j][k] += diff;
				bc_sumsq[j][k] += diff*diff;
			}
			
		}
	}
	
	for (j=0; j < arcs; j++)
	{
		fprintf(stdout, "mean, %d, %f, %f, %f, ",
			j,
			sum[0][j] / n_input_maps,
			sum[1][j] / n_input_maps,
			sum[2][j] / n_input_maps);
		for (k=0; k < n_bestcell_weights; k++)
			fprintf(stdout, "%f, ", bc_sum[j][k] / n_input_maps);
		fprintf(stdout, "%f", sum[3][j] / n_input_maps);
		fprintf(stdout, "\n");
				
		fprintf(stdout, "sd, %d, %f, %f, %f, ",
			j,
			sqrt(((n_input_maps * sumsq[0][j]) - (sum[0][j] * sum[0][j])) / (n_input_maps * (n_input_maps-1))),
			sqrt(((n_input_maps * sumsq[1][j]) - (sum[1][j] * sum[1][j])) / (n_input_maps * (n_input_maps-1))),
			sqrt(((n_input_maps * sumsq[2][j]) - (sum[2][j] * sum[2][j])) / (n_input_maps * (n_input_maps-1))));
		for (k=0; k < n_bestcell_weights; k++)
			fprintf(stdout, "%f, ", sqrt(((n_input_maps * bc_sumsq[j][k]) - (bc_sum[j][k] * bc_sum[j][k])) / (n_input_maps * (n_input_maps-1))));
		fprintf(stdout,"%f", sqrt(((n_input_maps * sumsq[3][j]) - (sum[3][j] * sum[3][j])) / (n_input_maps * (n_input_maps-1))));
		fprintf(stdout, "\n");

	}	
}

void moment(double data[], unsigned int n, double *ave, double *adev, double *sdev,
    double *var, double *skew, double *curt)
//Given an array of data[1..n], this routine returns its mean ave, average deviation adev,
//standard deviation sdev, variance var, skewness skew, and kurtosis curt.
{
    unsigned int j;
    double ep=0.0,s,p;
    if (n <= 1) {
        *ave = NAN; *adev = NAN; *sdev = NAN; *var = NAN; *skew = NAN; *curt = NAN;
        //*max = NAN;
    }

        //*max=0.0;
    s=0.0;
    for (j=0;j<n;j++) s += data[j];
    *ave=s/n;

    *adev=(*var)=(*skew)=(*curt)=0.0;

    for (j=0;j<n;j++) {
        //if (data[j] > *max) *max = data[j];
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


int find_boundaries(char* map, BoundaryPtr b, int bi)
{
	char* mapset;
	
	struct Cell_head cellhd;
	int row,col,i;
	int infd;
	void *inrast;
	int nrows, ncols;
	
#ifdef DEBUG
	printf("bi is %d\n", bi);
#endif
	
	if (map == NULL || b == NULL)
		return -1;
	
	reset_arcs();

	/* find past map in mapset */
	mapset = G_find_cell2 (map, "");
	if (mapset == NULL)
		G_fatal_error ("cell file [%s] not found", map);

	if (G_get_cellhd (map, mapset, &cellhd) < 0)
		G_fatal_error ("Cannot read file header of [%s]", map);
		
	/* Allocate input buffer */
	inrast = G_allocate_raster_buf(datatype);

	/* Get region size */
	nrows = G_window_rows();
	ncols = G_window_cols();
	
	/* Find centre if it hasn't been set */
	if (uses_mean_centre)
		find_centre(map, mapset, &(mean_x[bi]), &(mean_y[bi]));

#ifdef DEBUG
	printf("centre %d %d\n", start_x, start_y);
#endif
	
	if ( (infd = G_open_cell_old (map, mapset)) < 0)
		G_fatal_error ("Cannot open cell file [%s]", map);
	
	/* Process map by adding occupied cells to the corresponding arc */
	for (row = 0; row < nrows; row++)
	{	
		/* read input map */
		if (G_get_raster_row (infd, inrast, row, datatype) < 0)
			G_fatal_error ("Could not read from <%s>",map);
		
		switch (datatype) {
		case CELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (!G_is_c_null_value(inrast + (col*sizeof(CELL))))
					add_to_arc(row,col);
			}
			break;
		case FCELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (!G_is_f_null_value(inrast + (col*sizeof(FCELL))))
					add_to_arc(row,col);
			}
			break;
		case DCELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (!G_is_d_null_value(inrast + (col*sizeof(DCELL))))
					add_to_arc(row,col);
			}
			break;
		}

	}
	G_close_cell (infd);
	G_free(inrast);
	
	#ifdef DEBUG
	dump_arcs();
	#endif
	
	/* Sort the distances in the arcs/segments */
	for (i = 0; i < arcs; i++)
		if (arcs_count[i] > UINT_MAX)
		{
			printf ("arcs_count[%d] greater than UINT_MAX",i);
			exit(1);
		}
		qsort(arcs_distances[i], (unsigned int) arcs_count[i], sizeof(double), &cmp_distances);
	
	#ifdef DEBUG
	dump_arcs();
	#endif
	
	// Calc mean and s.d	
	for (i = 0; i < arcs; i++)
	{
		// For other distance measures:
		double ave, adev, sdev, var, skew, curt;

		moment(arcs_distances[i], arcs_count[i], &ave, &adev, &sdev, &var, &skew, &curt);
		
		b->mean[i] = ave;
		b->sd[i] = sdev;
		b->adev[i] = adev;
		b->skew[i] = skew;
		b->curt[i] = curt;
		
	}
	
	// Calc furthest forward
	for (i = 0; i < arcs; i++)
	{
//			printf("ffw %d %f\n", i, b->ffw[i]);
		if (arcs_count[i])
			b->ffw[i] = arcs_distances[i][arcs_count[i]-1];
	}

	// Calc best cell	
	{
		int k;
		double r;
		double max;
		double inc, res;
		int index, min_index;
		
		// misclassified cells as absent, present
		double ma, mp;
		
		double error, min_error = HUGE_VAL;

		for (k=0; k < n_bestcell_weights; k++)
		{
			double weight = bestcell_weights[k];
		
			for (i = 0; i < arcs; i++)
			{
				if (arcs_count[i] < 1) continue;
				// max is the largest distance in arc
				max = arcs_distances[i][arcs_count[i]-1];
				// inc is the amount to increment by every iteration
				res = window.ns_res * window.ew_res;
				inc = (window.ns_res + window.ew_res) / 2.0;
				r=inc*2.0;
				index = 0; min_index = -1;
				min_error = HUGE_VAL;
				
				while (r < max)
				{
					while (r > arcs_distances[i][index])
					{
						index++;
					}
					
					ma = (M_PI * r * r / (arcs * res)) - index;
					mp = weight * (arcs_count[i] - (index + 1));
					
					error = ma + mp;
	
					#ifdef DEBUG2
					fprintf(stderr, "bc %f %f %f\n", ma, mp, error);
					#endif
					
					if (error < min_error)
					{
						min_error = error;
						min_index = index;
					}
					
					r += inc;
				}
				
				if (min_index != -1)		
					b->best_cell[i][k] = arcs_distances[i][min_index];
			}
			
		}
	}
	
	// density
	{
				
		double r, lower_r;
		double max;
		double res,inc;
		int index, lower_index, last_index, max_delta_index = -1;
		
		double density, last_density;
		double delta = 0.0, max_delta = 0.0;
		
		double *deltas = NULL; int ndeltas;
		int d_index;

		res = (window.ns_res + window.ew_res) / 2.0;
		
		for (i = 0; i < arcs; i++)
		{
			if (arcs_count[i] < 1) continue;
			// max is the largest distance in arc
			max = arcs_distances[i][arcs_count[i]-1];
			// inc is the amount to increment by every iteration
			// 5 should be replaced by a variable on coarseness
			inc = b->mean[i] / (5.0 * res);
		
			d_index = 0;
			ndeltas = (max/inc) + 1;
			deltas = G_malloc((unsigned int) sizeof(double) * ndeltas);
			
			delta = 0.0;
			max_delta = 0.0;
			max_delta_index = -1;
			last_density = -1.0;
			
			lower_r=0.0;
			r=inc;//b->mean[i];
			index = 0; lower_index = 0;
			last_index = 0;
			
			while (r < max)
			{
				while (lower_r > arcs_distances[i][lower_index])
				{
					lower_index++;
				}
				while (r > arcs_distances[i][index])
				{
					index++;
				}

				// inc is also average resolution
				// sqrt because this way it doesn't matter about resolution and
				// how many cells are completely within a certain radius
				//area = (M_PI * r * r / (arcs * inc)) - (M_PI * lower_r * lower_r / (arcs * inc));// - last_area;

				density = sqrt((double) index) - sqrt((double) lower_index); // floor(area); //(index - lower_index) / area;
								
				if (last_density != -1.0)
				{
					deltas[d_index] = last_density - density;
					//printf("d %f\n",deltas[d_index]);
					d_index++;

				}
				
				last_density = density;
				last_index = index;
				
				r += inc;
				lower_r += inc;
			}
			
			for (index = 0; index < d_index; index++)
			{
				delta = deltas[index];// + deltas[index] + deltas[index + 1];
				delta = delta;// / 3;
				
				if (delta > max_delta)
				{
					max_delta = delta;
					max_delta_index = index;
					
					//fprintf(stderr,"new max d %f index %d\n", delta, index);
				}
			}
			
			index = 0;
			r=inc*(max_delta_index+2);
			while (r > arcs_distances[i][index])
			{
				index++;
			}
			
			if (max_delta_index != -1)
				b->density[i] = arcs_distances[i][index];
			
			G_free(deltas);
		}
	}
	
//#ifdef DEBUG
//	dump_boundary(b);
//#endif
	
    return 0;
	
}

int cmp_distances(const void *a, const void *b)
{
	double *da, *db, result;
	da = (double*) a; db = (double*) b;
	result = ((*da) - (*db));
	
	if (result < 1.0 && result > 0.0)
		result = 1.0;
	else if (result > -1.0 && result < 0.0)
		result = -1.0;

//	fprintf(stderr,"da %f db %f result %f\n", *da, *db, result);
	return (int) result;
}



int init_arcs()
{
	int i;
	
	arcs_count = G_malloc((unsigned int) ( arcs * sizeof(unsigned int) ));
	arcs_max = G_malloc((unsigned int) ( arcs * sizeof(unsigned int) ));
	arcs_distances = G_malloc((unsigned int) ( arcs * sizeof(double*) ) );
	
	for (i=0; i < arcs; i++)
	{
		arcs_max[i] = ARC_INC;
		arcs_count[i] = 0u;
		arcs_distances[i] = G_malloc((unsigned int) arcs_max[i] * sizeof(double));
	}
	arc_width = (2 * M_PI) / arcs;
	
	return 0;
}

void reset_arcs()
{
	int i;
	for (i=0; i < arcs; i++)
	{
		arcs_count[i] = 0u;
	}
}

void add_to_arc(int row, int col)
{
	int dx, dy;
	double distance;
	double a;
	int arc_index;
	
	dx = (col - start_x) * window.ew_res;
	dy = (row - start_y) * window.ns_res;
	
	distance = sqrt((double) ((double)dy * (double)dy) + ((double)dx * (double)dx));
	a = atan2((double)dx, (double)dy);
	
	#ifdef DEBUG
	if (isnan(distance))
	{
		printf("Distance to add is nan. dx %d dy %d\n", dx, dy);
		exit(1);
	}
	#endif // DEBUG	
	
	// decide on arc to place into, based on angle
	if (a < 0) a += (2*M_PI);
	a = a - (start_angle - (arc_width/2.0)) + M_PI;
	if (a >= (2*M_PI)) a = a - (2*M_PI);

	arc_index = a / arc_width;
	
#ifdef DEBUG2
	printf("add dist %f, angle %f, to arc %d\n", distance, a, arc_index);
#endif
	
	// Increase space if needed
	if (arcs_count[arc_index] >= arcs_max[arc_index])
	{
#ifdef DEBUG
		printf("increase dist %d storage %u/%u to %u/%u \n", arc_index, arcs_count[arc_index],
		arcs_max[arc_index], arcs_count[arc_index], arcs_max[arc_index] + ARC_INC);
#endif
		arcs_max[arc_index] = arcs_max[arc_index] + ARC_INC;
		arcs_distances[arc_index] = G_realloc(arcs_distances[arc_index],
				(unsigned int) arcs_max[arc_index] * sizeof(double));
	}
	
	arcs_distances[arc_index][arcs_count[arc_index]] = distance;
	arcs_count[arc_index] = arcs_count[arc_index] + 1u;

//#ifdef DEBUG2
//	dump_arcs();
//#endif
	
}



int init()
{
	int i;
	
	for (i=0; i < n_input_maps; i++)
	{
		/* find past map in mapset */
		input_mapsets[i] = G_find_cell2 (input_maps[i], "");
    	if (input_mapsets[i] == NULL)
    		G_fatal_error ("cell file [%s] not found", input_maps[i]);

		input_mapsets[i] = G_strdup(input_mapsets[i]);    		
	}
   
    if (output != NULL)
    {
    	output_mapset = G_find_vector2 (output, input_mapsets[i]);
		if ( output_mapset != NULL )
		{
			if (is_overwrite == TRUE)
			{
				char buffer[512];
				sprintf(buffer, "g.remove vect=%s > /dev/null", output);
				system(buffer);
			
			} else {
				G_fatal_error ("Output map <%s> exists (use -o flag to force"
				" overwrite)",output);
			}
		}
	}
        
    /* determine the past inputmap type (CELL/FCELL/DCELL) */
	datatype = G_raster_map_type(input_maps[0], input_mapsets[0]);
	
	boundaries = G_malloc((unsigned int) sizeof(BoundaryPtr) * n_input_maps);
	for (i=0; i < n_input_maps; i++)
	{
		boundaries[i] = new_boundary();
	}
	
	if (uses_mean_centre)
	{
		mean_x = G_malloc((unsigned int) sizeof(int) * n_input_maps);
		mean_y = G_malloc((unsigned int) sizeof(int) * n_input_maps);
		
		//memset(mean_x, 0, sizeof(int) * n_input_maps);
		//memset(mean_y, 0, sizeof(int) * n_input_maps);
	}
	
	return 0;
    
}


void parse_options(int argc, char* argv[])
{
	struct Option *o_input, *o_out;
	struct Option *o_arcs, *o_start_angle;
	struct Option *o_start_point;
	struct Option *o_weights;
	struct Flag *f_bool, *f_overwrite, *f_verbose, *f_summary, *f_rate, *f_segments, *f_center;
	
	/*  Get database window parameters      */

	if (G_get_window(&window) < 0)
	{
	G_fatal_error ("Can't read current window parameters");
	exit(1);
	}
	
	/* Define the different options */

	o_input = G_define_option() ;
	o_input->key        = "input";
	o_input->type       = TYPE_STRING;
	o_input->required   = YES;
	o_input->gisprompt  = "old,cell,raster" ;
	o_input->description= "List of input raster maps in chronological order";
	o_input->multiple   = YES;

	o_out = G_define_option() ;
	o_out->key        = "output";
	o_out->type       = TYPE_STRING;
	o_out->required   = NO;
	o_out->gisprompt  = "dig,vector" ;
	o_out->description= "Output vector map of boundaries";

	o_arcs = G_define_option() ;
	o_arcs->key        = "arcs";
	o_arcs->type       = TYPE_INTEGER;
	o_arcs->required   = NO;
	o_arcs->description= "Number of arcs/segments to calculate boundaries for";
	o_arcs->answer     = "1";

	o_start_angle = G_define_option() ;
	o_start_angle->key        = "angle";
	o_start_angle->type       = TYPE_DOUBLE;
	o_start_angle->required   = NO;
	o_start_angle->description= "Direction for the centre of the first arc (0 degree = North), or direction from centre to calc. boundaries from (with -f)";
	o_start_angle->answer     = "0.0";

	o_start_point = G_define_option();
	o_start_point->key        = "centre";
	o_start_point->type       = TYPE_STRING;
	o_start_point->key_desc   = "x,y";
	o_start_point->required   = NO;
	o_start_point->description= "Centre point from which to calc. boundaries from (default = mean centre of map)";

	o_weights = G_define_option();
	o_weights->key        = "weights";
	o_weights->type       = TYPE_STRING;
	o_weights->key_desc   = "x";
	o_weights->required   = NO;
	o_weights->description= "Weight parameters to use for calculating boundaries via best cell method";
	o_weights->multiple   = YES;
	
	/* Define the different flags */
	
	f_bool = G_define_flag() ;
	f_bool->key         = 'b' ;
	f_bool->description = "Boolean map, cells are present/absent";
	f_bool->answer      = FALSE;
	
	f_segments = G_define_flag();
	f_segments->key    = 'f' ;
	f_segments->description = "Calculate as segments in one direction instead of radially";
	f_segments->answer = FALSE;

	f_verbose = G_define_flag();
	f_verbose->key    = 'q' ;
	f_verbose->description = "Quiet";
	f_verbose->answer = FALSE;
	
	f_rate = G_define_flag();
	f_rate->key    = 's' ;
	f_rate->description = "Spread rates instead of boundaries";
	f_rate->answer = FALSE;
		
	f_summary = G_define_flag();
	f_summary->key    = 'S' ;
	f_summary->description = "Spread rate stats only";
	f_summary->answer = FALSE;

	f_overwrite = G_define_flag();
	f_overwrite->key    = 'o' ;
	f_overwrite->description = "Overwrite output map";
	f_overwrite->answer = FALSE;
	
	f_center = G_define_flag();
	f_center->key    = 'c' ;
	f_center->description = "Output center coordinates";
	f_center->answer = FALSE;
	
	if (G_parser(argc, argv))
		exit (-1);

	parse_input_maps(o_input->answers);

	output = o_out->answer;

	arcs = atoi(o_arcs->answer);
	start_angle = atof(o_start_angle->answer);
	
	// Get starting point
	if (o_start_point->answers)
	{
		if (!process_answers(o_start_point->answers))
			G_fatal_error("Couldn't get start points");
			
		uses_mean_centre = 0;
	}
	else {
		uses_mean_centre = 1;
		
		start_x = 0;
		start_y = 0;
	}

	// Get bestcell weight parameters
	if (o_weights->answers)
	{
		int n;
		char** answers;
		answers = o_weights->answers;

		for(n=0; *answers != NULL && n < 10; answers += 1)
		{
			bestcell_weights[n] = atof(*answers);
			n++;
			if (n>=10) G_warning("Arbitrary limit of 10 values for best cell weight parameter, ignoring the rest");
		}
		n_bestcell_weights=n;
	} else {
		bestcell_weights[0]=3.0;
		n_bestcell_weights=1;
	}
	
	is_boolean = f_bool->answer;
	is_overwrite = f_overwrite->answer;
	is_verbose = !(f_verbose->answer);
	is_summary = f_summary->answer;
	is_rate = f_rate->answer;
        is_segments = f_segments->answer;
	is_center = f_center->answer;
	
	// Is rates are not calculated and centers are based on the mean then output centers
	// because if we don't rates can't be calculated later.
	if (!is_rate && uses_mean_centre)
	{
		is_center = 1;
	}
	if (!is_boolean)
	{
		G_fatal_error("Non boolean ROS analysis not yet supported.\n");
	}
	if (is_segments)
	{
		G_fatal_error("Segment ROS analysis not yet supported.\n");
	}
	
}

// Scans the start coordinate
char process_answers (char **answers)
{
        int col, row, n ;
        double east, north;

        int got_one = 0 ;

        if (! answers)
                return(0) ;

        for(n=0; *answers != NULL; answers+=2)
        {
                if(!G_scan_easting(*answers, &east, G_projection()))
                {
                        fprintf (stderr, "Illegal x coordinate <%s>\n",
                                         *answers);
                        G_usage();
                        exit(1);
                }
                if(!G_scan_northing(*(answers+1), &north, G_projection()))
                {
                        fprintf (stderr, "Illegal y coordinate <%s>\n",
                                         *(answers+1));
                        G_usage();
                        exit(1);
               }

                if(east < window.west ||
                   east > window.east ||
                   north < window.south ||
                   north > window.north)
                {
                        fprintf(stderr,"Warning, ignoring point outside window: \n") ;
                        fprintf(stderr,"   %.4f,%.4f\n", east, north) ;
                        continue ;
                }
                else
                        got_one = 1 ;

                row = (window.north - north) / window.ns_res;
                col = (east - window.west) / window.ew_res;

                start_y = row;
                start_x = col;

        }
        return(got_one) ;
}

void parse_input_maps(char** answers)
{
	int i = 0;
	while (answers[i] != NULL) i++;
	n_input_maps = i;
	
	input_maps = answers;
	input_mapsets = G_malloc((unsigned int) sizeof(char*) * n_input_maps);
	
}

int find_centre(char* map, char* mapset, int* x, int* y)
{
	double sum_x = 0.0;
	double sum_y = 0.0;
	unsigned int n = 0;
	void *inrast;
	int row,col;
	int nrows,ncols;
	int infd;

	/* Allocate input buffer */
	inrast = G_allocate_raster_buf(datatype);
    
    	/* Get region size */
	nrows = G_window_rows();
	ncols = G_window_cols();
	
	// Find mean centre
	// TODO: make it find centre of gravity for non boolean maps
	// TODO: Another type of boundary using s.d of centre?		
	if ( (infd = G_open_cell_old (map, mapset)) < 0)
		G_fatal_error ("Cannot open cell file [%s]", map);
		
	for (row = 0; row < nrows; row++)
	{	
		/* read input map */
		if (G_get_raster_row (infd, inrast, row, datatype) < 0)
			G_fatal_error ("Could not read from <%s>",map);
		
		switch (datatype) {
		case CELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (!G_is_c_null_value(inrast + (col*sizeof(CELL))))
				{
					sum_x += col;
//						sumsq_x += (col * col);
					sum_y += row;
//						sumsq_y += (row * row);
					n++;
					
					#ifdef DEBUG2
					printf("sum x %d y %d\n",sum_x,sum_y);
					#endif
				}
			}
			break;
		case FCELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (!G_is_f_null_value(inrast + (col*sizeof(FCELL))))
				{
					sum_x += col;
//						sumsq_x += (col * col);
					sum_y += row;
//						sumsq_y += (row * row);
					n++;						
				}
			}
			break;
		case DCELL_TYPE:
			/*process the data */
			for (col=0; col < ncols; col++)
			{
				if (!G_is_d_null_value(inrast + (col*sizeof(DCELL))))
				{
					sum_x += col;
//					sumsq_x += (col * col);
					sum_y += row;
//					sumsq_y += (row * row);
					n++;						
				}
			}
			break;
		}

	}
	
	*x = sum_x / n;
	*y = sum_y / n;

	start_x = *x;
	start_y = *y;
	
	//#ifdef DEBUG
	printf("sum x %f y %f, n %u, mean centre %d %d\n", sum_x, sum_y, n, start_x, start_y);
	//#endif

	G_close_cell (infd);

	return 0;
}
