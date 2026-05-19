#ifndef __BISECT_H__
#define __BISECT_H__

int select(int mmax,double *x);
int bisect(int mmax,double *x,double xtmp);

#ifndef __HEADERS__
#define __HEADERS__
#include "debug.c"
#include "random.c"


int bisect(int mmax,double *x,double xtmp)
  {
   int m1=0;
   int m2=mmax-1;
   while (m2>m1)
     {
      int mm=(m2+m1)/2;			
      if (xtmp>x[mm+1]) {m1=mm+1;} else if (xtmp<=x[mm]) m2=mm; else m2=m1=mm;
     }
   if (m1!=m2 || m1<0 || m1>=mmax) debug(9,"errore 101... m1=%i m2=%i mmax=%i\n",m1,m2,mmax);
   if (xtmp<x[m1] || xtmp>x[m1+1]) debug(9,"errore 102... %.16f %.16f %.16f\n",x[m1],xtmp,x[m1+1]);
   return m1;
  }


int select(int mmax,double *x)
  {
   double xmax=0;
   for (int m=0;m<mmax;m++)
     {
      if (x[m]<0) debug(9,"errore in select: probabilità negativa...\n");
      xmax+=x[m];
     }
   double xtmp=xmax*Xrandom();
   int m=0;
   while (m<mmax-1 && xtmp>x[m])
     {
      xtmp-=x[m];
      m++;
     }
   return m;
  }
#endif
#endif
