#ifndef __GETMEM_H__
#define __GETMEM_H__
#include <stdlib.h>

void *getmem(void *ptr,long size);
int *ivector(int imin,int imax,int *ptr=NULL);
int **imatrix(int imin,int imax,int jmin,int jmax,int **ptr=NULL);
int ***itensor(int imin,int imax,int jmin,int jmax,int kmin,int kmax);
long int *lvector(int imin,int imax,long int *ptr=NULL);
long int **lmatrix(int imin,int imax,int jmin,int jmax,long int **ptr=NULL);
double *dvector(int imin,int imax,double *ptr=NULL);
double **dmatrix(int imin,int imax,int jmin,int jmax,double **ptr=NULL);
double ***dtensor(int imin,int imax,int jmin,int jmax,int kmin,int kmax);

#ifndef __HEADERS__
#include <stdio.h>

void *getmem(void *ptr,long size)
  {
   void *ptmp;
   if (size>0)
     {
      if (ptr==NULL) ptmp=calloc((size_t)size,(size_t)1); else ptmp=realloc(ptr,(size_t)size);
      if (ptmp==NULL)
        {
         fprintf(stderr,"errore in allocazione memoria: size=%li\n",size);
         exit(1);
        }
     }
   else if (size==0)
     {
      if (ptr) free(ptr);
      ptmp=NULL;
     }
   else ptmp=NULL;
   return ptmp;
  }


int *ivector(int imin,int imax,int *ptr)
  {
   if (ptr) return (int*)getmem(ptr+imin,(long)(imax-imin+1)*sizeof(int))-imin; else return (int*)getmem(NULL,(long)(imax-imin+1)*sizeof(int))-imin;
  }

long int *lvector(int imin,int imax,long int *ptr)
  {
   if (ptr) return (long int*)getmem(ptr+imin,(long)(imax-imin+1)*sizeof(long int))-imin; else return (long int*)getmem(NULL,(long)(imax-imin+1)*sizeof(long int))-imin;
  }

int **imatrix(int imin,int imax,int jmin,int jmax,int **ptr)
  {
   int n=imax-imin+1;
   int m=jmax-jmin+1;
   if (ptr)
     {
      ptr=(int**)getmem(ptr+imin,(long)n*sizeof(int*))-imin;
      ptr[imin]=(int*)getmem(ptr[imin]+jmin,(long)n*m*sizeof(int))-jmin;
     }
   else
     {
      ptr=(int**)getmem(NULL,(long)n*sizeof(int*))-imin;
      ptr[imin]=(int*)getmem(NULL,(long)n*m*sizeof(int))-jmin;
     }
   for (int i=imin+1;i<=imax;i++) ptr[i]=ptr[i-1]+m;
   return ptr;
  }

long int **lmatrix(int imin,int imax,int jmin,int jmax,long int **ptr)
  {
   int n=imax-imin+1;
   int m=jmax-jmin+1;
   if (ptr)
     {
      ptr=(long int**)getmem(ptr+imin,(long)n*sizeof(long int*))-imin;
      ptr[imin]=(long int*)getmem(ptr[imin]+jmin,(long)n*m*sizeof(long int))-jmin;
     }
   else
     {
      ptr=(long int**)getmem(NULL,(long)n*sizeof(long int*))-imin;
      ptr[imin]=(long int*)getmem(NULL,(long)n*m*sizeof(long int))-jmin;
     }
   for (int i=imin+1;i<=imax;i++) ptr[i]=ptr[i-1]+m;
   return ptr;
  }

double *dvector(int imin,int imax,double *ptr)
  {
   if (ptr) return (double*)getmem(ptr+imin,(long)(imax-imin+1)*sizeof(double))-imin; else return (double*)getmem(NULL,(long)(imax-imin+1)*sizeof(double))-imin;
  }

double **dmatrix(int imin,int imax,int jmin,int jmax,double **ptr)
  {
   int n=imax-imin+1;
   int m=jmax-jmin+1;
   if (ptr)
     {
      ptr=(double**)getmem(ptr+imin,(long)n*sizeof(double*))-imin;
      ptr[imin]=(double*)getmem(ptr[imin]+jmin,(long)n*m*sizeof(double))-jmin;
     }
   else
     {
      ptr=(double**)getmem(NULL,(long)n*sizeof(double*))-imin;
      ptr[imin]=(double*)getmem(NULL,(long)n*m*sizeof(double))-jmin;
     }
   for (int i=imin+1;i<=imax;i++) ptr[i]=ptr[i-1]+m;
   return ptr;
  }

double ***dtensor(int imin,int imax,int jmin,int jmax,int kmin,int kmax)
  {
   double ***ptr;
   int n=imax-imin+1;
   int m=jmax-jmin+1;
   int l=kmax-kmin+1;
   ptr=(double***)getmem(NULL,n*sizeof(double**))-imin;
   ptr[imin]=(double**)getmem(NULL,n*m*sizeof(double*))-jmin;
   for (int i=imin+1;i<=imax;i++) ptr[i]=ptr[i-1]+m;
   ptr[imin][jmin]=(double*)getmem(NULL,n*m*l*sizeof(double))-kmin;
   for (int j=jmin+1;j<=jmax;j++) ptr[imin][j]=ptr[imin][j-1]+l;
   for (int i=imin+1;i<=imax;i++)
     {
      ptr[i][jmin]=ptr[i-1][jmax]+l;
      for (int j=jmin+1;j<=jmax;j++) ptr[i][j]=ptr[i][j-1]+l;
     }
   return ptr;
  }

int ***itensor(int imin,int imax,int jmin,int jmax,int kmin,int kmax)
  {
   int ***ptr;
   int n=imax-imin+1;
   int m=jmax-jmin+1;
   int l=kmax-kmin+1;
   ptr=(int***)getmem(NULL,n*sizeof(int**))-imin;
   ptr[imin]=(int**)getmem(NULL,n*m*sizeof(int*))-jmin;
   for (int i=imin+1;i<=imax;i++) ptr[i]=ptr[i-1]+m;
   ptr[imin][jmin]=(int*)getmem(NULL,n*m*l*sizeof(int))-kmin;
   for (int j=jmin+1;j<=jmax;j++) ptr[imin][j]=ptr[imin][j-1]+l;
   for (int i=imin+1;i<=imax;i++)
     {
      ptr[i][jmin]=ptr[i-1][jmax]+l;
      for (int j=jmin+1;j<=jmax;j++) ptr[i][j]=ptr[i][j-1]+l;
     }
   return ptr;
  }

#endif
#endif
