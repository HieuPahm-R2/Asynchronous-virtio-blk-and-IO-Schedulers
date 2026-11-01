//
// kernel/io_request.c
// Finite asynchronous request pool with generation handles (W2-I01).
//
// Contract: docs/week02/interface.md D2 (pool-owned staging buffer),
// D4 (handle + generation), D5 (request lifecycle), D6 (single io_lock),
// D10 (accounting). Header: kernel/io_request.h.
//
// This card implements the pool + handle primitives only. It deliberately does
// NOT talk to the queue or the device yet:
//   - W2-L01 adds the pending queue and will call io_queue_init() from io_init();
//   - W2-I02 adds poll/wait/submit wiring on top of these primitives;
//   - W2-H01/H02 add try-submit, completion and descriptor reclaim.
// The pool state is protected by the ONE io_lock domain from the driver
// (virtio_disk_io_lock(), contract D6). The kernel selftest (make test-io) is
// built from kernel/io_request_test.c.
//
#include "types.h"
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "spinlock.h"
#include "fs.h"
#include "io_request.h"

// Invariant: the whole pool lives in BSS so every header/status/buffer address
// is stable for the entire boot (contract D2/D7). No kalloc on this path.
static struct io_request io_pool[IO_NREQ];

// Incremented counters; queued/inflight/free_req are derived from slot states
// on demand so they cannot drift from the pool.
static struct io_stats io_counters;

// Generation 0 is never valid: start at 1 and skip 0 on wrap. A slot has to be
// released 2^32-1 times before an old handle could alias again; that is outside
// the MVP test scope but the wrap is handled explicitly (contract D4).
static uint
io_next_gen(uint gen)
{
  gen++;
  if (gen == 0)
    gen = 1;
  return gen;
}

// One-time boot init. Called from main() once, after virtio_disk_init() (so the
// driver lock exists) and before userinit(). Boot CPU only; no concurrency yet.
void
io_init(void)
{
  struct spinlock *lk = virtio_disk_io_lock();

  acquire(lk);
  memset(&io_counters, 0, sizeof(io_counters));
  for (int i = 0; i < IO_NREQ; i++) {
    struct io_request *req = &io_pool[i];
    memset(req, 0, sizeof(*req));
    req->id = i;
    req->gen = 1;
    req->state = IO_SLOT_FREE;
    req->op = IO_OP_READ;
    req->next = IO_NIL;
    req->head = IO_NIL;
  }
  release(lk);
  // W2-L01: call io_queue_init() here once kernel/io_queue.c lands.
}

// Try to take a FREE slot. Returns NULL if the pool is full: no sleep, no
// panic, no partial state change (contract D8, T02).
struct io_request *
io_alloc_slot_locked(void)
{
  for (int i = 0; i < IO_NREQ; i++) {
    struct io_request *req = &io_pool[i];
    if (req->state != IO_SLOT_FREE)
      continue;

    // Do not leak the previous request's disk data to the next caller. The
    // contents are still undefined until DONE (contract D2), this just makes
    // early reads deterministic instead of returning stale disk blocks.
    memset(req->data, 0, sizeof(req->data));
    req->state = IO_ALLOCATED;
    req->op = IO_OP_READ;
    req->status = 0;
    req->dev = 0;
    req->blockno = 0;
    req->enqueue_seq = 0;
    req->next = IO_NIL;
    req->head = IO_NIL;
    req->t_enqueue = 0;
    req->t_dispatch = 0;
    req->t_complete = 0;
    req->waiters = 0;
    return req;
  }

  io_counters.eagain_pool++;
  return 0;
}

// Validate a handle before any dereference: index in range, slot in use and
// generation match. Never trust caller-provided ids (T03).
struct io_request *
io_lookup_handle_locked(struct io_handle h)
{
  if (h.id < 0 || h.id >= IO_NREQ) {
    io_counters.stale_handle++;
    return 0;
  }

  struct io_request *req = &io_pool[h.id];
  if (req->state == IO_SLOT_FREE || req->gen != h.gen) {
    io_counters.stale_handle++;
    return 0;
  }
  return req;
}

// Release a terminal slot. DONE/ERROR only: DONE is not FREE because the
// caller still needs the result until it releases (contract D5, T04).
int
io_release_locked(struct io_handle h)
{
  struct io_request *req = io_lookup_handle_locked(h);
  if (req == 0)
    return IO_ENOENT;
  if (req->state != IO_DONE && req->state != IO_ERROR)
    return IO_EBUSY;
  if (req->waiters != 0)
    return IO_EBUSY;

  req->gen = io_next_gen(req->gen);
  req->state = IO_SLOT_FREE;
  req->op = IO_OP_READ;
  req->status = 0;
  req->dev = 0;
  req->blockno = 0;
  req->enqueue_seq = 0;
  req->next = IO_NIL;
  req->head = IO_NIL;
  req->t_enqueue = 0;
  req->t_dispatch = 0;
  req->t_complete = 0;
  req->waiters = 0;
  return 0;
}

// Public release wrapper (I01 slice of the I02 API): takes io_lock itself.
int
aio_release(struct io_handle h)
{
  struct spinlock *lk = virtio_disk_io_lock();
  int rc;

  acquire(lk);
  rc = io_release_locked(h);
  release(lk);
  return rc;
}

// Snapshot of the request-layer counters for tests T02/T11. queued/inflight/
// free_req are derived from the slot states so accounting cannot drift.
void
io_get_stats(struct io_stats *out)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_stats s;

  if (out == 0)
    return;

  acquire(lk);
  s = io_counters;
  s.queued = 0;
  s.inflight = 0;
  s.free_req = 0;
  for (int i = 0; i < IO_NREQ; i++) {
    switch (io_pool[i].state) {
    case IO_SLOT_FREE:
      s.free_req++;
      break;
    case IO_QUEUED:
      s.queued++;
      break;
    case IO_INFLIGHT:
      s.inflight++;
      break;
    default:
      break;
    }
  }
  release(lk);

  *out = s;
}
