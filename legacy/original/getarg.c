#ifndef __GETARG_H__
#define __GETARG_H__
#include <stdlib.h>

void init_args(int *argc=NULL,char ***argv=NULL);
int getarg_i(const char *name,int ndef=0,const char *srem=NULL);
double getarg_d(const char *name,double xdef=0.,const char *srem=NULL);
char *getarg_s(const char *name,const char *sdef=NULL,const char *srem=NULL);
int getlinearg(const char *path,int nline=0,const char *name=NULL);

#ifndef __HEADERS__
#include <stdio.h>
#include <limits.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <ctype.h>
#include <stdarg.h>
#define __HEADERS__
#include "pvm.c"
#include "debug.c"

#define BUFF_MAX 1024

static int init_arg;
static int s_argc;
static char **s_name;
static char **s_argv;
static int *s_flag;

static void append_args(const char *form,...)
  {
   va_list ap;
   char buffer[BUFF_MAX];
   va_start(ap,form);
   vsprintf(buffer,form,ap);
   va_end(ap);
   int n=0;
   while (buffer[n]=='#') n++;
   char *p=buffer+n;
   char *q=strchr(p,'=');
   if (q==NULL) return;			
   *q='\0';
   q++;
   char *s=q;
   while (*s)
     {
      if (*s=='\n') *s='\0';
      s++;
     }
   if (strlen(p)<1 || strlen(q)<1) return;
   int i=0;
   while (i<s_argc && strcmp(p,s_name[i])) i++;
   if (i==s_argc)								
     {
      s_name=(char**)realloc(s_name,(1+s_argc)*sizeof(char*));
      s_argv=(char**)realloc(s_argv,(1+s_argc)*sizeof(char*));
      s_flag=(int*)realloc(s_flag,(1+s_argc)*sizeof(int));
      s_name[s_argc]=(char*)calloc(strlen(p)+1,sizeof(char));
      s_argv[s_argc]=(char*)calloc(strlen(q)+1,sizeof(char));
      strcpy(s_name[s_argc],p);
      strcpy(s_argv[s_argc],q);
      if (pvm_debug()==0)			
        {
         static int count;
         FILE *stream=fopen("getarg.log",count==0?"w":"a");
         fprintf(stream,"%s=%s\n",s_name[s_argc],s_argv[s_argc]);
         fclose(stream);
         count++;
        }
      s_flag[s_argc]=(n>0?0:1);			
      s_argc++;
     }
  }

int getlinearg(const char *path,int nline,const char *name)
  {
   init_args(0,NULL);
   char buffer[PATH_MAX];
   FILE *stream=fopen(path,"r");
   if (stream==NULL) debug(9,"getlinearg: file %s non trovato...\n",path);
   int nmax=0;
   while (fgets(buffer,PATH_MAX,stream)) nmax++;
   if (nmax<1) debug(9,"getlinearg: il file %s contiene %i linee...\n",path,nmax);
   rewind(stream);
   for (int i=0;i<=(nline%nmax);i++) if (fgets(buffer,PATH_MAX,stream));
   fclose(stream);
   char *p=buffer;              
   char buff2[PATH_MAX];
   strcpy(buff2,name);
   char *q=buff2;
   while (1)
     {
      while (isspace(*q)) q++;
      char *v=q;
      while (isgraph(*v)) v++;
      while (isspace(*p)) p++;
      char *z=p;
      while (isgraph(*z)) z++;
      int eol=(*v=='\0');
      *v='\0';
      *z='\0';
      append_args("%s=%s",q,p);
      if (eol) break;
      q=v+1;
      p=z+1;
     }
   return nmax;
  }

void init_args(int *argc,char ***argv)
  {
   if (init_arg) return;
   init_arg=1;
   int a_argc;
   char **a_argv;
   if (argc!=NULL && argv!=NULL)
     {
      a_argc=(*argc);
      a_argv=(*argv);
     }
   else
     {
      a_argc=0;
      a_argv=NULL;
      int pid=(int)getpid();
      char buffer[BUFF_MAX];
      sprintf(buffer,"/proc/%i/cmdline",pid);
      int fd=open(buffer,O_RDONLY);
      if (fd<0)
        {
        }
      int nr=read(fd,buffer,BUFF_MAX-1);
      if (nr<0)
        {
        }
      char *q=buffer;
      for (int i=0;i<nr;i++)
        {
         if (buffer[i]=='\0')
           {
            int l=strlen(q);
            a_argc++;
            a_argv=(char**)realloc(a_argv,a_argc*sizeof(char*));
            a_argv[a_argc-1]=(char*)calloc(l+1,sizeof(char));
            strcpy(a_argv[a_argc-1],q);
            q=buffer+i+1;
           }
        }
      if (close(fd)<0)
        {
        }
     }
   for (int i=1;i<a_argc;i++)
     {
      char *p=a_argv[i];
      while (*p && isspace(*p)) p++;
      append_args("%s",p);
     }
   FILE *stream=fopen("SEED","r");
   if (stream)
     {
      char buffer[BUFF_MAX];
      while (fgets(buffer,BUFF_MAX,stream))
        {
         char *p=buffer;
         while (*p && isspace(*p)) p++;
         if (!isalpha(*p)) continue;
         append_args("%s",p);
        }
      fclose(stream);
     }
  }

static void scan_args(const char *name,const char *form,void *ptr,const char *srem)
  {
   const char *p=name;
   while (*p=='#') p++;
   int i=0;
   while (i<s_argc && strcmp(p,s_name[i])) i++;
   if (i>=s_argc) debug(9,"getarg: errore 101...\n");
   if (strcmp(form,"%i")==0)
     {
      sscanf(s_argv[i],"%i",(int*)ptr);
     }
   else if (strcmp(form,"%le")==0)
     {
      sscanf(s_argv[i],"%le",(double*)ptr);
     }
   else if (strcmp(form,"%s")==0)
     {
      *((char**)ptr)=(char*)calloc(strlen(s_argv[i])+1,sizeof(char));
      sscanf(s_argv[i],"%s",*((char**)ptr));
     }
   else debug(9,"getarg: errore 102...\n");
   if (s_flag[i]>0)
     {
      char buffer[BUFF_MAX];
      sprintf(buffer,"%s=%s",s_name[i],s_argv[i]);
      if (srem) fprintf(stderr,"%-30s %s\n",buffer,srem); else fprintf(stderr,"%s\n",buffer);
      s_flag[i]=0;
     }
  }

int getarg_i(const char *name,int ndef,const char *srem)
  { 
   init_args();
   int n=ndef;
   append_args("%s=%i",name,n);
   scan_args(name,"%i",&n,srem);
   return n;
  }

double getarg_d(const char *name,double xdef,const char *srem)
  {
   init_args();
   double x=xdef;
   append_args("%s=%.16g",name,x);
   scan_args(name,"%le",&x,srem);
   return x;
  }

char *getarg_s(const char *name,const char *sdef,const char *srem)
  {
   init_args();
   const char *sdef2=(sdef==NULL?"NULL":sdef);
   append_args("%s=%s",name,sdef2);
   char *buff;
   scan_args(name,"%s",&buff,srem);
   return buff;
  }
#endif
#endif
