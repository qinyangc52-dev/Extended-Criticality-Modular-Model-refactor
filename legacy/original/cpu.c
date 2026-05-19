#ifndef __CPU_H__
#define __CPU_H__
#include <stdlib.h>

void cpustart(double cpu=0.,double save=0.);
double cputime(double *stime=NULL);
double walltime(void);
int cpuint(int level=0);
int cputerm(void);
int cpunext(int skip=0);
void gprof(int level=-1);

#ifndef __HEADERS__
#include <stdio.h>
#include <signal.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

static double cpu;		
static double save;

static int init_cpu;
static double start;		
static int flag;		
static double ctrc;	
static double last;		
static struct timeval tv;

static double tmin=10;		
static double tmax=10000;	
static double tdelta;		
static double tnext;		

#define lmax 16

static int ftmp[lmax];
static int ltmp;
static double clast;
static double csum[lmax];		

#define TBIG 1e30

static void handler(int signum)
  {
   if (signum==SIGTERM) flag=1;
   else if (signum==SIGINT)
     {
      double now=walltime();
      if (ctrc<TBIG && now<ctrc+1)
        {
         ctrc=TBIG;
         flag=1;	
        }
      else ctrc=now;		
     }
   signal(signum,handler);
  }

double cputime(double *_stime)
  {
   struct rusage usage;
   if (getrusage(RUSAGE_SELF,&usage))
     {
      fprintf(stderr,"cputime: errore in getrusage\n");
      exit(1);
     }
   double utime=usage.ru_utime.tv_sec+1e-6*usage.ru_utime.tv_usec;		
   double stime=usage.ru_stime.tv_sec+1e-6*usage.ru_stime.tv_usec;		
   if (_stime) *_stime=stime;
   return utime+stime;
  }

void gprof(int level)
  {
   if (level>=0 && level<lmax)
     {
      double ctmp=cputime();
      csum[ltmp]+=ctmp-clast;
      clast=ctmp;
      ltmp=level;
     }
   else
     {
      double ctot=cputime();				
      FILE *stream=fopen("gprof.log","w");
      fprintf(stream,"CPU=%12g\n",ctot);
      for (int l=0;l<lmax;l++) if (csum[l]>0) fprintf(stream," %3i: %12g (%6.3f%%)\n",l,csum[l],100*csum[l]/ctot);
      fclose(stream);
     }
  }

double walltime(void)
  {
   if (init_cpu==0) cpustart(0.,0.);
   gettimeofday(&tv,NULL);
   return (tv.tv_sec+1e-6*tv.tv_usec)-start;
  }

void cpustart(double _cpu,double _save)
  {
   init_cpu++;			
   if (_cpu>0) cpu=_cpu;
   if (_save>0) save=_save;
   if (init_cpu==1) start=walltime();
   signal(SIGINT,handler);
   signal(SIGTERM,handler);
   ctrc=TBIG;
   tdelta=tnext=tmin;
   ltmp=0;
   clast=cputime();
  }

int cpunext(int skip)
  {
   double now=walltime();
   if (now>=tnext)
     {
      if (skip==0)	
        {
         if (tdelta<tmax) tdelta*=2;
         do {tnext+=tdelta;} while (tnext<=now);
        }
      return 1;
     }
   else return 0;
  }


int cpuint(int level)
  {
   if (level<0) level=0;
   if (level>=lmax) level=lmax-1;
   if (flag && level==0)    
     {
      static int count;
      count++;
      int cmax=100;
      if (count>=cmax)
        {
         fprintf(stderr,"... loop infinito cpuint? ...\n");
         exit(1);
        }
     }
   double now=walltime();
   int flag2=0;
   if (now>ctrc+1)
     {
      ctrc=TBIG;
      last=now;
      flag2=1;
     }
   else if (save>0 && now>last+save) 
     {
      last=now;
      flag2=1;
     }
   int fret=ftmp[level];
   if (flag2)
     {
      for (int l=0;l<level;l++) ftmp[l]=1;
      fret=1;
     }
   else ftmp[level]=0;
   return fret;
  }

int cputerm(void)
  {
   static double next;
   double now=walltime();
   if (cpu<=0 || now<cpu)
     {
      if (now>next)
        {
         struct stat buf;
         if (lstat("STOP",&buf)==0 && S_ISREG(buf.st_mode)) flag=1;
         next+=600;
        }
     }
   else flag=1;
   return flag;
  }
#endif
#endif
