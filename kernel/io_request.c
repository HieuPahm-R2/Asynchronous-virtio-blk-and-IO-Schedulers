//
// kernel/io_request.c
// Finite asynchronous request pool with generation handles
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
// is stable for the entire boot. No kalloc on this path.
static struct io_request io_pool[IO_NREQ];

// Incremented counters; queued/inflight/free_req are derived from slot states
// on demand so they cannot drift from the pool.
static struct io_stats io_counters;

#ifdef IO_SELFTEST
// TEST-ONLY: hooks used by kernel/io_request_test.c
// to drive completion deterministically. Declared here because aio_wait() uses
// them before their definitions below.
static void (*io_wait_gap_fn)(struct io_request *);
static struct io_request *io_timer_req;
static int io_timer_status;
static int io_timer_delay;
static void io_test_wait_gap_hook(struct io_request *req);
static int io_test_slept;
#endif

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

// Non-blocking status check (W2-I02, T05). Never sleeps, never frees the slot:
//   1 = DONE, 0 = QUEUED/INFLIGHT, IO_EIO = ERROR, IO_ENOENT = stale handle.
int
aio_poll(struct io_handle h)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_request *req;
  int rc;

  acquire(lk);
  req = io_lookup_handle_locked(h);
  if (req == 0)
    rc = IO_ENOENT;
  else if (req->state == IO_DONE)
    rc = 1;
  else if (req->state == IO_ERROR)
    rc = IO_EIO;
  else
    rc = 0;
  release(lk);
  return rc;
}

// Process-context wait for a terminal state (W2-I02, T05/T06). Never holds
// io_lock across sleep(): the pin's sleep_prepare()/release()/sleep()/acquire()
// pattern closes the lost-wakeup window. Single consumer in the MVP: a second
// concurrent wait (waiters != 0) is refused with IO_EBUSY.
int
aio_wait(struct io_handle h)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_request *req;
  int rc;

  if (myproc() == 0)
    return IO_EINVAL; // IRQ/scheduler context: never wait without a process

  acquire(lk);
  req = io_lookup_handle_locked(h);
  if (req == 0) {
    release(lk);
    return IO_ENOENT;
  }
  if (req->waiters != 0) {
    release(lk);
    return IO_EBUSY;
  }
  req->waiters = 1;

  while (req->state == IO_QUEUED || req->state == IO_INFLIGHT) {
    sleep_prepare(req); // register the channel while still holding io_lock
#ifdef IO_SELFTEST
    io_test_wait_gap_hook(req); // one-shot completion in the prepare->sleep gap
    io_test_slept = 1;
#endif
    release(lk);
    sleep();
    acquire(lk);
    // The slot cannot be released while waiters == 1, so the generation must
    // still match; check defensively instead of dereferencing a reused slot.
    if (req->gen != h.gen) {
      req->waiters = 0;
      release(lk);
      return IO_ENOENT;
    }
  }

  rc = (req->state == IO_DONE) ? 0 : IO_EIO;
  req->waiters = 0;
  release(lk);
  return rc;
}

// Return the pool-owned staging buffer for a valid handle, else NULL. The
// caller reads it after DONE and before aio_release(); never frees it (D2).
void *
aio_data(struct io_handle h)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_request *req;
  void *data;

  acquire(lk);
  req = io_lookup_handle_locked(h);
  data = (req == 0) ? 0 : req->data;
  release(lk);
  return data;
}

// Canonical request completion transition (contract D7). The driver (W2-H02)
// calls this from virtio_disk_intr() after validating the head mapping and
// copying the 1-byte device status; the test hook calls it from the gap/timer
// hooks. Must run with io_lock held; never sleeps itself (wakeup only).
void
io_async_completed_locked(struct io_request *req, int dev_status)
{
  if (req == 0 || req->state != IO_INFLIGHT)
    panic("io_async_completed");

  if (dev_status == 0) {
    req->status = 0;
    req->state = IO_DONE;
    io_counters.completed++;
  } else {
    req->status = dev_status;
    req->state = IO_ERROR;
    io_counters.errors++;
  }
  req->t_complete = ticks;
  wakeup(req);
}

#ifdef IO_SELFTEST
// ---------------------------------------------------------------------------
// TEST-ONLY hooks (see io_request.h). Defined only in -DIO_SELFTEST builds.
// ---------------------------------------------------------------------------

// One-shot hook consumed by aio_wait() inside the sleep_prepare()->sleep()
// window; fn runs with io_lock held and must not sleep.
static void
io_test_wait_gap_hook(struct io_request *req)
{
  void (*fn)(struct io_request *) = io_wait_gap_fn;

  if (fn == 0)
    return;
  io_wait_gap_fn = 0;
  fn(req);
}

void
io_test_set_wait_hook(void (*fn)(struct io_request *))
{
  io_wait_gap_fn = fn;
}

int
io_test_take_slept_flag(void)
{
  int v = io_test_slept;

  io_test_slept = 0;
  return v;
}

// Timer-driven completion: arm a request to be completed from clockintr() after
// delay_ticks ticks, so a waiter that is really SLEEPING is woken by an
// interrupt (T06b). Controlled by a tick countdown, not a wall-clock guess.
void
io_test_arm_timer_completion(struct io_handle h, int status, int delay_ticks)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_request *req;

  acquire(lk);
  req = io_lookup_handle_locked(h);
  if (req != 0 && req->state == IO_INFLIGHT) {
    io_timer_req = req;
    io_timer_status = status;
    io_timer_delay = delay_ticks;
  }
  release(lk);
}

void
io_test_timer_tick(void)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_request *req;

  if (cpuid() != 0 || io_timer_req == 0)
    return;
  if (io_timer_delay > 0) {
    io_timer_delay--;
    return;
  }
  if (holding(lk))
    return; // this CPU already holds io_lock; retry on the next tick
  acquire(lk);
  req = io_timer_req;
  io_timer_req = 0;
  if (req != 0 && req->state == IO_INFLIGHT)
    io_async_completed_locked(req, io_timer_status);
  release(lk);
}
#endif // IO_SELFTEST

