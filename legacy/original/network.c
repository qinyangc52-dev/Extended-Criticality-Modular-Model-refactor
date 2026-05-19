#ifndef __NETWORK_H__
#define __NETWORK_H__
#include <stdlib.h>

class network
  {
   public:
   network(void);

   char *topo;
   int S;
   int G;
   int *Z;
   int *K;
   int P;
   int N;
   int sort;
   double swap;
   double range;
   double f;
   int pmax;
   char name2[128];

   char *tmpdir;
   int *start;
   int *where;
   int **sites;		
   int **posix;
   int **who;
   double **phi;
   double **J;
   int *H;
   int **order;

   int mcue;
   int *wcue;
   double *tcue;

   void creaposix(void);
   void readcues(void);
   void sitipattern(void);
   void neuronipattern(void);
   void connessioni(void);
   void hmatrix(void);
   void fasi(void);
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
#include "fopenf.c"
#include "getarg.c"
#include "random.c"
#include "cpu.c"
#include "debug.c"
#include "hpsort.c"
#include "permuta.c"
#include "bisect.c"
#include "tract1.c"		

void network::readcues(void)
  {
   mcue=0;				
   wcue=NULL;
   tcue=NULL;
   int ncue=0;
   FILE *stream=fopen("SEED","r");
   if (stream)
     {
      char buffer[1024];
      while (fgets(buffer,1024,stream)) if (strstr(buffer,"begin cue description")) break;
      if (!feof(stream))
        {
         if (fgets(buffer,1024,stream)) sscanf(buffer,"%i",&ncue);
         if (ncue>0)
           {
            if (ncue>P) debug(9,"numero di cue maggiore del numero di pattern...\n");
            debug(0,"numero cue: %i\n",ncue);
            for (int k=0;k<ncue;k++)
              {
               int M;
               double tstart,fs;
               if (fgets(buffer,1024,stream)) sscanf(buffer,"%le",&tstart);
               if (fgets(buffer,1024,stream)) sscanf(buffer,"%i",&M);                
               if (fgets(buffer,1024,stream)) sscanf(buffer,"%le",&fs);
               debug(0,"cue %i (pattern %i) tstart=%g ms, numero spike %i, frequenza %g Hz\n",k,k,tstart,M,fs);
               wcue=(int*)getmem(wcue,(mcue+M)*sizeof(int));
               tcue=(double*)getmem(tcue,(mcue+M)*sizeof(double));
               for (int i=0;i<M;i++)
                 {
                  int j=i%H[k];
                  wcue[mcue+i]=who[k][j];
                  tcue[mcue+i]=tstart+(1000/fs)*i/(double)H[k];
                 }
               mcue+=M;
              }
           }
        }
      fclose(stream);
     }
   if (ncue==0) debug(0,"numero cue: 0\n");
  }

void network::sitipattern(void)		
  {
   if (strcmp(topo,"random")==0)
     {
      for (int p=0;p<P;p++)
        {
         for (int i=0;i<S;i++) sites[p][i]=i;
         if (p>0) permuta(S,S,sites[p]);
        }
     }
#if 1											
   else if (strcmp(topo,"tract1")==0 || strcmp(topo,"tract2")==0)
     {
      double **W=tract1(S);
      double *wtot=dvector(0,S-1);
      for (int j=0;j<S;j++) for (int j2=0;j2<S;j2++) wtot[j]+=W[j][j2];
      for (int p=0;p<P;p++)
        {
         int ntry=0;
         int maxtry=10000;
         while (1)
           {
            sites[p][0]=select(S,wtot);
            int i=1;
            while (i<=G)
              {
               int j1=sites[p][i-1];               
               int j2;
               while (1)
                 {
                  j2=select(S,W[j1]);
                  if (i==G) break;
                  int k=0;
                  while (k<i && sites[p][k]!=j2) k++;
                  if (k==i) break;                                 
                 }
               sites[p][i]=j2;
               i++;
              }
            if (sites[p][G]==sites[p][0]) break;           
            ntry++;
            if (ntry>maxtry) debug(9,"p=%i... non riesco a trovare cammini chiusi... aumentare maxtry?\n",p);
           }
         int i=G;
         while (i<S)
           {
            int j=0;
            while (j<S)
              {
               int k=0;
               while (k<i && sites[p][k]!=j) k++;
               if (k==i) break;
               j++;
              }
            if (j>=S) debug(9,"errore...\n");
            sites[p][i]=j;
            i++;
           }
        }
      free(wtot);
      free(W[0]);
      free(W);
     }
#endif
   else debug(9,"valore di topo non riconosciuto...\n");
   int ptmp=(P<pmax?P:pmax);
   FILE *stream=fopenf("%s/sites3-%s.txt","w",tmpdir,name2);
   for (int i=0;i<G;i++)
     {
      for (int p=0;p<ptmp;p++) fprintf(stream," %4i",sites[p][i]);
      fprintf(stream,"\n");
     }
   fclose(stream);
  }

void network::hmatrix(void)
  {
   for (int p=0;p<P;p++)
     {
      H[p]=0;
      for (int i=0;i<G;i++)
        {
         int s=sites[p][i];                                                             
         H[p]+=K[s];     
        }
     }
  }

void network::neuronipattern(void)
  {
   int *stack=ivector(0,N-1);
   for (int p=0;p<P;p++)
     {
      int h=0;
      for (int i=0;i<G;i++)
        {
         int s=sites[p][i];								
         for (int j=0;j<Z[s];j++) stack[j]=start[s]+j;
         if (p>0) permuta(K[s],Z[s],stack);
         for (int j=0;j<K[s];j++)
           {
            who[p][h]=stack[j];
            h++;
           }
        }
     }
   free(stack);
  }

void network::creaposix(void)
  {
   order=imatrix(0,P-1,0,N-1);
   for (int p=0;p<P;p++)
     {
      for (int i=0;i<N;i++) order[p][i]=-1;
      for (int k=0;k<H[p];k++) order[p][who[p][k]]=k;           
     }
   posix=imatrix(0,P-1,0,N-1);
   int *stack=ivector(0,N-1);
   for (int p=0;p<P;p++)
     {
      for (int i=0;i<N;i++)
        {
         stack[i]=0;
         posix[p][i]=-1;     
        }
      int h=0;						
      for (int s=0;s<S;s++)
        {
         for (int i=0;i<H[p];i++) 
            {
             int imin=who[p][i];                             
             int s1=where[imin];
             if (s1==s)
               {
                stack[imin]=1;
                posix[p][imin]=h;
                h++;
               }
            }
         for (int i=start[s];i<start[s]+Z[s];i++)
            {
             if (stack[i]==0)
               {
                posix[p][i]=h;
                h++;
               }
            }
        }
      if (h!=N) debug(9,"errore nella creazione del vettore posix...\n");
     }
   free(stack);
  }

void network::fasi(void)
  {
   if (sort==0)
     {
      for (int p=0;p<P;p++)
        {
         int nswap=(int)rint(swap*H[p]);
         for (int i=0;i<nswap;i++)
           {
            int d1=(int)floor(fabs(range*Grandom()));
            int j1=(int)floor(H[p]*Xrandom());
            int j2=(j1+d1)%H[p];
            int wtmp=who[p][j1];
            who[p][j1]=who[p][j2];
            who[p][j2]=wtmp;
           }
         for (int i=0;i<H[p];i++) phi[p][i]=2*M_PI*Xrandom();
         hpsort(H[p],phi[p]-1);
        }
     }
   else if (sort==1 || sort==2)
     {
      for (int p=0;p<P;p++)
        {
         int h=0;
         for (int i=0;i<G;i++)
           {
            int s=sites[p][i];	
            if (sort==1)
              {
               double p1=2*M_PI*h/(double)H[p];
               double p2=2*M_PI*(h+K[s])/(double)H[p];
               for (int j=0;j<K[s];j++) phi[p][h+j]=p1+(p2-p1)*Xrandom();
              }
            else
              {
               double pm=2*M_PI*(h+0.5*K[s])/H[p];
               double dp=2*M_PI*range*(0.5*K[s])/H[p];
               for (int j=0;j<K[s];j++) phi[p][h+j]=pm+dp*Grandom();
              }
            h+=K[s];
           }
         hpsort3(H[p],phi[p]-1,who[p]-1);
        }
     }
   else debug(9,"valore di sort non implementato...\n");
  }

#define STDP(t) ( t>0 ? 0.4121037*exp(-0.0980392*t)-0.2295345*exp(-0.392157*t) : 0.4121037*exp(0.13986*t)-0.2295345*exp(0.034965*t) )

void network::connessioni(void)
  {
   double T=1000/f;		
   int nmax=ceil(286/T);
   for (int p=0;p<P;p++)
     {
      for (int i=0;i<H[p];i++) for (int j=0;j<H[p];j++) if (i!=j)
        {
         int k1=who[p][i];
         int k2=who[p][j];
         for (int n=-nmax;n<=nmax;n++) J[k2][k1]+=STDP(T*(n+(phi[p][j]-phi[p][i])/(2*M_PI)));
         if (cpuint(9)) fprintf(stderr,"sto calcolando le connessioni...\n");
        }
     }
  }

network::network(void)
  {
   topo=getarg_s("topo","random","topologia connessioni");
   S=getarg_i("S",20,"numero siti");
   G=getarg_i("G",10,"siti del pattern");
   Z=ivector(0,S-1);
   K=ivector(0,S-1);
   int ztmp=getarg_i("Z",100,"neuroni per sito");
   int ktmp=getarg_i("K",50,"neuroni per sito del pattern");
   sort=getarg_i("sort",0,"tipo di sorting dei neuroni");
   if (sort==0) swap=getarg_d("swap",0); else swap=0;
   if (sort==0 || sort==2) range=getarg_d("range",1,"range di spread delle fasi"); else range=0;
   P=getarg_i("P",1,"numero pattern");
   if (strcmp(topo,"random")==0)
     {
      for (int i=0;i<S;i++) Z[i]=ztmp;
      for (int i=0;i<S;i++) K[i]=ktmp;
     }
#if 1							
   else if (strncmp(topo,"tract",5)==0)
     {
      if (strcmp(topo,"tract1")==0)
        {
         for (int i=0;i<S;i++) Z[i]=ztmp;
         for (int i=0;i<S;i++) K[i]=ktmp;
        }
      else sizes(S,ztmp,ktmp,Z,K);
     }
#endif
   else debug(9,"topo=%s non implementato\n",topo);
   N=0;
   for (int s=0;s<S;s++) N+=Z[s];			
   start=ivector(0,S-1);				
   int ntmp=0;
   for (int s=0;s<S;s++)
     {
      start[s]=ntmp;
      ntmp+=Z[s];
     }
   where=ivector(0,N-1);			
   for (int i=0;i<N;i++)
     {
      int s=0;
      int n=i;
      while (n>=Z[s])
        {
         n-=Z[s];
         s++;
        }
      where[i]=s;
     }
   f=getarg_d("f",8,"frequenza di learning (Hz)");
   int file=getarg_i("file",0,"salvare/leggere file delle connessioni");
   pmax=getarg_i("pmax",3,"numero massimo di pattern osservati");
   tmpdir=getarg_s("tmpdir","/tmp/spikes/");
   FILE *stream2=fopenf("%s/start-%s.txt","w",tmpdir,topo);
   for (int s=0;s<S;s++) fprintf(stream2,"%12i %12i %12i %12i\n",1+s,Z[s],start[s],K[s]);
   fprintf(stream2,"%12i %12i %12i %12i\n",1+S,0,N,0);
   fclose(stream2);
   sprintf(name2,"%i-%i-%i-%i-%i-%i-%g-%g-%s",S,ztmp,G,ktmp,P,sort,swap,range,topo);
   sites=imatrix(0,P-1,0,S-1);
   who=imatrix(0,P-1,0,N-1);
   phi=dmatrix(0,P-1,0,N-1);
   J=dmatrix(0,N-1,0,N-1);
   H=ivector(0,P-1);
   char tmpfile[PATH_MAX];
   sprintf(tmpfile,"%s/CONNESSIONI5-%s",tmpdir,name2);
   FILE *stream=(file&1)?fopenf("%s","r",tmpfile):NULL;
   if (stream)
     {
      if (fread(sites[0],sizeof(int),P*(long)S,stream));
      if (fread(H,sizeof(int),P,stream));
      if (fread(who[0],sizeof(int),P*(long)N,stream));
      if (fread(phi[0],sizeof(double),P*(long)N,stream));
      if (fread(J[0],sizeof(double),N*(long)N,stream));
      fclose(stream);
      debug(0,"pattern & connessioni letti dal file %s\n",tmpfile);
     }
   else
     {
      unsigned long seed1=randomseed();
      int seed3=getarg_i("seed3",0);
      if (seed3>0) init_random(seed3);
      sitipattern();
      hmatrix();
      neuronipattern();
      fasi();
      connessioni();
      FILE *stream3=stdout;
      fprintf(stream3,"FILE: matrice3-%s.txt",name2);
      fprintf(stream3,"\tdati nelle colonne:\n");
      fprintf(stream3,"\t1) sito di partenza\n");
      fprintf(stream3,"\t2) sito di arrivo\n");
      fprintf(stream3,"\t3) somma di tutte le connessioni positive dal sito di partenza a quello di arrivo\n");
      fprintf(stream3,"\t4)   \"       \"         \"      negative      \"        \"                 \"\n");
      FILE *stream4=fopenf("%s/matrice3-%s.txt","w",tmpdir,name2);
      for (int i=0;i<S;i++) for (int j=0;j<S;j++)
        {
         double se=0;
         double si=0;
         for (int k=0;k<Z[i];k++) for (int l=0;l<Z[j];l++)
           {
            int i1=start[i]+k;
            int i2=start[j]+l;
            if (i1!=i2 && J[i1][i2]>0) se+=J[i1][i2];
            if (i1!=i2 && J[i1][i2]<0) si+=J[i1][i2];
           }
         fprintf(stream4,"%6i %6i %12g %12g\n",j,i,se,si);            
        }
      fclose(stream4);
      if (file&2)
        {
         debug(0,"scrivo pattern & connessioni nel file %s (%g Gb)\n",tmpfile,4e-9*P*(S+N)+8e-9*(P+N)*N);
         stream=fopenf("%s","w",tmpfile);
         if (fwrite(sites[0],sizeof(int),P*(long)S,stream));
         if (fwrite(H,sizeof(int),P,stream));
         if (fwrite(who[0],sizeof(int),P*(long)N,stream));
         if (fwrite(phi[0],sizeof(double),P*(long)N,stream));
         if (fwrite(J[0],sizeof(double),N*(long)N,stream));
         fclose(stream);
        }
      if (file&4)
        {
         debug(0,"esco senza fare dinamica...\n");
         exit(0);
        }
      if (seed3>0) pushrandom(seed1);
     }
   creaposix();
   readcues();
  }
#endif
#endif
