#ifndef __MPI_H__
#define __MPI_H__
#include <stdlib.h>

void mpi_init(int *argc,char ***argv);
int mpi_mype(void);
int mpi_npes(void);
void mpi_barrier(void);
void mpi_ibcast(int *ptr,int n,int root);
void mpi_isend(int *ptr,int n,int tid);
void mpi_irecv(int *ptr,int n,int tid);
void mpi_dbcast(double *ptr,int n,int root);
void mpi_dsend(double *ptr,int n,int tid);
void mpi_drecv(double *ptr,int n,int tid);
int mpi_term(void);
void mpi_end(void);

#ifndef __HEADERS__
#ifdef __USE_MPI__
#include <mpi.h>
#endif
#define __HEADERS__
#include "cpu.c"

void mpi_init(int *argc,char ***argv)
  {
#ifdef __USE_MPI__
   MPI_Init(argc,argv);
#endif
  }

int mpi_mype(void)
  {
   int mype=0;
#ifdef __USE_MPI__
   MPI_Comm_rank(MPI_COMM_WORLD,&mype);
#endif
   return mype;
  }

int mpi_npes(void)
  {
   int npes=1;
#ifdef __USE_MPI__
   MPI_Comm_size(MPI_COMM_WORLD,&npes);
#endif
   return npes;
  }

void mpi_barrier(void)
  {
#ifdef __USE_MPI__
   MPI_Barrier(MPI_COMM_WORLD);
#endif
  }

void mpi_ibcast(int *ptr,int n,int root)
  {
#ifdef __USE_MPI__
   MPI_Bcast(ptr,n,MPI_INT,root,MPI_COMM_WORLD);
#endif
  }

void mpi_isend(int *ptr,int n,int tid)
  {
#ifdef __USE_MPI__
   MPI_Send(ptr,n,MPI_INT,tid,0,MPI_COMM_WORLD);
#endif
  }

void mpi_irecv(int *ptr,int n,int tid)
  {
#ifdef __USE_MPI__
   MPI_Status status;
   MPI_Recv(ptr,n,MPI_INT,(tid<0?MPI_ANY_SOURCE:tid),0,MPI_COMM_WORLD,&status);
#endif
  }

void mpi_dbcast(double *ptr,int n,int root)
  {
#ifdef __USE_MPI__
   MPI_Bcast(ptr,n,MPI_DOUBLE,root,MPI_COMM_WORLD);
#endif
  }

void mpi_dsend(double *ptr,int n,int tid)
  {
#ifdef __USE_MPI__
   MPI_Send(ptr,n,MPI_DOUBLE,tid,0,MPI_COMM_WORLD);
#endif
  }

void mpi_drecv(double *ptr,int n,int tid)
  {
#ifdef __USE_MPI__
   MPI_Status status;
   MPI_Recv(ptr,n,MPI_DOUBLE,(tid<0?MPI_ANY_SOURCE:tid),0,MPI_COMM_WORLD,&status);
#endif
  }

int mpi_term(void)
  {
   int mype=0;
#ifdef __USE_MPI__
   MPI_Comm_rank(MPI_COMM_WORLD,&mype);
   MPI_Barrier(MPI_COMM_WORLD);
#endif
   int flag=0;
   if (mype==0) flag=cputerm();
#ifdef __USE_MPI__
   MPI_Bcast(&flag,1,MPI_INT,0,MPI_COMM_WORLD);
#endif
   return flag;
  }

void mpi_end(void)
  {
#ifdef __USE_MPI__
   MPI_Finalize();
#endif
  }
#endif
#endif
