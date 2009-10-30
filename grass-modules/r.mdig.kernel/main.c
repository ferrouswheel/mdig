/****************************************************************************
 * MODULE:       r.mdig.kernel
 * AUTHOR(S):    Joel Pitt
 * PURPOSE:      Spreads present cells at random to remote sites.
 *
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
 *
 *****************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

#include "grass/gis.h"

#include "kernel_math.h"
#include "is_present.h"

extern double gamma_values;

typedef struct {
    int row;
    int col;
    CELL cvalue;
    FCELL fvalue;
    DCELL dvalue;
} Jump;

void init_jump(Jump* jptr);
void expand_jump_array();

void parse_options(int argc, char* argv[]);
int compare_jumps(const void *a, const void *b);
void process_jumps();

int get_number_of_events(double, double);

int nrows, ncols;
int infd;
RASTER_MAP_TYPE data_type;

int is_boolean, is_overwrite, is_verbose, is_perimeter;
int check_zero=-1;

char *name, *result, *mapset;
void *inrast;

char *out_mapset;
void **outrast;

enum { GENERAL, CAUCHY, EXPONENTIAL, LOG } distribution;
double dist_a, dist_b, freq;
double (*dist_function)(double, double, double)=NULL;
long seed;
unsigned int maturity_age;
double truncation_limit=0.0;

#define JUMP_INC 10000
unsigned int jumps_count = 0, jumps_max = 0;
Jump* jumps = NULL;

int total_counter = 0;
int existing_counter = 0;

int out_of_bounds_counter=0;
double nsres, ewres;

#if defined(HAVE_DRAND48)
#define UNIFORM_RANDOM drand48()
#else
#define UNIFORM_RANDOM ((double)rand()/RAND_MAX)
#endif

/*-------------------------------------
Utility functions for jump array
  -------------------------------------*/
void init_jump(Jump* jptr) {
    memset(jptr, 0, sizeof(Jump));
}

void expand_jump_array() {
    int i;

    jumps_max += JUMP_INC;
    jumps = G_realloc(jumps, (unsigned int) sizeof(Jump) * jumps_max);

    for (i=jumps_count; i < jumps_max; i++) {
        init_jump(&(jumps[i]));
    }

}
/*-------------------------------------*/

/*
 * Calc finds out the distance and direction for
 * a dispersal event and adds to the jumps array
 */
void calc(void* x, int col, int row) {
    int events = 0, i;

    switch (data_type) {
    case CELL_TYPE:
	if (((CELL*)x)[col] < maturity_age) return;
	break;
    case FCELL_TYPE:
	if (((FCELL*)x)[col] < maturity_age) return;
	break;
    case DCELL_TYPE:
	if (((DCELL*)x)[col] < maturity_age) return;
	break;
    default:
	G_fatal_error ("Unknown data_type");
	break;
    }

    events = get_number_of_events(UNIFORM_RANDOM, freq);
    total_counter += events;
    for (i=0; i < events; i++) {
        double dist, a, b, angle;
        int dest_col, dest_row;

        a=dist_a;
        b=dist_b;

        dist=dist_function(UNIFORM_RANDOM, a, b);
        if (dist > truncation_limit) continue;

        angle = UNIFORM_RANDOM * (2.0 * M_PI);

        // Divide by resolution so that distance is res independent
        a=(sin(angle) * dist)/ewres;
        b=(cos(angle) * dist)/nsres;

        // If the distance is too small to leave the main cell:
        if (rint(a) == 0 && rint(b) == 0) {
            /*if (fabs(a) > fabs(b))
            {
            	if (a > 0) a = ewres;
            	else a = -1;
            } else{
            	if (b > 0) b = nsres;
            	else b = -1;
            }*/
            existing_counter++;
            continue;

        }

        dest_col = col + (int) rint(a);
        dest_row = row + (int) rint(b);

        /* Check the destination coordinates are within boundaries */

        if (dest_col < 0 || dest_row < 0 ||
                dest_col >= ncols || dest_row >= nrows) {
            out_of_bounds_counter++;
            continue;
        }

        /* If we have run out of space for new jump events
         * then create some more
         */
        if ((jumps_count + 1) >= jumps_max) expand_jump_array();
        init_jump(&(jumps[jumps_count]));

        jumps[jumps_count].col = dest_col;
        jumps[jumps_count].row = dest_row;

        // TODO: allow the population that disperses to be settable
        switch (data_type) {
        case CELL_TYPE:
            //if (is_boolean) jumps[jumps_count].cvalue = (CELL) 1;
            //else {
            jumps[jumps_count].cvalue = (CELL) 1;
            //}
            break;
        case FCELL_TYPE:
            //if (is_boolean) jumps[jumps_count].fvalue = 1.0f;
            //else
            jumps[jumps_count].fvalue = 1.0f;
            break;
        case DCELL_TYPE:
            //if (is_boolean) jumps[jumps_count].dvalue = 1.0;
            //else
            jumps[jumps_count].dvalue = 1.0;
            break;
        default:
            G_fatal_error ("Unknown data_type");
            break;
        }

        jumps_count++;

    }


}

