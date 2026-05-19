#include <limits.h> 
#include <math.h>
#define __HEADERS__
#include "pvm.c"
#include "getarg.c"
#include "fopenf.c"
#include "getmem.c"
#include "cpu.c"
#include "network.c"
#include "neuroni.c"
#include "debug.c"

int main(int argc,char **argv)
  {
   pvm_init();

   char *name=getarg_s("name","new");
   char *tmpdir=getarg_s("tmpdir","/tmp/spikes");
   char *outdir=getarg_s("outdir",tmpdir);
   network *Y=new network();
   neuroni *X=new neuroni(Y->N,Y->J,Y->mcue,Y->wcue,Y->tcue);

   double smin=getarg_d("#smin",X->sigma,"minimo E0");
   double smax=getarg_d("#smax",X->sigma,"massimo E0");
   double bin=getarg_d("bin",1,"bin temporale (ms)");
   int flush=getarg_i("flush",10,"ogni quanti bin scrive medie e overlap");
   int flush2=getarg_i("flush2",20,"su quanti flush calcola fluttuazioni overlap");
   double *qstack=dvector(0,flush2-1);
   double rstop=getarg_d("rstop",0,"rate di stop (Hz per neurone)");
   int nstop=getarg_i("nstop",0,"numero flush di stop");
   double tmax=getarg_d("tmax",1000,"tempo massimo simulazione");
   int pout=getarg_i("pout",3,"numero massimo di pattern osservati");
   double tmin=getarg_d("tmin",100,"start calcolo overlap");
   double twin=getarg_d("twin",200,"finestra massima overlap");
   double fmin=getarg_d("fmin",0.5,"finestra minima = fmin*twin");
   int maxsp=getarg_i("maxsp",1<<20,"numero massimo di spike scritte su file");
   double *rates=dvector(0,Y->S-1);
   double tplay=getarg_d("tplay",0);
   if (tplay>0)
     {
      int pout2=getarg_i("#pout2",5);
      int ptmp2=(Y->P>pout2?pout2:Y->P);
      for (int p=0;p<ptmp2;p++)
        {
         FILE *stream=fopenf("%s/spikes0-%i-%s.dat","w",tmpdir,p,name);
         FILE *stream2=fopenf("%s/rate0-%i-%s.dat","w",tmpdir,p,name);
         double T=1000/Y->f;       
         int hp=Y->H[p];		
         int k=0;
         double tnext=bin;
         for (int s=0;s<Y->S;s++) rates[s]=0;
         while (k<maxsp)
           {
            double t=T*(Y->phi[p][k%hp]/(2*M_PI)+(k/hp));
            if (t>tnext)
              {
               double trate=0.001*bin;	
               for (int s=0;s<Y->S;s++) fprintf(stream2," %12g",rates[s]/(Y->Z[s]*trate));
               fprintf(stream2,"\n");
               if (t>tplay) break;
               tnext+=bin;
               for (int s=0;s<Y->S;s++) rates[s]=0;
              }
            int flag=1;
            int imin=Y->who[p][k%hp];
            fprintf(stream,"%12g %4i %6i %6i\n",t,flag,imin,Y->posix[p][imin]);
            rates[Y->where[imin]]++;
            k++;
           }
         fclose(stream2);
         fclose(stream);
        }
     }
   int xmax=8;
   double x[xmax],y[xmax];
   for (int i=0;i<xmax;i++) x[i]=y[i]=0;
   long ntot=0;
   int tail2=0;				
   double last2=0;			
   int count2=0;			
   double norm=1000/(bin*X->N);			
   double dsdt=2*(smax-smin)/tmax;	
   double tstop=tmax/2;			
   int ntmp=0;
   int count=0;				
   while (1)
     {
      double t1=(X->tnow<tstop?X->tnow:2*tstop-X->tnow);
      X->sigma=smin+dsdt*t1;
      X->dsdt=dsdt*(X->tnow<tstop?1:-1);
      int nhit=X->dinamica(bin);
      ntot+=nhit;
      x[0]++;
      x[1]+=nhit;
      x[2]+=nhit*(double)nhit;
      count++;
      if (count%flush==0 || X->tnow>=2*tstop)
        {
         for (int i=0;i<xmax;i++) y[i]+=x[i];
         if (true)
           {
            double xtmp=y[1]/y[0];                                                               
            double rtmp=norm*xtmp;                                                               
            double x2=y[2]/y[0];
            double var=x2-xtmp*xtmp;                                                             
            double CV=sqrt(var)/xtmp;                                                            
            double F=var/xtmp;                                                                   
            if (count==flush)
              {
               FILE *stream3=stdout;
               fprintf(stream3,"FILE: medie3-%s.txt",name);
               fprintf(stream3,"\tfile scritto ogni flush=%i bin (1 bin = %g ms)\n",flush,bin);
               fprintf(stream3,"\tdifferisce da temp3-%s.dat nel senso che le medie e le varianze sono calcolate su tutto il run,\n",name);
               fprintf(stream3,"\tnon solo sugli ultimi %i bin\n",flush);
               fprintf(stream3,"\tper una descrizione delle quantità in colonna vedi temp3-%s.txt\n",name);
              }
            FILE *stream=fopenf("%s/medie3-%s.dat",count==flush?"w":"a",outdir,name);
            fprintf(stream,"%12g %12g %12g %12g %12g %12g %12g %12g\n",X->sigma,X->delta,X->alpha,X->tnow,rtmp,var,CV,F);
            fclose(stream);
           }
         if (true)
           {
            double xtmp=x[1]/x[0];                                                               
            double rtmp=norm*xtmp;                                                               
            double x2=x[2]/x[0];
            double var=x2-xtmp*xtmp;                                                             
            double CV=sqrt(var)/xtmp;                                                            
            double F=var/xtmp;                                                                   
            if (count==flush)
              {
               FILE *stream3=stdout;
	       fprintf(stream3,"FILE: temp3-%s.txt",name);
               fprintf(stream3,"\tfile scritto ogni flush=%i bin (1 bin = %g ms)\n",flush,bin);
               fprintf(stream3,"\tdati nelle colonne:\n");
               fprintf(stream3,"\t1) sigma\n");
               fprintf(stream3,"\t2) delta\n");
               fprintf(stream3,"\t3) alpha\n");
               fprintf(stream3,"\t4) tempo in ms\n");
               fprintf(stream3,"\t5) rate medio per neurone in Hz (calcolato sugli ultimi %i bin)\n",flush);
               fprintf(stream3,"\t   N.B: il rate è il numero di spike in un bin, diviso per N=%i neuroni e per il bin in secondi\n",X->N);
               fprintf(stream3,"\t6) varianza del numero di spike in un bin (calcolata sugli ultimi %i bin)\n",flush);
               fprintf(stream3,"\t7) coefficiente di variazione (radice della varianza del numero di spike diviso la media del numero di spike)\n");
               fprintf(stream3,"\t8) fattore di Fano (varianza del numero diviso la media... è uguale a 1 per spike poissoniane)\n");
              }
            FILE *stream=fopenf("%s/temp3-%s.dat",count==flush?"w":"a",outdir,name);
            fprintf(stream,"%12g %12g %12g %12g %12g %12g %12g %12g\n",X->sigma,X->delta,X->alpha,X->tnow,rtmp,var,CV,F);
            fclose(stream);
            if (dsdt>0)	
              {
               if (rstop>0 && rtmp>rstop) ntmp++;
               if (nstop>0 && ntmp>=nstop && tstop>X->tnow) tstop=X->tnow;
              }
           }
         for (int i=0;i<xmax;i++) x[i]=0;
        }
      int kmin=0;
      int kmax=X->count;
      if (count%flush==0 || X->tnow>=2*tstop)
        {
         double qm=0;
         double qs=0;
         double qmaxx=0;                     
         int pmaxx=0;                                
         double *qmax=dvector(0,Y->P-1);          
         double *wq=dvector(0,Y->P-1);            
         double tlast=(kmax==0?0:X->times[kmax-1]);
         double tstart=(tlast<tmin+twin?tmin:tlast-twin);		
         while (kmin<kmax && X->times[kmin]<tstart) kmin++;
         int ktot=kmax-kmin;
         int kwin=2;						
         if (ktot>kwin && tlast-tstart+1e-8>=fmin*twin)
           {
            double wmin=10;              
            double wmax=200;             
            double wdel=5;
            for (int p=0;p<Y->P;p++)
              {
               for (double w=wmin;w<=wmax;w+=wdel)
                 {
                  double ctmp=0;
                  double stmp=0;
                  for (int k=kmin;k<kmax;k++)
                    {
                     int imin=X->who[k]/2;
                     double tk=X->times[k];
                     int q=Y->order[p][imin];
                     if (q>=0)
                       {
                        double htmp=(2*M_PI*tk/w)-Y->phi[p][q];
                        ctmp+=cos(htmp);
                        stmp+=sin(htmp);
                       }
                    }
                  double qtmp=sqrt(ctmp*ctmp+stmp*stmp)/ktot;
                  if (qtmp>qmax[p]) {qmax[p]=qtmp; wq[p]=w;}
                 }
               if (qmax[p]>qmaxx) {qmaxx=qmax[p]; pmaxx=p;}
              }
            int c1=count/flush;
            qstack[(c1-1)%flush2]=qmaxx;
            int cmax=(c1<flush2?c1:flush2);
            for (int c=0;c<cmax;c++)
              {
               qm+=qstack[c];
               qs+=qstack[c]*qstack[c];
              }
            qm/=cmax;
            qs=qs/cmax-qm*qm;
           }
         int ptmp=(Y->P>pout?pout:Y->P);
         static int flag;
         if (flag==0)
           {
            FILE *stream3=stdout;
            fprintf(stream3,"FILE: q3-%s.txt",name);
            fprintf(stream3,"\tfile scritto ogni flush=%i bin (1 bin = %g ms)\n",flush,bin);
            fprintf(stream3,"\tdati nelle colonne:\n");
            fprintf(stream3,"\t1) sigma\n");
            fprintf(stream3,"\t2) delta\n");
            fprintf(stream3,"\t3) alpha\n");
            fprintf(stream3,"\t4) tmin: tempo iniziale calcolo overlap\n");
            fprintf(stream3,"\t5) tmax: tempo finale calcolo overlap\n");
            fprintf(stream3,"\t6) numero di spike tra tmin e tmax\n");
            fprintf(stream3,"\t7) quale overlap ha dato overlap massimo\n");
            fprintf(stream3,"\t8) valore dell'overlap massimo\n");
            fprintf(stream3,"\t9) fluttuazioni dell'overlap massimo calcolate sugli ultimi flush2=%i punti\n",flush2);
            fprintf(stream3,"\t10, 12, ...) finestra utilizzata per calcolo overlap (per i primi pout=%i pattern)\n",pout);
            fprintf(stream3,"\t11, 13, ...) valore dell'overlap (per i primi pout=%i pattern)\n",pout);
            flag=1;
           }
         FILE *stream=fopenf("%s/q3-%s.dat",flag?"a":"w",tmpdir,name);
         fprintf(stream,"%12g %12g %12g %12g %12g %12i %12i %12g %12g",X->sigma,X->delta,X->alpha,tstart,tlast,ktot,pmaxx,qmaxx,qs);
         for (int p=0;p<ptmp;p++) fprintf(stream," %6g %12g",wq[p],qmax[p]);
         fprintf(stream,"\n");
         fclose(stream);
         free(wq);
         free(qmax);
        }
      if (true) 
        {
         if (X->count<0 || tail2<0 || tail2>X->count) debug(9,"errore... X->count=%li tail2=%i\n",X->count,tail2);
         static int flag2;
         if (flag2==0)
           {
            FILE *stream3=stdout;
	    fprintf(stream3,"FILE: spikes3-%s.txt",name);
            fprintf(stream3,"\tcolonne:\n");
            fprintf(stream3,"\t1) tempo in ms\n");
            fprintf(stream3,"\t2) flag=0 se la spike è dovuta a input interno alla rete\n");
            fprintf(stream3,"\t   flag=1 se la spike è indotta dalla cue\n");
            fprintf(stream3,"\t3) quale neurone ha sparato\n");
            fprintf(stream3,"\t4,5,6...) per i primi pout=%i pattern, posizione del neurone nel pattern\n",pout);
            fprintf(stream3,"\tla posizione è determinata dal sito (primo sito in basso, secondo subito sopra, etc...)\n");
            fprintf(stream3,"\tall'interno del sito i neuroni appartententi al pattern sono i primi nell'ordine che hanno nel pattern\n");
           }
         if (count2<maxsp)
           {
            int ptmp=(Y->P>pout?pout:Y->P);
            FILE *stream=fopenf("%s/spikes3-%s.dat",flag2?"a":"w",tmpdir,name);
            for (int k=tail2;k<X->count;k++)
              {
               int flag=X->who[k]%2;
               int imin=X->who[k]/2;
               fprintf(stream,"%20.15g %4i %6i",X->times[k],flag,imin);
               for (int p=0;p<ptmp;p++) fprintf(stream," %6i",Y->posix[p][imin]);
               fprintf(stream,"\n");
              }
            fclose(stream);
           }
         if (flag2==0)
           {
            FILE *stream3=stdout;
	    fprintf(stream3,"FILE: rate3-%s.txt",name);
            fprintf(stream3,"\tfile scritto ogni bin (1 bin = %g ms)\n",bin);
            fprintf(stream3,"\tcolonne:\n");
            fprintf(stream3,"\t1) tempo in ms\n");
            fprintf(stream3,"\t2...%i) per ognuno dei %i siti, il rate medio nell'ultimo bin\n",1+Y->S,Y->S);
           }
         for (int s=0;s<Y->S;s++) rates[s]=0;
         for (int k=tail2;k<X->count;k++)
           {
            int imin=X->who[k]/2;
            rates[Y->where[imin]]++;
           }
         double trate=0.001*(X->tnow-last2);
         FILE *stream2=fopenf("%s/rate3-%s.dat",flag2?"a":"w",tmpdir,name);
         fprintf(stream2,"%8g",X->tnow);
         for (int s=0;s<Y->S;s++)
           {
	    double rtmp=rates[s]/(Y->Z[s]*trate);
            fprintf(stream2," %12g",rtmp);
           }
         fprintf(stream2,"\n");
         fclose(stream2);
         count2+=(X->count-tail2);
         tail2=X->count;
         last2=X->tnow;
         flag2=1;
        }
      if (kmin>0 && tail2>=kmin)
        {
         for (int k=kmin;k<X->count;k++)
           {
            X->who[k-kmin]=X->who[k];
            X->times[k-kmin]=X->times[k];
           }
         X->count-=kmin;
         tail2-=kmin;
        }
      if (cpuint() || cputerm() || X->tnow>=2*tstop)
        {
         double f=1000.*ntot/(X->N*X->tnow);
         printf("t=%g ms (%g Hz/neurone) spike totali: %li (numero di spike scritte %i)\n",X->tnow,f,ntot,count2);
         if (cputerm() || X->tnow>=2*tstop) break;
        }
     }

   FILE *stream=fopenf("%s/spikes3-%s.gnu","w",tmpdir,name);
   fprintf(stream,"set term pngcairo enhanced dashed\n");
   fprintf(stream,"set output \"spikes3-%s.png\"\n",name);
   fprintf(stream,"set xrange [0:%g]\n",X->tnow);
   fprintf(stream,"set yrange [0:%i]\n",X->N);
   fprintf(stream,"plot \\\n");
   for (int i=1;i<Y->S;i++) fprintf(stream,"%i title \"\" with lines dt 2 lw 1 lc rgb \"black\",\\\n",Y->start[i]);
   fprintf(stream,"\"spikes3-%s.dat\" using 1:4 title \"\" with points pt 7 ps 1 lc rgb \"red\"\n",name);
   fclose(stream);

   pvm_end();
   return 0;
  }
