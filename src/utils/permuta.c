#ifndef __PERMUTA_H__
#define __PERMUTA_H__

void permuta(int n,int N,int *stack);

#ifndef __HEADERS__
#include <math.h>
#define __HEADERS__
#include "random.c"


void permuta(int n,int N,int *stack)
  {
   for (int i=0;i<n;i++)
     {
      int j=(int)floor((N-i)*Xrandom());
      int itmp=stack[i];
      stack[i]=stack[i+j];
      stack[i+j]=itmp;
     }
  }
#endif
#endif
