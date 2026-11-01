//
// kernel/io_request_test.c
// Kernel self-test for W2-I01: finite request pool + generation handles.
//
// Built only for `make test-io` (Makefile adds -DIO_SELFTEST and main.c calls
// io_selftest() right after io_init()). A production `make` compiles the empty
// stub at the bottom and never runs the test.
//
// Coverage (week-2 matrix): T02 pool-exhaustion, T03 stale-handle,
// T04 release-active, T11 accounting-drain (10 cycles) + buffer-address
// stability. Device/queue cases T01/T05-T10/T12/T13 belong to later cards.
//
#include "types.h"
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "spinlock.h"
#include "fs.h"
#include "io_request.h"

#ifdef IO_SELFTEST

static int io_selftest_failures;

static void
io_check(int cond, const char *test, const char *what)
{
  if (cond)
    return;
  io_selftest_failures++;
  printk("IO-SELFTEST: %s FAIL: %s\n", test, what);
}

static struct io_handle
io_handle_of(struct io_request *req)
{
  struct io_handle h;

  h.id = req->id;
  h.gen = req->gen;
  return h;
}

static void
io_case_start(const char *name)
{
  printk("IO-SELFTEST: %s ...\n", name);
}

static void
io_case_end(const char *name, int before)
{
  if (io_selftest_failures == before)
    printk("IO-SELFTEST: %s PASS\n", name);
}

