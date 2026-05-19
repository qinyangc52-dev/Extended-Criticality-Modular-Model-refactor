#ifndef __HPSORT_H__
#define __HPSORT_H__
#include <stdlib.h>

void hpsort(int n,double *ra);
void hpsort3(int n,double *ra,int *rb=NULL,int *rc=NULL);

#ifndef __HEADERS__

void hpsort(int n,double *ra)
{
	unsigned long i,ir,j,l;
	double rra;
	if (n < 2) return;
	l=(n >> 1)+1;
	ir=n;
	for (;;) {
		if (l > 1) {
			rra=ra[--l];
		} else {
			rra=ra[ir];
			ra[ir]=ra[1];
			if (--ir == 1) {
				ra[1]=rra;
				break;
			}
		}
		i=l;
		j=l+l;
		while (j <= ir) {
			if (j < ir && ra[j] < ra[j+1]) j++;
			if (rra < ra[j]) {
				ra[i]=ra[j];
				i=j;
				j <<= 1;
			} else break;
		}
		ra[i]=rra;
	}
}

void hpsort3(int n,double *ra,int *rb,int *rc)
  {
   if (n < 2) return;
   int l=(n >> 1)+1;
   int ir=n;
   double rra;
   int rrb=0;
   int rrc=0;
   while (1)
     {
      if (l>1)
        {
         l--;
         rra=ra[l];
         if (rb) rrb=rb[l];
         if (rc) rrc=rc[l];
        }
      else
        {
         rra=ra[ir];
         ra[ir]=ra[1];
         if (rb)
           {
            rrb=rb[ir];
            rb[ir]=rb[1];
           }
         if (rc)
           {
            rrc=rc[ir];
            rc[ir]=rc[1];
           }
         ir--;
         if (ir==1)
           {
            ra[1]=rra;
            if (rb) rb[1]=rrb;
            if (rc) rc[1]=rrc;
            break;
           }
        }
      int i=l;
      int j=l+l;
      while (j <= ir)
        {
         if (j<ir && ra[j]<ra[j+1]) j++;
         if (rra<ra[j])
           {
            ra[i]=ra[j];
            if (rb) rb[i]=rb[j];
            if (rc) rc[i]=rc[j];
            i=j;
            j<<=1;
           }
         else break;
	}
      ra[i]=rra;
      if (rb) rb[i]=rrb;
      if (rc) rc[i]=rrc;
     }
  }
#endif
#endif
