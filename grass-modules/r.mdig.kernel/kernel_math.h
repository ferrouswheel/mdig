#ifndef KERNEL_MATH_H_
#define KERNEL_MATH_H_

#include <gsl/gsl_sf_gamma.h>

// Probability Distributions
double inv_cauchy_cdf(double p, double a, double b);
double inv_exponential_cdf(double p, double a, double b);

double clark(double p, double d, double shape);
double gamma_ln(double xx);

#endif /*KERNEL_MATH_H_*/