void
io_selftest(void)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_handle hs[IO_NREQ];
  struct io_handle h;
  struct io_handle h1;
  struct io_handle h2;
  struct io_request *req;
  struct io_request *prev;
  struct io_request *fresh;
  struct io_stats st;
  void *buf;
  int before;
  int i;
  int rc;
  int cycles;

  printk("IO-SELFTEST: begin (NREQ=%d, BSIZE=%d)\n", IO_NREQ, BSIZE);

  // ---------------------------------------------------------------- T02
  // Fill the pool, reject request NREQ+1 without changing the accounting,
  // then release everything and check the pool returns to its initial state.
  io_case_start("T02 pool-exhaustion");
  before = io_selftest_failures;

  acquire(lk);
  for (i = 0; i < IO_NREQ; i++) {
    req = io_alloc_slot_locked();
    io_check(req != 0, "T02", "alloc within IO_NREQ");
    if (req == 0)
      break;
    hs[i] = io_handle_of(req);
  }
  io_check(i == IO_NREQ, "T02", "allocated exactly IO_NREQ slots");
  prev = io_alloc_slot_locked();
  io_check(prev == 0, "T02", "IO_NREQ+1 rejected (NULL, no panic)");
  release(lk);

  io_get_stats(&st);
  io_check(st.free_req == 0, "T02", "free_req==0 while pool full");
  io_check(st.eagain_pool == 1, "T02", "eagain_pool==1 after rejection");
  io_check(st.stale_handle == 0, "T02", "no stale-handle rejections yet");

  acquire(lk);
  for (i = 0; i < IO_NREQ; i++) {
    req = io_lookup_handle_locked(hs[i]);
    io_check(req != 0, "T02", "allocated handle validates");
    if (req == 0)
      continue;
    req->state = IO_DONE;
    rc = io_release_locked(hs[i]);
    io_check(rc == 0, "T02", "release DONE returns 0");
  }
  release(lk);

  io_get_stats(&st);
  io_check(st.free_req == IO_NREQ, "T02", "pool back to IO_NREQ free slots");
  io_case_end("T02 pool-exhaustion", before);

  // ---------------------------------------------------------------- T03
  // Release + reuse the same slot: the old handle must be rejected and must
  // never resolve to the new request's result (generation + data check).
  io_case_start("T03 stale-handle");
  before = io_selftest_failures;

  acquire(lk);
  prev = io_alloc_slot_locked();
  io_check(prev != 0, "T03", "alloc for stale-handle test");
  if (prev != 0) {
    h1 = io_handle_of(prev);
    prev->state = IO_DONE;
    rc = io_release_locked(h1);
    io_check(rc == 0, "T03", "release terminal request");
    prev = 0;

    fresh = io_alloc_slot_locked();
    io_check(fresh != 0, "T03", "realloc slot after release");
    if (fresh != 0) {
      h2 = io_handle_of(fresh);
      io_check(h1.id == h2.id, "T03", "same slot index reused");
      io_check(h1.gen != h2.gen, "T03", "generation changed on reuse");

      req = io_lookup_handle_locked(h1);
      io_check(req == 0, "T03", "stale handle rejected by lookup");
      rc = io_release_locked(h1);
      io_check(rc == IO_ENOENT, "T03", "stale release returns IO_ENOENT");

      req = io_lookup_handle_locked(h2);
      io_check(req == fresh, "T03", "fresh handle maps to the new request");

      // Put a recognisable pattern into the new request and confirm the old
      // handle still cannot reach it: stale handle never returns new results.
      memset(fresh->data, 0xa5, sizeof(fresh->data));
      req = io_lookup_handle_locked(h1);
      io_check(req == 0, "T03", "stale handle rejected after new data written");
      io_check(fresh->data[0] == 0xa5, "T03", "new request data intact");
      fresh->state = IO_DONE;
      rc = io_release_locked(h2);
      io_check(rc == 0, "T03", "release new request");
    }
  }

  h.id = -1;
  h.gen = 1;
  req = io_lookup_handle_locked(h);
  io_check(req == 0, "T03", "negative id rejected");
  h.id = IO_NREQ;
  h.gen = 1;
  req = io_lookup_handle_locked(h);
  io_check(req == 0, "T03", "id==IO_NREQ rejected");
  h.id = 0;
  h.gen = 0;
  req = io_lookup_handle_locked(h);
  io_check(req == 0, "T03", "generation 0 rejected");
  release(lk);

  io_get_stats(&st);
  io_check(st.stale_handle >= 4, "T03", "stale_handle counter incremented");
  io_case_end("T03 stale-handle", before);

  // ---------------------------------------------------------------- T04
  // Release must refuse every live state and accept only DONE/ERROR with no
  // waiter; the slot must stay allocated after a refused release.
  io_case_start("T04 release-active");
  before = io_selftest_failures;

  acquire(lk);
  prev = io_alloc_slot_locked();
  io_check(prev != 0, "T04", "alloc for release-active test");
  if (prev != 0) {
    h = io_handle_of(prev);

    prev->state = IO_ALLOCATED;
    rc = io_release_locked(h);
    io_check(rc == IO_EBUSY, "T04", "release ALLOCATED rejected");
    io_check(prev->state == IO_ALLOCATED, "T04", "ALLOCATED slot not freed");

    prev->state = IO_QUEUED;
    rc = io_release_locked(h);
    io_check(rc == IO_EBUSY, "T04", "release QUEUED rejected");
    io_check(prev->state == IO_QUEUED, "T04", "QUEUED slot not freed");

    prev->state = IO_INFLIGHT;
    rc = io_release_locked(h);
    io_check(rc == IO_EBUSY, "T04", "release INFLIGHT rejected");
    io_check(prev->state == IO_INFLIGHT, "T04", "INFLIGHT slot not freed");

    prev->state = IO_DONE;
    prev->waiters = 1;
    rc = io_release_locked(h);
    io_check(rc == IO_EBUSY, "T04", "release with waiter rejected");
    io_check(prev->state == IO_DONE, "T04", "DONE slot kept while waiter exists");

    prev->waiters = 0;
    rc = io_release_locked(h);
    io_check(rc == 0, "T04", "release terminal without waiter accepted");
    io_check(prev->state == IO_SLOT_FREE, "T04", "released slot is FREE");

    rc = io_release_locked(h);
    io_check(rc == IO_ENOENT, "T04", "released handle is stale");
  }
  release(lk);
  io_case_end("T04 release-active", before);

  // ---------------------------------------------------------------- T11
  // Ten alloc/release cycles: no leak, counters drain, buffer address stable.
  io_case_start("T11 accounting-drain");
  before = io_selftest_failures;

  acquire(lk);
  for (cycles = 0; cycles < 10; cycles++) {
    prev = io_alloc_slot_locked();
    io_check(prev != 0, "T11", "alloc in drain cycle");
    if (prev == 0)
      break;
    h = io_handle_of(prev);
    buf = prev->data;
    io_check(prev->data == buf, "T11", "buffer address stable at alloc");
    prev->state = IO_QUEUED;
    io_check(prev->data == buf, "T11", "buffer address stable in QUEUED");
    prev->state = IO_INFLIGHT;
    io_check(prev->data == buf, "T11", "buffer address stable in INFLIGHT");
    prev->state = IO_DONE;
    io_check(prev->data == buf, "T11", "buffer address stable in DONE");
    rc = io_release_locked(h);
    io_check(rc == 0, "T11", "release in drain cycle");
  }
  release(lk);

  io_get_stats(&st);
  io_check(st.free_req == IO_NREQ, "T11", "all slots FREE after 10 cycles");
  io_check(st.queued == 0, "T11", "queued==0 after drain");
  io_check(st.inflight == 0, "T11", "inflight==0 after drain");
  io_case_end("T11 accounting-drain", before);

  // ------------------------------------------------------------- summary
  if (io_selftest_failures == 0)
    printk("IO-SELFTEST: PASS (T02/T03/T04/T11, failures=0)\n");
  else
    printk("IO-SELFTEST: FAIL (failures=%d)\n", io_selftest_failures);
}

#else // !IO_SELFTEST

void
io_selftest(void)
{
}

#endif // IO_SELFTEST
