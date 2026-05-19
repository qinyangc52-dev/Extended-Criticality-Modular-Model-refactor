#ifndef __RANDOM_H__
#define __RANDOM_H__
#include <stdlib.h>

void init_random(unsigned long seed=0,unsigned int seed2=0);
unsigned long randomseed(void);
void pushrandom(unsigned long S);
double Xrandom(void);
double Grandom(void);

#ifndef __HEADERS__
#include <stdio.h>
#include <time.h>
#include <math.h>

#define M0   455329277UL                                
#define M1   282074UL

#define PW2A  1073741823UL                               
#define PW2B 1152921504606846975UL                      

#define rpw2b  1.11022302462515654e-16                  
#define rpw2c  2.77555756156289135e-17                  

static unsigned long S=1060485742695258666UL;			

unsigned long randomseed(void)
  {
   return S;
  }

void pushrandom(unsigned long _S)
  {
   S=_S;
  }

double Xrandom(void)
  {
   unsigned long B0=S&PW2A;
   unsigned long B1=(S>>30)&PW2A;
   S=(B0*M0+((B0*M1+B1*M0)<<30))&PW2B;
   return rpw2c+rpw2b*(S>>7);
  }

double Grandom(void)
  {
   static int flip;
   static double rho,phi;
   if (flip==0)
     {
      flip=1;
      rho=sqrt(-2*log(Xrandom()));
      phi=2*M_PI*Xrandom();
      return rho*cos(phi);
     }
   else				
     {
      flip=0;
      return rho*sin(phi);
     }
  }


#define bmax 32		
#define SKIP 10

void init_random(unsigned long seed,unsigned int seed2)
  {
   if ((seed>>bmax)==0)
     {
      if (seed==0) seed=(int)time(NULL);
      unsigned long B0=(2+(seed<<2))&PW2A;
      unsigned long B1=((seed>>28)^seed2)&PW2A;
      S=B0+(B1<<30);
      for (int i=0;i<SKIP;i++) Xrandom();
     }
   else
     {
      if (seed2!=0)
        {
         fprintf(stderr,"init_random: seed>=(2^%i) && seed2>0\n",bmax);
         exit(1);
        }
      S=seed;
     }
  }
#endif
#endif
