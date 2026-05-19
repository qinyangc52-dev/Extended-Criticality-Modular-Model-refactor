#ifndef __NEURONI_H__
#define __NEURONI_H__
#include <stdlib.h>

class neuroni
  {
   public:
   neuroni(int N,double **J,int mcue=0,int *wcue=NULL,double *tcue=NULL);
   int dinamica(double bin);

   int N;
   double **J;

   int noise;
   double alpha;
   double rho;
   double sigma;
   double delta;
   double dsdt;

   double *A;
   double *B;
   double *theta;
   double um;

   int size;		
   int maxsize;
   int *who;		
   double *times;	
   int count;			
   
   double prossimaspike(int i);
   void timestep(double tnext);
   void nextevent(double tmax,int *imin,int *flag);

   int mcue;
   int *wcue;
   double *tcue;
   int m;

   double tnoise;
   double tnow;
  };

#ifndef __HEADERS__
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>
#include <limits.h>
#define __HEADERS__
#include "getmem.c"
#include "getarg.c"
#include "random.c"
#include "hpsort.c"

#define TBIG 1e30

neuroni::neuroni(int _N,double **_J,int _mcue,int *_wcue,double *_tcue)
  {
   N=_N;
   J=_J;
   noise=getarg_i("noise",0,"0: rumore gaussiano, 1: rumore costante");
   alpha=getarg_d("alpha",1,"ampiezza rumore");
   if (alpha>0) rho=getarg_d("rho",1,"rate rumore (ms^-1)"); else rho=0;
   sigma=getarg_d("sigma",1,"forza connessioni eccitatorie (E0)");              
   dsdt=0;                                                              
   delta=getarg_d("delta",0,"forza connessioni inibitorie (I0)");            
   A=dvector(0,N-1);
   B=dvector(0,N-1);
   theta=dvector(0,N-1);
   um=10;						
   for (int i=0;i<N;i++)
     {
      A[i]=B[i]=0;
      theta[i]=1;
     }
   if (rho>0) tnoise=-log(Xrandom())/(N*rho); else tnoise=TBIG;
   tnow=0;
   int seed4=getarg_i("seed4",0);
   if (seed4>0) init_random(seed4);
   mcue=_mcue;
   wcue=_wcue;
   tcue=_tcue;
   hpsort3(mcue,tcue-1,wcue-1);
   m=0;
   maxsize=1<<25;
   size=0;
   who=NULL;
   times=NULL;
   count=0;
  }

double neuroni::prossimaspike(int i)
  {
   double tspike=TBIG;
   double atmp=A[i];
   double btmp=B[i];
   if (atmp-btmp<theta[i])
     {
      if (atmp>0 && btmp>0) 
        {
         double dtmp=atmp*atmp-4*btmp*theta[i];
         if (dtmp>0)
           {
            double xtmp=(atmp+sqrt(dtmp))/(2*btmp);
            if (xtmp<1) tspike=-um*log(xtmp);
           }
        }
     }
   else tspike=0;
   return tspike;
  }

void neuroni::timestep(double tnext)
  {
   sigma+=dsdt*(tnext-tnow);
   double fxa=exp(-(tnext-tnow)/um);
   double fxb=fxa*fxa;
   for (int j=0;j<N;j++)
     {
      A[j]=A[j]*fxa;
      B[j]=B[j]*fxb;
     }
   tnow=tnext;
  }

void neuroni::nextevent(double tmax,int *imin,int *flag)
  {
   double tmin=TBIG;
   for (int i=0;i<N;i++)
     {
      double tnext=tnow+prossimaspike(i);
      if (tnext<tmin)
        {
         tmin=tnext;
         *imin=i;
        }
     }
   *flag=0;
   if (m<mcue && tcue[m]<tmin)
     {
      tmin=tcue[m];
      *imin=wcue[m];
      *flag=1;
     }
   if (tnoise<tmin && tnoise<tmax)
     {
      timestep(tnoise);
      int i=(int)floor(N*Xrandom());
      double jtmp=(noise==0?alpha*Grandom():alpha);
      A[i]+=jtmp;
      B[i]+=jtmp;
      tnoise=tnow-log(Xrandom())/(N*rho);
      *flag=2;
     }
   else if (tmin<tmax)
     {
      timestep(tmin);
      A[*imin]=B[*imin]=0;
      for (int j=0;j<N;j++) if (j!=(*imin))
        {
         A[j]+=sigma*J[j][*imin]-delta;                       
         B[j]+=sigma*J[j][*imin]-delta;
        }
      if (*flag==1) m++;
     }
   else
     {
      timestep(tmax);
      *flag=-1;
     }
  }

int neuroni::dinamica(double bin)
  {
   double tmax=tnow+bin;
   int nhit=0;
   while (tnow<tmax)
     {
      int imin,flag;
      nextevent(tmax,&imin,&flag);
      if (flag==0 || flag==1)
        {
         nhit++;
         if (count>=size && size<maxsize)
           {
            size+=1024;
            who=(int*)getmem(who,size*sizeof(int));
            times=(double*)getmem(times,size*sizeof(double));
           }
         if (count<size)
           {
            who[count]=flag+2*imin;
            times[count]=tnow;
            count++;
           }
        }
     }
   return nhit;
  }
#endif
#endif
