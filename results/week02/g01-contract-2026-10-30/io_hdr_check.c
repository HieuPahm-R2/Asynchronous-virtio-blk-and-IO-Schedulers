// W2-G01 compile check for kernel/io_request.h.
// Run from repo root:
//   riscv64-linux-gnu-gcc -Wall -Werror -std=gnu11 -march=rv64gc -ffreestanding
//     -fno-common -nostdlib -I kernel -fsyntax-only
//     results/week02/g01-contract-2026-10-30/io_hdr_check.c
// (one command line; wrapped here only for readability)
#include "io_request.h"

// Confirm the contract's memory-budget claim: 14 x 4-byte fields + BSIZE.
_Static_assert(sizeof(struct io_request) == 1080, "io_request size changed");
_Static_assert(IO_NREQ == 16, "IO_NREQ changed");
_Static_assert(IO_SECTORS_PER_BLOCK == 2, "sector conversion changed");

void
io_contract_compile_check(void)
{
  struct io_handle h = {0, 0};
  struct io_request *r = 0;
  (void)h;
  (void)r;
  (void)virtio_disk_io_lock;
  (void)virtio_disk_try_submit_read;
  (void)io_async_completed_locked;
  (void)io_dispatch_locked;
}