int
main(int argc, char *argv[]) {
    struct Cell_head cellhd;

    char rname[256], rmapset[256];
    char buff[1024];
    int row,col,is_reclass;
    int (*is_present)(void*, int) = NULL;

    struct GModule *module;

    G_gisinit(argv[0]);

    module = G_define_module();
    module->description =
        "Spread to neighbouring cells";

    parse_options(argc, argv);

    // find map in mapset
    mapset = G_find_cell2 (name, "");
    if (mapset == NULL)
        G_fatal_error ("cell file [%s] not found", name);

    if (G_legal_filename (result) < 0)
        G_fatal_error ("[%s] is an illegal name", result);

    // determine the inputmap type (CELL/FCELL/DCELL)
    data_type = G_raster_map_type(name, mapset);

    if ( (infd = G_open_cell_old (name, mapset)) < 0)
        G_fatal_error ("Cannot open cell file [%s]", name);

    // resolution information should come from active region
    // NOT from the input map
    //if (G_get_cellhd (name, mapset, &cellhd) < 0)
    //    G_fatal_error ("Cannot read file header of [%s]", name);
    if (G_get_set_window(&cellhd) < 0)
        G_fatal_error ("Cannot read active region");

    is_reclass = (G_is_reclass (name, mapset, rname, rmapset) > 0);
    sprintf(buff, "cell_misc/%s", name);
    // If check_zero is -1 then it hasn't been set through a command-line option
    if (check_zero == -1 && (!G_find_file(buff, "null", mapset) || is_reclass))
        check_zero=1;
    else
        check_zero=0;

    switch (distribution) {
    case GENERAL:
        dist_function = clark;
        break;
    case LOG:
        // TODO: implement LOG distribution
        G_warning("Log distribution not implemented, using Cauchy");
    case CAUCHY:
        dist_function = inv_cauchy_cdf;
        break;
    case EXPONENTIAL:
        dist_function = inv_exponential_cdf;
        break;
    }

    /* Allocate input buffer */
    inrast = G_allocate_raster_buf(data_type);

    /* Get region size */
    nrows = G_window_rows();
    ncols = G_window_cols();

    nsres = cellhd.ns_res;
    ewres = cellhd.ew_res;

    is_present = IS_PRESENT(data_type,check_zero);

    // When we thought freq should change with res...
    //if (is_perimeter)
    //	freq = (freq / 10000.0) * (2* (ewres + nsres));
    //else
    //	freq = (freq / 10000.0) * (nsres * ewres);

    // ...when it is really the same
    // (kernel, res, limited and earlier experiments used this method, 10000 as freq
    //freq = freq / 10000.0;
    // ....not necessary to divide either.

    for (row = 0; row < nrows; row++) {
        if (is_verbose) G_percent (row, 2 * nrows, 2);

        /* read input map */
        if (G_get_raster_row (infd, inrast, row, data_type) < 0)
            G_fatal_error ("Could not read from <%s>",name);

        /* process the data */
        for (col=0; col < ncols; col++) {
            if (is_present(inrast,col))
                calc(inrast,col,row);
        }

    }

    G_close_cell (infd);
    if ( (infd = G_open_cell_old (name, mapset)) < 0)
        G_fatal_error ("Cannot open cell file [%s]", name);

    process_jumps();

    G_free(inrast);

    printf("%d/%d/%d/%d new/existing/OOB/total dispersal events\n",
           total_counter - (existing_counter + out_of_bounds_counter),
           existing_counter,out_of_bounds_counter, total_counter);

    jumps_count = 0;
    G_free(jumps);

    return 0;
}

