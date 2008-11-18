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
#ifndef KERNEL_MATH_H_
#define KERNEL_MATH_H_

#include <gsl/gsl_sf_gamma.h>

// Probability Distributions
double inv_cauchy_cdf(double p, double a, double b);
double inv_exponential_cdf(double p, double a, double b);

double clark(double p, double d, double shape);
double gamma_ln(double xx);

#endif /*KERNEL_MATH_H_*/
