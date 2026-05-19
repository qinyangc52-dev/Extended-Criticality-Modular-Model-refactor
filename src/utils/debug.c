#ifndef __DEBUG_H__
#define __DEBUG_H__

void debug(int level,const char *format,...);

#ifndef __HEADERS__
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <unistd.h>

void debug(int level,const char *format,...)
  {
   va_list ap;
   va_start(ap,format);
   vfprintf(stderr,format,ap);
   va_end(ap);
   if (level==-1)
     {
      sleep(1);
     }
   else if (level==9) exit(1);
  }
#endif
#endif
