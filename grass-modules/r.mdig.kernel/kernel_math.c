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
#include "stdio.h"
#include "stdlib.h"
#include "math.h"

#include "kernel_math.h"

/* 
 * Inverse cauchy is positive negative centred around 0, p = 0..1, b = shape.
 * */
//http://home.att.net/~numericana/answer/functions.htm#gamma

double inv_cauchy_cdf(double p, double a, double b)
{
	double r;
    r=b * tan((p-0.5)*M_PI);
	return r;
}

double inv_exponential_cdf(double p, double a, double b)
{
	double r;
	r = log(-p+1)*(-b);
	return r;
}

double int_clark(double x, double s, double d)
{
	double result;
	double ratio;
	double a, b, c;
	
	ratio = pow((x/d), s);
	
	a = pow(ratio, -1.0 / s);
	b = gsl_sf_gamma(1/s);
	c = gsl_sf_gamma_inc(1/s,ratio);
	
	result = x * a * (b - c) / s;
	
	return result;
	
}

// General kernel from Clark98
// Uses numeircal method seen in PestSpread, /mnt/unity/projects/pestspread/Modelling/Dll_Source/buffer.dpr
// uses Gnu Scientific library for gamma function but alternative is gamma_ln
double clark(double p, double d, double s)
{
	static int max_step = 0;
	static double _d = -1, _s = -1;
#define CLARK_STEPS 131072 //65536 //16384
	static int acum_limit = CLARK_STEPS;
	static double *acum;
	static double normal = 0;
	double kernel, step_width, result;
	
	int i;
	
	if (acum == NULL) {
		acum = malloc(sizeof(double) * acum_limit);
	}

	i=0;
	if (_d != d || _s != s) 
	{
		_d = d; _s = s;
		acum[i] = 0.0;
		max_step=0;
		normal = s / (d * gsl_sf_gamma(1.0 / s));
	}
	
	step_width = d * 0.005;
	
	while(acum[i] < p)
	{
		i++;
		if (i >= max_step)
		{
			if (p > 0.999999999 || max_step >= (8 * CLARK_STEPS-1)) {
				fprintf(stdout,"Limit for stepping clark pdf reached (p=%f,max_step=%d)\n",p,max_step);
				acum[i] = 1.0;
			} else {
				if (max_step >= acum_limit - 1)
				{
					int step;
					step = acum_limit / CLARK_STEPS;
					step++;
					acum_limit = step * CLARK_STEPS;
					acum = realloc(acum, sizeof(double) * acum_limit);
					//fprintf(stderr,"p=%f,max_step=%d\n",acum[i-1],max_step);
	
				}
				max_step++;
				kernel = normal * exp(-pow(((double)i-0.5) * step_width / d, s));
				acum[i] = acum[i-1] + (kernel * step_width);
				//fprintf(stderr,"p=%f,max_step=%d\n",acum[i],max_step);
							
			}
		}
	}
	
	result = step_width * (i - ((acum[i] - p) / (acum[i] - acum[i-1])));

	//static double clark_zero = 0;	
	// Integral doesn't seem to be working...
	//if (!clark_zero) clark_zero = int_clark(0.000000000001, shape, d);
	//result = int_clark(p, shape, d) - clark_zero;
	
	return result;
}

// Natural log of gamma function.. only for xx > 0. from Numerical recipes in C
double gamma_ln(double xx)
{
    static double cof[6]={76.18009172947146,-86.50532032941677,
         24.01409824083091,-1.231739572450155,
         0.1208650973866179e-2,-0.5395239384953e-5};
    static double lastxx=-1.0;
    static double lastresult=0.0;
    
    if (xx < 0) return -1;
    if (lastxx == xx) return lastresult;

	if (xx >= 0.5)
	{
		// Lanczos64 approximation for xx > 0.5
	    double a,b;
	    double tmpa,c0;
	    int j;
	    b=a=xx;
	    tmpa=a+5.5;
	    tmpa -= (a+0.5)*log(tmpa);
	    c0=1.000000000190015;
	    for (j=0;j<=5;j++) c0 += cof[j]/++b;
	    return -tmpa+log(2.5066282746310005*c0/a);
	} else if (xx == 0.5) {
		// Gamma(0.5) = square root of Pi
		return log( sqrt(M_PI) );		
	} else {
		// Reflection formula: G(z)G(1-z) = p/sin(pz) 
		return log( 5.0 / ( sin(5.0*xx) * exp( gamma_ln( 1 - xx ) )));
	}
}