int compare_jumps(const void *a, const void *b) {
    int value = 0;

    Jump* aj = (Jump*) a;
    Jump* bj = (Jump*) b;

    value = aj->row - bj->row;
    if (value == 0) value = aj->col - bj->col;
    return value;
}

void process_jumps() {
    int row;
    int outfd;
    int jump_index=0;

    /* Open output file */

    /* Check for existing map and remove if overwrite flag is on */
    out_mapset = G_find_cell2 (result, mapset);
    if ( out_mapset != NULL ) {
        if (is_overwrite == TRUE) {
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

    qsort(jumps, (unsigned int) jumps_count, sizeof(Jump), *compare_jumps);

    for (row = 0; row < nrows; row++) {
        if (is_verbose) G_percent (row + nrows, 2 * nrows, 2);

        /* read input map */
        if (G_get_raster_row (infd, inrast, row, data_type) < 0)
            G_fatal_error ("Could not read from <%s>",name);

        switch (data_type) {
        case CELL_TYPE:
            for ( ; jump_index < jumps_count && jumps[jump_index].row == row; jump_index++ ) {
                int i = jump_index;
                int col = jumps[i].col;

                if (G_is_c_null_value(inrast + (col*sizeof(CELL))))
                    ((CELL *) inrast)[col] = jumps[i].cvalue;
                else existing_counter++;
            }
            break;
        case FCELL_TYPE:
            for ( ; jump_index < jumps_count && jumps[jump_index].row == row; jump_index++ ) {
                int i = jump_index;
                int col = jumps[i].col;

                if (G_is_f_null_value(inrast + (col*sizeof(FCELL))))
                    ((FCELL *) inrast)[col] = jumps[i].fvalue;
                else existing_counter++;
            }
            break;
        case DCELL_TYPE:
            for ( ; jump_index < jumps_count && jumps[jump_index].row == row; jump_index++ ) {
                int i = jump_index;
                int col = jumps[i].col;

                if (G_is_d_null_value(inrast + (col*sizeof(DCELL))))
                    ((DCELL *) inrast)[col] = jumps[i].dvalue;
                else existing_counter++;
            }
            break;
        }

        if (G_put_raster_row (outfd, inrast, data_type) < 0)
            G_fatal_error ("Cannot write to <%s>",result);

    }
    G_close_cell (outfd);

}

void parse_options(int argc, char* argv[]) {
    struct Option *input, *output, *o_dist, *o_freq;
    struct Option *o_limit;
    struct Option *o_dist_a, *o_dist_b, *o_seed, *o_agem;
    struct Flag *f_bool, *f_overwrite, *f_verbose, *f_check_zero;

    char buffer[64];

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

    o_dist = G_define_option() ;
    o_dist->key        = "kernel";
    o_dist->type       = TYPE_STRING;
    o_dist->required   = NO;
    o_dist->answer     = "cauchy";
    o_dist->options    = "cauchy,exponential,log,general";
    o_dist->description= "Distribution representing size of jump events";

    o_dist_a = G_define_option() ;
    o_dist_a->key        = "d_a";
    o_dist_a->type       = TYPE_DOUBLE;
    o_dist_a->required   = NO;
    o_dist_a->answer	 = "0.0";
    o_dist_a->description= "Parameter specifying parameter of distribution (a)";

    o_dist_b = G_define_option() ;
    o_dist_b->key        = "d_b";
    o_dist_b->type       = TYPE_DOUBLE;
    o_dist_b->required   = NO;
    o_dist_b->answer     = "1.0";
    o_dist_b->description= "Parameter specifying parameter of distribution (b)";

    o_freq = G_define_option() ;
    o_freq->key        = "frequency";
    o_freq->type       = TYPE_DOUBLE;
    o_freq->required   = NO;
    o_freq->answer     = "0.05";
    o_freq->description= "Frequency of jump events";

    o_limit = G_define_option() ;
    o_limit->key        = "limit";
    o_limit->type       = TYPE_DOUBLE;
    o_limit->required   = NO;
    o_limit->answer     = "0.0";
    o_limit->description= "Truncation distance. Events greater than this are discarded.";

    o_seed = G_define_option();
    o_seed->key        = "seed";
    o_seed->type       = TYPE_INTEGER;
    o_seed->required   = NO;
    snprintf(buffer, 64, "%d", (int) time(NULL));
    o_seed->answer     = buffer;
    o_seed->description= "Optional seed value for random number generator";

    o_agem = G_define_option() ;
    o_agem->key        = "agem";
    o_agem->type       = TYPE_INTEGER;
    o_agem->required   = NO;
    o_agem->answer     = "0";
    o_agem->description= "Age of maturity. Implies map values contain population age. \n"
	"Only cells > this value generate events.";

    /* Define the different flags */

    f_bool = G_define_flag() ;
    f_bool->key         = 'b' ;
    f_bool->description = "Boolean spread, cells are present/absent";
    f_bool->answer      = FALSE;

    f_overwrite = G_define_flag();
    f_overwrite->key    = 'o' ;
    f_overwrite->description = "Overwrite output file if it exists";
    f_overwrite->answer = FALSE;

    f_verbose = G_define_flag();
    f_verbose->key    = 'q' ;
    f_verbose->description = "Quiet";
    f_verbose->answer = FALSE;

    f_check_zero = G_define_flag();
    f_check_zero->key    = 'z' ;
    f_check_zero->description = "Explicitly check and ignore cell values that are zero.";
    f_check_zero->answer = FALSE;

    if (G_parser(argc, argv))
        exit (-1);

    name    = input->answer;
    result  = output->answer;
    is_boolean = f_bool->answer;
    is_overwrite = f_overwrite->answer;
    is_verbose = !(f_verbose->answer);
    maturity_age = atoi(o_agem->answer);
    if (f_check_zero->answer) check_zero = 1;

    if (o_dist_a->answer) dist_a = atof(o_dist_a->answer);
    if (o_dist_b->answer) dist_b = atof(o_dist_b->answer);
    if (o_freq->answer) freq = atof(o_freq->answer);
    if (o_limit->answer) truncation_limit = atof(o_limit->answer);
    if (o_seed->answer) {
        seed = atol(o_seed->answer);
#if defined(HAVE_DRAND48)
        srand48(seed);
#else
        srand((unsigned int) seed);
#endif
    }

    if (o_dist->answer) {
        if (G_strcasecmp(o_dist->answer, "cauchy") == 0) {
            distribution = CAUCHY;
        } else if (G_strcasecmp(o_dist->answer, "exponential") == 0) {
            distribution = EXPONENTIAL;
        } else if (G_strcasecmp(o_dist->answer, "log") == 0) {
            distribution = LOG;
        } else if (G_strcasecmp(o_dist->answer, "general") == 0) {
            distribution = GENERAL;
        }
    }
}

// Uses poisson dist to find number of jumps
int get_number_of_events(double p, double mu) {
    double sum = 0.0;
    double prob = 0.0;
    int count = 0;

    prob = sum = exp(-mu);

    if (sum == 0) {
        fprintf(stderr,"mean (%f) for poisson too large!\n", mu);
        exit(3);
    }

    while (p > sum) {
        count++;
        prob = (prob*mu)/count;
        sum += prob;
    }

    return count;
}
