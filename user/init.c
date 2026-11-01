// init: The initial user-level program

#include "kernel/types.h"
#include "kernel/stat.h"
#include "kernel/spinlock.h"
#include "kernel/sleeplock.h"
#include "kernel/fs.h"
#include "kernel/file.h"
#include "user/user.h"
#include "kernel/fcntl.h"

#ifdef IO_SELFTEST
// Test-only syscall (W2-I02): runs the kernel request-layer poll/wait selftest
// from process context. Only embedded/called when built with `make test-io`
// (-DIO_SELFTEST); production init never references it.
int io_selftest(void);
#endif

char *argv[] = {"sh", 0};

int
main(void)
{
  int pid, wpid;

  if (open("console", O_RDWR) < 0) {
    mknod("console", CONSOLE, 0);
    open("console", O_RDWR);
  }
  dup(0); // stdout
  dup(0); // stderr

#ifdef IO_SELFTEST
  {
    int rc = io_selftest();
    printf("IO-USER-TEST: %s (rc=%d)\n", rc == 0 ? "PASS" : "FAIL", rc);
  }
#endif

  for (;;) {
    printf("init: starting sh\n");
    pid = fork();
    if (pid < 0) {
      printf("init: fork failed\n");
      exit(1);
    }
    if (pid == 0) {
      exec("sh", argv);
      printf("init: exec sh failed\n");
      exit(1);
    }

    for (;;) {
      // this call to wait() returns if the shell exits,
      // or if a parentless process exits.
      wpid = wait((int *)0);
      if (wpid == pid) {
        // the shell exited; restart it.
        break;
      } else if (wpid < 0) {
        printf("init: wait returned an error\n");
        exit(1);
      } else {
        // it was a parentless process; do nothing.
      }
    }
  }
}
