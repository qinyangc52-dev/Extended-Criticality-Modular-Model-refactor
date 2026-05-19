#ifndef __FOPENF_H__
#define __FOPENF_H__
#include <stdio.h>

void rootdir(const char *format,...);
void removef(const char *format,...);
void makedir(const char *path,int mode=0755);
FILE *fopenf(const char *format,const char *mode,...);
void fprint2(FILE *stream,const char *format,...);

#ifndef __HEADERS__
#include <limits.h>
#include <stdlib.h>
#include <limits.h>
#include <string.h>
#include <stdarg.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <pwd.h>

static char *root=NULL;

void rootdir(const char *format,...)
  {
   if (format)
     {
      if (root==NULL) root=(char*)calloc(PATH_MAX,sizeof(char));
      va_list ap;
      va_start(ap,format);
      vsprintf(root,format,ap);
      va_end(ap);
     }
   else if (root)
     {
      free(root);
      root=NULL;
     }
  }

void removef(const char *format,...)
  {
   char path[PATH_MAX],buffer[2*PATH_MAX];
   va_list ap;
   va_start(ap,format);
   vsprintf(path,format,ap);
   va_end(ap);
   if (root && path[0]!='/') sprintf(buffer,"%s/%s",root,path); else strcpy(buffer,path);
   remove(buffer);
  }

void makedir(const char *path,int mode)
  {
   char buffer[PATH_MAX];
   if (root && path[0]!='/') sprintf(buffer,"%s/%s",root,path); else strcpy(buffer,path);
   char *p=buffer;
   char *q;
   while ((q=strchr(p,'/')))
     {
      *q='\0';
      mkdir(buffer,mode);
      *q='/';
      p=q+1;
     }
  }

FILE *fopenf(const char *format,const char *mode,...)
  {
   if (strcmp(mode,"r") && strcmp(mode,"w") && strcmp(mode,"a"))
     {
      fprintf(stderr,"fopenf: mode \"%s\" non riconosciuto\n",mode);
      exit(1);
     }
   char path[PATH_MAX],buffer[PATH_MAX];
   va_list ap;
   va_start(ap,mode);
   vsprintf(path,format,ap);
   va_end(ap);
   if (strncmp(path,"TMPDIR/",7)==0)
     {
      FILE *stream2=fopen(".tmpdir","r");
      if (stream2)
        {
         if (fscanf(stream2,"%s",buffer));
         fclose(stream2);
        }
      else
        {
         uid_t uid=getuid();
         struct passwd *pw=getpwuid(uid);
         sprintf(buffer,"/tmp/%s/tmpdir/",pw->pw_name);
        }
      strcat(buffer,path+6);
      strcpy(path,buffer);
     }
   if (root && path[0]!='/') sprintf(buffer,"%s/%s",root,path); else strcpy(buffer,path);
   if (strcmp(mode,"r")) makedir(buffer);
   FILE *stream=fopen(buffer,mode);
   return stream;
  }

#define BUFF_MAX 4096

void fprint2(FILE *stream,const char *format,...)
  {
   char buffer[BUFF_MAX];
   va_list ap;
   va_start(ap,format);
   vsprintf(buffer,format,ap);
   va_end(ap);
   fprintf(stream,"%s",buffer);
   printf("%s",buffer);
  }
#endif
#endif
