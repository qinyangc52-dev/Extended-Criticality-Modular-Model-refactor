#ifndef __PVM_H__
#define __PVM_H__
#include <stdlib.h>

void pvm_init(int *argc=NULL,char ***argv=NULL);
void pvm_end(void);
int pvm_mype(void);
int pvm_debug(void);
int pvm_nfile(int nfile=0);
void pvm_load(void);
void pvm_save(void);

#ifndef __HEADERS__
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <string.h>
#define __HEADERS__
#include "fopenf.c"
#include "getarg.c"
#include "random.c"
#include "cpu.c"
#include "getmem.c"
#include "mpi.c"

static int mype;
static int mype2;
static int npes;
static int nfile;
static int flag;		
static int deneb;		

void pvm_load(void)
  {
   FILE *stream=fopenf("temp/PVM","r");
   if (stream)
     {
      if (fread(&nfile,sizeof(int),1,stream));
      fclose(stream);
     }
  }

void pvm_save(void)
  {
   if (flag && deneb)
     {
      FILE *stream=fopenf("temp/PVM","w");
      if (fwrite(&nfile,sizeof(int),1,stream));
      fclose(stream);
      flag=0;
     }
  }

void pvm_init(int *argc,char ***argv)
  {
   mpi_init(argc,argv);
   init_args(argc,argv);
   mype=getarg_i("#mype",0);
   mype2=mpi_mype();
   npes=mpi_npes();

   char *path=getarg_s("#stdout");

   if (npes>1)
     {
      path=(char*)getmem(NULL,24*sizeof(char));
      sprintf(path,"output-%03i.txt",mype2);
      fprintf(stderr,"mpi process #%i: redirecting stdout & stderr to %s\n",mype2,path);
     }

   if (strcmp(path,"NULL"))
     {
      makedir(path);
      if (freopen(path,"a",stdout)==NULL) fprintf(stderr,"pvm_init: errore in freopenf(%s)\n",path);
      if (dup2(STDOUT_FILENO,STDERR_FILENO)==-1) fprintf(stderr,"pvm_init: errore in dup2\n");
     }
   setlinebuf(stdout);

   double cpu=getarg_d("#cpu",0.);
   double save=getarg_d("#save",3600.);
   cpustart(cpu,save);

   int seed=time(NULL);
   int seed2=mype2+mype*mpi_npes();
   seed=getarg_i("seed",seed);
   seed2=getarg_i("seed2",seed2);
   init_random(seed,seed2);

   int deb=getarg_i("#debug",1);
   deneb=(deb?0:1);
   pvm_load();
  }

int pvm_mype(void)
  {
   return mype2+mype*mpi_npes();
  }

int pvm_debug(void)	
  {
   return (deneb?0:1);
  }

int pvm_nfile(int ntmp)
  {
   if (ntmp)
     {
      if (ntmp!=1)
        {
         fprintf(stderr,"parametro errato in pvm_nfile\n");
         exit(1);
        }
      nfile++;
      flag=1;
     }
   return nfile;
  }

void pvm_end(void)
  {
   pvm_save();
   mpi_end();
  }
#endif
#endif
