/****************************************************************************
 *
 * MODULE:       r.mdig.localspread
 * AUTHOR(S):    Joel Pitt
 * PURPOSE:      Spreads population radially according to spread rate.
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
#include <time.h>
#include <math.h>
#include <limits.h>

#include "grass/gis.h"

#include "is_present.h"

//#define DEBUG

int nrows, ncols;
void* in_rast;

void* spread_rast;
RASTER_MAP_TYPE data_type;
RASTER_MAP_TYPE sm_data_type;

int is_boolean;

unsigned int num_spread_cells;
unsigned int diameter, shape;
//! Indicates whether maps are to be interpreted as having population age
int age_based = 0;
int maturity_age, max_age;
double spread_proportion;
double spread;
int check_zero = -1;
//! stochastic spread indicates whether population spread should be weighted by
//! how close a cell in an age based model is to spreading.
enum { NONE = 0, LINEAR } stochastic_spread;
float ewres = 1;
float nsres = 1;

//! Defines the smallest fractional individual
//! count to spread - to prevent entire map filling with zeros.
//! @todo Make small_limit an commandline option
double small_limit = 0.001;

struct _output_row {
    void *outrast;
    struct _output_row* next;
    struct _output_row* prev;
};
typedef struct _output_row output_row;

long seed;
#if defined(HAVE_DRAND48)
    #define UNIFORM_RANDOM drand48()
#else
    #define UNIFORM_RANDOM ((double)rand()/RAND_MAX)
#endif

void print_row(output_row* p, int ncols)
{
    int i;
    for (i=0; i < ncols; i++) {
        if (G_is_c_null_value(((CELL*)p->outrast)+i))
            printf("- ");
        else
            printf("%u ", ((CELL*)p->outrast)[i]);
    }
    printf ("\n");
}

void print_rows(output_row* p, int ncols)
{
    print_row(p,ncols);
    while (p->next) {
        p = p->next;
        print_row(p,ncols);
    }
}

output_row* new_output_row(int cols, RASTER_MAP_TYPE data_type)
{
    output_row* a;
    a = G_malloc(sizeof(output_row));
    a->next = a->prev = NULL;
    a->outrast = G_allocate_raster_buf(data_type);
    G_set_null_value(a->outrast,ncols,data_type);
#ifdef DEBUG
    print_row(a,cols);
#endif
    return a;
}

// Get spread area, needed to disperse individuals
// across an area evenly
#ifdef DEBUG
#define WITHIN_DIAMETER float dist = sqrt((i*ewres)*(i*ewres) + (j*nsres)*(j*nsres) ); printf("%.2f,",dist); if (dist <= radius) { count++; found = 1; }
#else
#define WITHIN_DIAMETER float dist = sqrt((i*ewres)*(i*ewres) + (j*nsres)*(j*nsres) ); if (dist <= radius) { count++; found = 1; }
#endif
int get_spread_area(int radius) {
    // TODO: this is inefficient, maybe calculate area using
    // pi( (d/nsres + d/ewres) / 2 )^2
    int i, j;
    // current border
    int c;
    // count of cells to spread to
    int count = 0;
    // set to false when search space exhausted
    int found = 1;

    // start by looking at surrounding cells
    c=1;

    while (found) {
        // new cells found?
        found = 0;
        // Traverse boundary
        j = -c;
        for (i=-c; i <= c; i++ ) {
            WITHIN_DIAMETER
        }
        j = c;
        for (i=-c; i <= c; i++ ) {
            WITHIN_DIAMETER
        }
        i=-c;
        for (j=-(c-1); j <= (c-1); j++ ) {
            WITHIN_DIAMETER
        }
        i=c;
        for (j=-(c-1); j <= (c-1); j++ ) {
            WITHIN_DIAMETER
        }
        c++;
    }
    count--; // Don't include source
#ifdef DEBUG
    printf("r=%d,count=%d\n", radius, count);
#endif
    return count;

}

double get_spread_from_map(void* rast, int col)
{
    double value = 0.0;
    switch (sm_data_type) {
    case CELL_TYPE:
        if (!G_is_null_value(rast + (col*sizeof(CELL)), CELL_TYPE))
            value = (double) ((CELL*) rast)[col];
        break;
    case FCELL_TYPE:
        if (!G_is_null_value(rast + (col*sizeof(FCELL)), FCELL_TYPE))
            value = (double) ((FCELL*) rast)[col];
        break;
    case DCELL_TYPE:
        if (!G_is_null_value(rast + (col*sizeof(DCELL)), DCELL_TYPE))
            value = (double) ((DCELL*) rast)[col];
        break;
    }

    return value;
}

void c_calc(CELL* x, output_row* out, double spread_value, int col)
{
    CELL c;
    int i, j;
    unsigned int individuals = 0;
    unsigned int mean_individuals = 0;
    unsigned int extra_individuals = 0;
    //! chance of spread to any given cell in spread_value distance. Only
    //! changed if sub res spread and stochastic spread is enabled.
    double spread_chance = 1.0;
    double diagonal_spread_chance = 1.0;
    int position;

    num_spread_cells = get_spread_area(spread_value);

    c = ((CELL *) x)[col];

    if (is_boolean) {
        mean_individuals = 1;
        c = 1;
    } else if (age_based) {
        if (c >= maturity_age && c <= max_age) {
            double max_res;
            double diagonal_dist; 
            diagonal_dist = sqrt(ewres*ewres + nsres*nsres);
            max_res = (ewres > nsres)? ewres : nsres;
            mean_individuals = 0;
            // if spread_value isn't enough to spread in one year
            // allow it to spread to neighbouring cells if it's been in a source
            // cell long enough...
            if ( ((int) (spread_value / max_res)) == 0 ) {
                spread_value = (c - maturity_age) * spread_value;
                switch (stochastic_spread) {
                case NONE:
                    if ( spread_value > max_res ) {
                    //spread_value = (int) max_res + 1;
                    // num_spread_cells = get_spread_area(spread_value);
                    mean_individuals = 1;
                    // limit the spread to no further than one cell 
                    if (spread_value < diagonal_dist)
                        diagonal_spread_chance = 0.0;
                    spread_value = (int) max_res;
#ifdef DEBUG
                    printf("res %.2f, c %d, num_cells = %d, spread value = %.2f\n",
                        max_res, c, num_spread_cells, spread_value);
#endif
                    }
                    break;
                case LINEAR:
                    mean_individuals = 1;
                    if ( spread_value - max_res < 0 ) {
                    spread_chance = (float) (spread_value / max_res);
                    diagonal_spread_chance = (float) (spread_value
                        / diagonal_dist);
                    // even though we not not spread to all cells,
                    // we have to set the spread_value so that all those
                    // cells are processed and at least get a chance to be
                    // spread.
                    spread_value = (int) max_res;
#ifdef DEBUG
                    printf("p %.2f, dp %.2f, res %.2f, c %d, num_cells = %d, spread value = %.2f\n",
                        spread_chance, diagonal_spread_chance, max_res, c, num_spread_cells, spread_value);
#endif
                    }
                    break;
                }
            } else {
                mean_individuals = 1;
            }
        }
    } else {
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

    if (mean_individuals) {
        output_row* f_row;
        int r = 0;

        f_row = out;
        
        // go back as many output rows as necessary to get the
        // furthest possible for spread.
        while (r <= (spread_value / nsres)) {
            if (!f_row->prev) break;
            f_row = f_row->prev;
            r++;
        }
        // f_row is now r rows above the current row being processed.
#ifdef DEBUG
        printf("spread_value = %.2f, r = %d\n",spread_value,r);
        printf("i=%d, max = %d, ", -r, (int) (spread_value/nsres));
#endif
        // move from r rows back, through current row, to future rows within spread_value
        for (i=-r; i <= (int) (spread_value/nsres); i++) {
            for (j=-(int)(spread_value/ewres); j <= (int) (spread_value/ewres); j++) {
                double ns_d, ew_d, temp_spread_value;
                if (i == 0 && j == 0) continue;
                ns_d = (i*nsres);
                ew_d = (j*ewres);
                ns_d *= ns_d;
                ew_d *= ew_d;
                temp_spread_value = spread_value;

                // For stochastic spread:
                if ((i == 0 || j == 0) && spread_chance < 1.0) {
                    double p2 = UNIFORM_RANDOM;
                    if (p2 <= spread_chance) {
                    if (i == 0)
                        temp_spread_value = (int) ewres + 1;
                    else // (j == 0)
                        temp_spread_value = (int) nsres + 1;
                    } else {
                    temp_spread_value = 0;
                    }
                } else if (diagonal_spread_chance < 1.0) {
                    double p2 = UNIFORM_RANDOM;
                    if (p2 <= diagonal_spread_chance) {
                    temp_spread_value = (int) sqrt(ns_d + ew_d) + 1;
                    } else {
                    temp_spread_value = 0;
                    }
                }
                // if cell within spread_value
                if (sqrt(ns_d + ew_d) <= temp_spread_value) {
#ifdef DEBUG
                    printf("d=%.f < spread value\n",sqrt(ns_d + ew_d));
#endif
                    position = col+j;
                    // Check we are not outside the boundary of the region
                    if ((position >= 0 ) && (position < ncols )) {
#ifdef DEBUG
                        printf("in bounds\n");
#endif
                        if (is_boolean) {
                            ((CELL*) f_row->outrast)[position] = (CELL) 1;
                        } else if (age_based) {
                            if (G_is_c_null_value(((CELL*)f_row->outrast) + position))
                                ((CELL*) f_row->outrast)[position] = (CELL) 1;
                        } else {
                            if (G_is_c_null_value(((CELL*)f_row->outrast) + position))
                                ((CELL*) f_row->outrast)[position] = mean_individuals;
                            else
                                ((CELL*) f_row->outrast)[position] += mean_individuals;
                        }
                    }
                }
            }
            // move output row fwd only if not the last row
            if (i <= spread_value/nsres) {
                if (!f_row->next) {
                    f_row->next = new_output_row(ncols,data_type);
                    f_row->next->prev = f_row;
                }
                f_row = f_row->next;
            }
#ifdef DEBUG
            printf("\n");
#endif

        }
        position = col;
        if (is_boolean) {
            ((CELL*) out->outrast)[position] = (CELL) 1;
        } else if (age_based) {
            ((CELL*) out->outrast)[col] = c;
        } else {
            if (G_is_c_null_value(((CELL*)out->outrast) + position))
                ((CELL*) out->outrast)[position] = c + extra_individuals;
            else
                ((CELL*) out->outrast)[position] += c + extra_individuals;
        }
    } else {
        position = col;

        if (is_boolean) {
            ((CELL*) out->outrast)[position] = (CELL) 1;
        } else if (age_based) {
            ((CELL*) out->outrast)[col] = c;
        } else {
            if (G_is_c_null_value(((CELL*)out->outrast) + position))
                ((CELL*) out->outrast)[position] = c + individuals;
            else
                ((CELL*) out->outrast)[position] += c + individuals;
        }
    }
#ifdef DEBUG
    printf("\n");
#endif
}

void f_calc(FCELL* x, output_row* out, double spread_value, int col)
{
    FCELL c;
    int i, j;
    unsigned int individuals = 0;
    unsigned int mean_individuals = 0;
    unsigned int extra_individuals = 0;
    //! chance of spread to any given cell in spread_value distance. Only
    //! changed if sub res spread and stochastic spread is enabled.
    double spread_chance = 1.0;
    double diagonal_spread_chance = 1.0;
    int position;

    num_spread_cells = get_spread_area(spread_value);

    c = ((FCELL *) x)[col];

    if (is_boolean) {
        mean_individuals = 1;
        c = 1;
    } else if (age_based) {
        if (c >= maturity_age && c <= max_age) {
        double max_res;
        double diagonal_dist; 
        diagonal_dist = sqrt(ewres*ewres + nsres*nsres);
        max_res = (ewres > nsres)? ewres : nsres;
        mean_individuals = 0;
        // if spread_value isn't enough to spread in one year
        // allow it to spread to neighbouring cells if it's been in a source
        // cell long enough...
        if ( ((int) (spread_value / max_res)) == 0 ) {
        spread_value = (c - maturity_age) * spread_value;
        switch (stochastic_spread) {
        case NONE:
            if ( spread_value > max_res ) {
            //spread_value = (int) max_res + 1;
            // num_spread_cells = get_spread_area(spread_value);
            mean_individuals = 1;
            // limit the spread to no further than one cell 
            if (spread_value < diagonal_dist)
                diagonal_spread_chance = 0.0;
            spread_value = (int) max_res;
#ifdef DEBUG
            printf("res %.2f, c %d, num_cells = %d, spread value = %.2f\n",
                max_res, c, num_spread_cells, spread_value);
#endif
            }
            break;
        case LINEAR:
            mean_individuals = 1;
            if ( spread_value - max_res < 0 ) {
            spread_chance = (float) (spread_value / max_res);
            diagonal_spread_chance = (float) (spread_value
                / diagonal_dist);
            // even though we not not spread to all cells,
            // we have to set the spread_value so that all those
            // cells are processed and at least get a chance to be
            // spread.
            spread_value = (int) max_res;
#ifdef DEBUG
            printf("p %.2f, dp %.2f, res %.2f, c %d, num_cells = %d, spread value = %.2f\n",
                spread_chance, diagonal_spread_chance, max_res, c, num_spread_cells, spread_value);
#endif
            }
            break;
        }
        } else {
        mean_individuals = 1;
        }
    }
    } else {
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

    if (mean_individuals) {
    output_row* f_row;
    int r = 0;

    f_row = out;
    
    // go back as many output rows as necessary to get the
    // furthest possible for spread.
    while (r <= (spread_value / nsres)) {
        if (!f_row->prev) break;
        f_row = f_row->prev;
        r++;
    }
    // f_row is now r rows above the current row being processed.
#ifdef DEBUG
    printf("spread_value = %.2f, r = %d\n",spread_value,r);
    printf("i=%d, max = %d, ", -r, (int) (spread_value/nsres));
#endif
    // move from r rows back, through current row, to future rows within spread_value
    for (i=-r; i <= (int) (spread_value/nsres); i++) {
        for (j=-(int)(spread_value/ewres); j <= (int) (spread_value/ewres); j++) {
        double ns_d, ew_d, temp_spread_value;
        if (i == 0 && j == 0) continue;
        ns_d = (i*nsres);
        ew_d = (j*ewres);
        ns_d *= ns_d;
        ew_d *= ew_d;
        temp_spread_value = spread_value;

        // For stochastic spread:
        if ((i == 0 || j == 0) && spread_chance < 1.0) {
            double p2 = UNIFORM_RANDOM;
            if (p2 <= spread_chance) {
            if (i == 0)
                temp_spread_value = (int) ewres + 1;
            else // (j == 0)
                temp_spread_value = (int) nsres + 1;
            } else {
            temp_spread_value = 0;
            }
        } else if (diagonal_spread_chance < 1.0) {
            double p2 = UNIFORM_RANDOM;
            if (p2 <= diagonal_spread_chance) {
            temp_spread_value = (int) sqrt(ns_d + ew_d) + 1;
            } else {
            temp_spread_value = 0;
            }
        }
        // if cell within spread_value
        if (sqrt(ns_d + ew_d) <= temp_spread_value) {
#ifdef DEBUG
            printf("d=%.f < spread value\n",sqrt(ns_d + ew_d));
#endif
            position = col+j;
                    // Check we are not outside the boundary of the region
                    if ((position >= 0 ) && (position < ncols )) {
#ifdef DEBUG
            printf("in bounds\n");
#endif
                        if (is_boolean) {
                            ((FCELL*) f_row->outrast)[position] = (FCELL) 1;
            } else if (age_based) {
                            if (G_is_f_null_value(((FCELL*)f_row->outrast) + position))
                ((FCELL*) f_row->outrast)[position] = (FCELL) 1;
            } else {
                            if (G_is_f_null_value(((FCELL*)f_row->outrast) + position))
                                ((FCELL*) f_row->outrast)[position] = mean_individuals;
                            else
                                ((FCELL*) f_row->outrast)[position] += mean_individuals;
            }
            }

        }
        }
        // move output row fwd only if not the last row
        if (i <= spread_value/nsres) {
        if (!f_row->next) {
            f_row->next = new_output_row(ncols,data_type);
            f_row->next->prev = f_row;
        }
        f_row = f_row->next;

        }

#ifdef DEBUG
        printf("\n");
#endif

    }
        position = col;
        if (is_boolean) {
            ((FCELL*) out->outrast)[position] = (FCELL) 1;
    } else if (age_based) {
        ((FCELL*) out->outrast)[col] = c;
    } else {
            if (G_is_f_null_value(((FCELL*)out->outrast) + position))
                ((FCELL*) out->outrast)[position] = c + extra_individuals;
            else
                ((FCELL*) out->outrast)[position] += c + extra_individuals;
    }
    } else {
        position = col;

        if (is_boolean) {
            ((FCELL*) out->outrast)[position] = (FCELL) 1;
    } else if (age_based) {
        ((FCELL*) out->outrast)[col] = c;
    } else {
            if (G_is_f_null_value(((FCELL*)out->outrast) + position))
                ((FCELL*) out->outrast)[position] = c + individuals;
            else
                ((FCELL*) out->outrast)[position] += c + individuals;
    }
    }

#ifdef DEBUG
    printf("\n");
#endif
}

void d_calc(DCELL* x, output_row* out, double spread_value, int col)
{
    DCELL c;
    int i, j;
    unsigned int individuals = 0;
    unsigned int mean_individuals = 0;
    unsigned int extra_individuals = 0;
    //! chance of spread to any given cell in spread_value distance. Only
    //! changed if sub res spread and stochastic spread is enabled.
    double spread_chance = 1.0;
    double diagonal_spread_chance = 1.0;
    int position;

    num_spread_cells = get_spread_area(spread_value);

    c = ((DCELL *) x)[col];

    if (is_boolean) {
        mean_individuals = 1;
        c = 1;
    } else if (age_based) {
        if (c >= maturity_age && c <= max_age) {
        double max_res;
        double diagonal_dist; 
        diagonal_dist = sqrt(ewres*ewres + nsres*nsres);
        max_res = (ewres > nsres)? ewres : nsres;
        mean_individuals = 0;
        // if spread_value isn't enough to spread in one year
        // allow it to spread to neighbouring cells if it's been in a source
        // cell long enough...
        if ( ((int) (spread_value / max_res)) == 0 ) {
        spread_value = (c - maturity_age) * spread_value;
        switch (stochastic_spread) {
        case NONE:
            if ( spread_value > max_res ) {
            //spread_value = (int) max_res + 1;
            // num_spread_cells = get_spread_area(spread_value);
            mean_individuals = 1;
            // limit the spread to no further than one cell 
            if (spread_value < diagonal_dist)
                diagonal_spread_chance = 0.0;
            spread_value = (int) max_res;
#ifdef DEBUG
            printf("res %.2f, c %d, num_cells = %d, spread value = %.2f\n",
                max_res, c, num_spread_cells, spread_value);
#endif
            }
            break;
        case LINEAR:
            mean_individuals = 1;
            if ( spread_value - max_res < 0 ) {
            spread_chance = (float) (spread_value / max_res);
            diagonal_spread_chance = (float) (spread_value
                / diagonal_dist);
            // even though we not not spread to all cells,
            // we have to set the spread_value so that all those
            // cells are processed and at least get a chance to be
            // spread.
            spread_value = (int) max_res;
#ifdef DEBUG
            printf("p %.2f, dp %.2f, res %.2f, c %d, num_cells = %d, spread value = %.2f\n",
                spread_chance, diagonal_spread_chance, max_res, c, num_spread_cells, spread_value);
#endif
            }
            break;
        }
        } else {
        mean_individuals = 1;
        }
    }
    } else {
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

    if (mean_individuals) {
    output_row* f_row;
    int r = 0;

    f_row = out;
    
    // go back as many output rows as necessary to get the
    // furthest possible for spread.
    while (r <= (spread_value / nsres)) {
        if (!f_row->prev) break;
        f_row = f_row->prev;
        r++;
    }
    // f_row is now r rows above the current row being processed.
#ifdef DEBUG
    printf("spread_value = %.2f, r = %d\n",spread_value,r);
    printf("i=%d, max = %d, ", -r, (int) (spread_value/nsres));
#endif
    // move from r rows back, through current row, to future rows within spread_value
    for (i=-r; i <= (int) (spread_value/nsres); i++) {
        for (j=-(int)(spread_value/ewres); j <= (int) (spread_value/ewres); j++) {
        double ns_d, ew_d, temp_spread_value;
        if (i == 0 && j == 0) continue;
        ns_d = (i*nsres);
        ew_d = (j*ewres);
        ns_d *= ns_d;
        ew_d *= ew_d;
        temp_spread_value = spread_value;

        // For stochastic spread:
        if ((i == 0 || j == 0) && spread_chance < 1.0) {
            double p2 = UNIFORM_RANDOM;
            if (p2 <= spread_chance) {
            if (i == 0)
                temp_spread_value = (int) ewres + 1;
            else // (j == 0)
                temp_spread_value = (int) nsres + 1;
            } else {
            temp_spread_value = 0;
            }
        } else if (diagonal_spread_chance < 1.0) {
            double p2 = UNIFORM_RANDOM;
            if (p2 <= diagonal_spread_chance) {
            temp_spread_value = (int) sqrt(ns_d + ew_d) + 1;
            } else {
            temp_spread_value = 0;
            }
        }
        // if cell within spread_value
        if (sqrt(ns_d + ew_d) <= temp_spread_value) {
#ifdef DEBUG
            printf("d=%.f < spread value\n",sqrt(ns_d + ew_d));
#endif
            position = col+j;
                    // Check we are not outside the boundary of the region
                    if ((position >= 0 ) && (position < ncols )) {
#ifdef DEBUG
            printf("in bounds\n");
#endif
                        if (is_boolean) {
                            ((DCELL*) f_row->outrast)[position] = (DCELL) 1;
            } else if (age_based) {
                            if (G_is_d_null_value(((DCELL*)f_row->outrast) + position))
                ((DCELL*) f_row->outrast)[position] = (DCELL) 1;
            } else {
                            if (G_is_d_null_value(((DCELL*)f_row->outrast) + position))
                                ((DCELL*) f_row->outrast)[position] = mean_individuals;
                            else
                                ((DCELL*) f_row->outrast)[position] += mean_individuals;
            }
            }

        }
        }
        // move output row fwd only if not the last row
        if (i <= spread_value/nsres) {
        if (!f_row->next) {
            f_row->next = new_output_row(ncols,data_type);
            f_row->next->prev = f_row;
        }
        f_row = f_row->next;

        }

#ifdef DEBUG
        printf("\n");
#endif

    }
        position = col;
        if (is_boolean) {
            ((DCELL*) out->outrast)[position] = (DCELL) 1;
    } else if (age_based) {
        ((DCELL*) out->outrast)[col] = c;
    } else {
            if (G_is_d_null_value(((DCELL*)out->outrast) + position))
                ((DCELL*) out->outrast)[position] = c + extra_individuals;
            else
                ((DCELL*) out->outrast)[position] += c + extra_individuals;
    }
    } else {
        position = col;

        if (is_boolean) {
            ((DCELL*) out->outrast)[position] = (DCELL) 1;
    } else if (age_based) {
        ((DCELL*) out->outrast)[col] = c;
    } else {
            if (G_is_d_null_value(((DCELL*)out->outrast) + position))
                ((DCELL*) out->outrast)[position] = c + individuals;
            else
                ((DCELL*) out->outrast)[position] += c + individuals;
    }
    }

#ifdef DEBUG
    printf("\n");
#endif
}

int main(int argc, char *argv[]) {
    struct Cell_head active_cellhd, in_cellhd, sm_cellhd;
    char *name, *result, *mapset;

    char *spread_map;
    char *spread_mapset;

    char *out_mapset;
    output_row* start_row, *current_row;
    output_row* i_row;

    char buffer[64];

    char rname[256], rmapset[256];
    char buff[1024];
    int is_reclass;
    int (*is_present)(void*, int) = NULL;

    int row,col;
    int infd, outfd, smfd = 0;
    //int i;

    struct GModule *module;
    struct Option *input, *output;
    struct Option *n_maturity_age, *n_max_age, *n_spread, *n_proportion;
    struct Option *n_seed;
    struct Flag *f_bool, *f_overwrite, *f_check_zero, *f_stochastic;

    G_gisinit(argv[0]);

    module = G_define_module();
    module->description =
        "Local spread to neighbouring cells based on a specified spread rate,"
    "or based on raster map with spread rates for each cell.";

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

    n_spread = G_define_option() ;
    n_spread->key        = "spread";
    n_spread->type       = TYPE_STRING;
    n_spread->required   = YES;
    n_spread->description= "Spread in metres (or name of a map with spread values)";

    n_proportion = G_define_option() ;
    n_proportion->key        = "proportion";
    n_proportion->type       = TYPE_DOUBLE;
    n_proportion->required   = NO;
    n_proportion->answer     = "1.0";
    n_proportion->description= "Proportion of individuals to spread from destination cell";

    n_maturity_age = G_define_option() ;
    n_maturity_age->key        = "agem";
    n_maturity_age->type       = TYPE_INTEGER;
    n_maturity_age->required   = NO;
    n_maturity_age->answer     = "-1";
    n_maturity_age->description= "Age of maturity. Implies map values contain population age. "
    "Only cells >= this value spread. New populations have age 1. -1 indicates that cells"
    " do not contain population age.";

    n_max_age = G_define_option() ;
    n_max_age->key        = "agemax";
    n_max_age->type       = TYPE_INTEGER;
    n_max_age->required   = NO;
    n_max_age->answer     = "-1";
    n_max_age->description= "Max age for spread. Implies map values contain population age. "
    "Only cells <= this value spread. New populations have age 1. -1 indicates that cells"
    " do not contain population age.";

    n_seed = G_define_option();
    n_seed->key        = "seed";
    n_seed->type       = TYPE_INTEGER;
    n_seed->required   = NO;
    snprintf(buffer, 64, "%d", (int) time(NULL));
    n_seed->answer     = buffer;
    n_seed->description= "Optional seed value for random number generator";

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

    f_stochastic = G_define_flag();
    f_stochastic->key    = 's' ;
    f_stochastic->description = "Stochastically spread.";
    f_stochastic->answer = FALSE;

    if (G_parser(argc, argv))
        exit (-1);

    name    = input->answer;
    result  = output->answer;

    // Determine whether this is *actually* a map or just a value later.
    spread_map = n_spread->answer;

    spread_proportion = atof(n_proportion->answer);

    // Work out whether maps are expected to contain age of population
    maturity_age = atoi(n_maturity_age->answer);
    max_age = atoi(n_max_age->answer);
    age_based = 0;
    if (maturity_age == -1) {
        maturity_age = 0;
    } else {
        age_based = 1;
    }
    if (max_age == -1) {
        max_age = INT_MAX;
    } else {
        age_based = 1;
    }
    
    is_boolean = (f_bool->answer);
    // check that options make sense
    if (is_boolean && age_based)
        G_fatal_error ("Options inconsistent (age specified and boolean specified)");

    if (f_stochastic->answer) stochastic_spread = LINEAR;
    if (f_check_zero->answer) check_zero=1;
    else check_zero = 0;

    if (n_seed->answer) {
        seed = atol(n_seed->answer);
#if defined(HAVE_DRAND48)
        srand48(seed);
#else
        srand((unsigned int) seed);
#endif
    }

    // check output name is legal
    if (G_legal_filename (result) < 0)
        G_fatal_error ("[%s] is an illegal name", result);

    // find input map in mapset
    mapset = G_find_cell2 (name, "");
    if (mapset == NULL)
        G_fatal_error ("cell file [%s] not found", name);

    // determine the inputmap type (CELL/FCELL/DCELL)
    data_type = G_raster_map_type(name, mapset);

    // open input map
    if ( (infd = G_open_cell_old (name, mapset)) < 0)
        G_fatal_error ("Cannot open cell file [%s]", name);

    // read the input map header
    if (G_get_cellhd (name, mapset, &in_cellhd) < 0)
        G_fatal_error ("Cannot read file header of [%s]", name);

    // Allocate input buffer
    in_rast = G_allocate_raster_buf(data_type);

    // check if map is a reclass
    is_reclass = (G_is_reclass (name, mapset, rname, rmapset) > 0);
    sprintf(buff, "cell_misc/%s", name);
    // If check_zero is -1 then it hasn't been set through a command-line option
    if (check_zero == -1 && (!G_find_file(buff, "null", mapset) || is_reclass))
        check_zero=1;
    else
        check_zero=0;

    // check if a map or value was given for the spread rate
    //--
    // find spread map in mapset
    spread_mapset = G_find_cell2 (spread_map, "");
    if (spread_mapset == NULL) {
        // G_warning("cell file [%s] not found", spread_map);
        // map not found, so try to convert the string to a float
        spread = atof(spread_map);
        if (spread <=0) {
            G_fatal_error ("Invalid spread rate");
        }
        printf("spread rate %f\n", spread);
    } else {
        // map found

        // determine the spread map type (CELL/FCELL/DCELL)
        sm_data_type = G_raster_map_type(spread_map, spread_mapset);

        // open spread map
        if ( (smfd = G_open_cell_old (spread_map, spread_mapset)) < 0)
            G_fatal_error ("Cannot open cell file [%s]", spread_map);

        // read the spread map header
        if (G_get_cellhd (spread_map, spread_mapset, &sm_cellhd) < 0)
            G_fatal_error ("Cannot read file header of [%s]", spread_map);

        // allocate spread row buffer
        spread_rast = G_allocate_raster_buf(sm_data_type);
    }
    
    // get active region settings
    G_get_set_window(&active_cellhd);

    nrows = G_window_rows();
    ncols = G_window_cols();

    nsres = active_cellhd.ns_res;
    ewres = active_cellhd.ew_res;
#ifdef DEBUG
    printf("%d rows, %d cols, nsres %.2f, ewres %.2f\n", nrows, ncols, nsres, ewres);
#endif
    
    // Allocate initial output row buffer, using input map data type
    start_row = current_row = new_output_row(ncols,data_type);

    // Open output file

    // Check for existing map and remove if overwrite flag is on
    out_mapset = G_find_cell2 (result, mapset);
    if ( out_mapset != NULL ) {
        if (f_overwrite->answer == TRUE) {
            char buffer[512];
        int r;
            sprintf(buffer, "g.remove rast=%s > /dev/null", result);
            r = system(buffer);

        } else {
            G_fatal_error ("Output map <%s> exists (use -o flag to force"
                           " overwrite)",result);
        }
    }
    if ( (outfd = G_open_raster_new (result, data_type)) < 0)
        G_fatal_error ("Couldn't create new raster <%s>",result);

    // set the appropriate function for checking if a cell is present
    // or not based on check_zero option and data_type
    is_present = IS_PRESENT(data_type,check_zero);

    for (row = 0; row < nrows; row++) {
        G_percent (row, nrows, 2);

#ifdef DEBUG
        printf("Row %d\n", row);
#endif
        // read input map
        if (G_get_raster_row (infd, in_rast, row, data_type) < 0)
            G_fatal_error ("Could not read from <%s>",name);

        // read spread map
        if (spread_rast) {
            if (G_get_raster_row (smfd, spread_rast, row, sm_data_type) < 0)
            G_fatal_error ("Could not read from <%s>",name);
        }

        switch (data_type) {
        case CELL_TYPE:
            // process the data
            for (col=0; col < ncols; col++) {
                if (is_present(in_rast,col)) {
                    // work out spread amount, either from map or cmd line
                    // if map:
                    if (spread_rast)
                        spread = get_spread_from_map(spread_rast,col);
#ifdef DEBUG
                    printf("col %d\n", col);
#endif
                    c_calc((CELL *)in_rast,current_row,spread,col);
                }
            }
            break;
        case FCELL_TYPE:
            // process the data
            for (col=0; col < ncols; col++) {
                if (is_present(in_rast,col)) {
                    // work out spread amount, either from map or cmd line
                    // if map:
                    if (spread_rast)
                        spread = get_spread_from_map(spread_rast,col);

                    f_calc((FCELL *)in_rast,current_row,spread,col);
                }
            }
            break;
        case DCELL_TYPE:
            // process the data
            for (col=0; col < ncols; col++) {
                if (is_present(in_rast,col)) {
                    // work out spread amount, either from map or cmd line
                    // if map:
                    if (spread_rast)
                        spread = get_spread_from_map(spread_rast,col);

                    d_calc((DCELL*)in_rast,current_row,spread,col);
                }
            }
            break;
        }

#ifdef DEBUG
        print_rows(start_row,ncols);
#endif
        if (!current_row->next) {
            current_row->next = new_output_row(ncols,data_type);
            current_row->next->prev = current_row;
        }
        current_row = current_row->next;


        // Once the output buffer row is no longer needed...
        //if (row > (spread - 1)) {
        //  if (G_put_raster_row (outfd, outrast[0], data_type) < 0)
        //    G_fatal_error ("Cannot write to <%s>",result);
        //}

        // G_set_null_value(outrast[0],ncols,data_type);

        // outrast[diameter] = outrast[0];

        // for ( i=0; i < (diameter-1); i++) {
        //    outrast[i] = outrast[i+1];
        //}
        //outrast[diameter-1] = outrast[diameter];

    }
    for ( i_row = start_row; i_row; i_row = i_row->next) {
#ifdef DEBUG
        printf("saving row\n");
#endif
        if (G_put_raster_row (outfd, i_row->outrast, data_type) < 0)
            G_fatal_error ("Cannot write to <%s>",result);
        G_free( i_row->outrast );
        if ( i_row->prev ) {
            G_free( i_row->prev );
            i_row->prev = NULL;
        }
    }

    /* DIsabled because glibc throws a spaz
        G_free(in_rast);
        for ( i=0; i <= diameter; i++)
        {
            G_free(outrast[i]);
        }
        G_free(outrast);*/


    G_close_cell (infd);
    G_close_cell (outfd);
    if (smfd) G_close_cell (smfd);

    return 0;
}
