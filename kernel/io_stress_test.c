// W3-H02 - Hoàng. Multi-producer real virtio READ stress & data verification.
// Compiled only when IO_STRESS_SELFTEST is defined. Production builds compile
// only types.h and emit zero symbols from this file.
#include "types.h"

#ifdef IO_STRESS_SELFTEST
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "spinlock.h"
#include "sleeplock.h"
#include "fs.h"
#include "buf.h"
#include "virtio.h"
#include "proc.h"
#include "io_request.h"
#include "io_queue_test.h"

#define FIXTURE (FSSIZE - 32)
#define IO_STRESS_NWORKERS 4
#define IO_STRESS_READS_PER_WORKER 120
#define IO_STRESS_WINDOW 5
#define IO_STRESS_MAX_ITERS 200000
#define IO_STRESS_WATCHDOG_TICKS 600

#ifndef IO_STRESS_SEED
#define IO_STRESS_SEED 0x26128003U
#endif

struct io_stress_worker_stat {
  int pid;
  int started;
  int finished;
  uint submitted;
  uint completed;
  uint eagain_pool;
  uint poll_hits;
  uint submit_errors;
  uint wait_errors;
  uint data_errors;
  uint release_errors;
  uint watchdog_tripped;
  uint failures;
  int first_id;
  uint first_gen;
  uint first_blk;
  int last_id;
  uint last_gen;
  uint last_blk;
  uint trace_hash;
};

static struct {
  int ready;
  uint start_ticks;
  struct io_stats before_stats;
  struct io_desc_stats before_desc;
  struct ioq_counters before_q;
  struct io_stress_worker_stat w[IO_STRESS_NWORKERS];
} stress;

static uint
read_ticks(void)
{
  uint t;
  acquire(&tickslock);
  t = ticks;
  release(&tickslock);
  return t;
}

static int
matches_pattern(void *ptr, uint block)
{
  uchar *data = ptr;
  if (data == 0)
    return 0;
  for (uint i = 0; i < BSIZE; i++) {
    if (data[i] != (uchar)(block * 17 + i * 31 + (i >> 8) * 7))
      return 0;
  }
  return 1;
}

static uint
pick_fixture_block(int w, uint seq)
{
  if (seq == 0)
    return FIXTURE; // always cover first fixture block for negative control
  uint x = IO_STRESS_SEED ^ ((uint)(w + 1) * 0x9e3779b1U) ^ (seq * 0x85ebca6bU);
  x ^= x >> 16;
  x *= 0x7feb352dU;
  x ^= x >> 15;
  return FIXTURE + (x & 31U);
}

static int
io_stress_begin(void)
{
  struct spinlock *lk = virtio_disk_io_lock();
  memset(&stress, 0, sizeof(stress));
  stress.start_ticks = read_ticks();
  io_get_stats(&stress.before_stats);
  virtio_disk_get_stats(&stress.before_desc);
  acquire(lk);
  io_queue_get_counters_locked(&stress.before_q);
  release(lk);
  printk("IO-STRESS: begin workers=%d reads_per_worker=%d window=%d fixture=%d..%d seed=0x%x\n",
         IO_STRESS_NWORKERS, IO_STRESS_READS_PER_WORKER, IO_STRESS_WINDOW,
         FIXTURE, FIXTURE + 31, IO_STRESS_SEED);
  return 0;
}

static int
io_stress_run_worker(int w)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_handle win_h[IO_STRESS_WINDOW];
  uint win_blk[IO_STRESS_WINDOW];
  int win_active[IO_STRESS_WINDOW];
  struct io_stress_worker_stat local;
  int active_count = 0;
  uint iters = 0;
  uint t0 = read_ticks();

  if (w < 0 || w >= IO_STRESS_NWORKERS || myproc() == 0)
    return 1;

  memset(&local, 0, sizeof(local));
  memset(win_active, 0, sizeof(win_active));
  local.pid = myproc()->pid;
  local.started = 1;
  local.first_id = -1;
  local.last_id = -1;
  local.trace_hash = 0x811c9dc5U ^ (uint)w;

  acquire(lk);
  stress.ready++;
  stress.w[w].pid = local.pid;
  stress.w[w].started = 1;
  release(lk);

  // Brief bounded barrier so all producer processes overlap in the pool/queue.
  for (int b = 0; b < 64; b++) {
    int rdy;
    acquire(lk);
    rdy = stress.ready;
    release(lk);
    if (rdy >= IO_STRESS_NWORKERS)
      break;
    yield();
  }

  while (local.completed < IO_STRESS_READS_PER_WORKER) {
    iters++;
    if (iters > IO_STRESS_MAX_ITERS || read_ticks() - t0 > IO_STRESS_WATCHDOG_TICKS) {
      local.watchdog_tripped = 1;
      local.failures++;
      break;
    }

    // 1. Fill window up to IO_STRESS_WINDOW handles (4 * 5 = 20 > 16 pool slots).
    for (int s = 0; s < IO_STRESS_WINDOW && local.submitted < IO_STRESS_READS_PER_WORKER; s++) {
      if (win_active[s])
        continue;
      uint blk = pick_fixture_block(w, local.submitted);
      struct io_handle h = { -1, 0 };
      int rc = aio_read_submit(ROOTDEV, blk, &h);
      if (rc == 0) {
        if (h.id < 0 || h.id >= IO_NREQ || h.gen == 0) {
          local.submit_errors++;
          local.failures++;
          break;
        }
        win_h[s] = h;
        win_blk[s] = blk;
        win_active[s] = 1;
        active_count++;
        if (local.submitted == 0) {
          local.first_id = h.id;
          local.first_gen = h.gen;
          local.first_blk = blk;
        }
        local.last_id = h.id;
        local.last_gen = h.gen;
        local.last_blk = blk;
        local.trace_hash = (local.trace_hash ^ (uint)h.id) * 16777619U;
        local.trace_hash = (local.trace_hash ^ h.gen) * 16777619U;
        local.trace_hash = (local.trace_hash ^ blk) * 16777619U;
        local.submitted++;
      } else if (rc == IO_EAGAIN) {
        // Pool full under multi-producer contention: do not busy-spin; drain or yield.
        local.eagain_pool++;
        break;
      } else {
        local.submit_errors++;
        local.failures++;
        break;
      }
    }

    if (local.failures != 0)
      break;

    // Yield with active handles in flight/queued so all workers contend on the pool.
    yield();

    if (active_count == 0) {
      // Bounded yield when waiting for other workers to release pool slots.
      yield();
      continue;
    }

    // 2. Poll active handles first, then wait/verify/release one handle.
    int chosen = -1;
    for (int s = 0; s < IO_STRESS_WINDOW; s++) {
      if (!win_active[s])
        continue;
      if (chosen < 0)
        chosen = s;
      int prc = aio_poll(win_h[s]);
      if (prc == 1) {
        local.poll_hits++;
        chosen = s;
        break;
      } else if (prc < 0) {
        local.wait_errors++;
        local.failures++;
        chosen = s;
        break;
      }
    }

    if (chosen >= 0 && win_active[chosen]) {
      struct io_handle h = win_h[chosen];
      uint blk = win_blk[chosen];
      int wrc = aio_wait(h);
      if (wrc != 0 || aio_poll(h) != 1) {
        local.wait_errors++;
        local.failures++;
      } else if (!matches_pattern(aio_data(h), blk)) {
        local.data_errors++;
        local.failures++;
      }
      int rrc = aio_release(h);
      if (rrc != 0) {
        local.release_errors++;
        local.failures++;
      }
      win_active[chosen] = 0;
      active_count--;
      local.completed++;
    }
  }

  // Cleanup any remaining active handles if the loop exited early on error.
  for (int s = 0; s < IO_STRESS_WINDOW; s++) {
    if (!win_active[s])
      continue;
    (void)aio_wait(win_h[s]);
    (void)aio_release(win_h[s]);
    win_active[s] = 0;
    active_count--;
  }

  local.finished = 1;
  acquire(lk);
  stress.w[w] = local;
  release(lk);
  return local.failures == 0 ? 0 : 1;
}

static int
io_stress_finish(void)
{
  struct spinlock *lk = virtio_disk_io_lock();
  struct io_stats st;
  struct io_desc_stats ds;
  struct ioq_counters qc;
  struct io_stress_worker_stat snap_w[IO_STRESS_NWORKERS];
  int qcount;
  int failures = 0;
  uint total_submitted = 0;
  uint total_completed = 0;
  uint total_eagain_pool = 0;
  uint total_data_errors = 0;

  // Global snapshot after all workers exit.
  io_get_stats(&st);
  virtio_disk_get_stats(&ds);
  acquire(lk);
  io_queue_get_counters_locked(&qc);
  qcount = io_queue_count_locked();
  for (int w = 0; w < IO_STRESS_NWORKERS; w++)
    snap_w[w] = stress.w[w];
  release(lk);

  for (int w = 0; w < IO_STRESS_NWORKERS; w++) {
    struct io_stress_worker_stat *ws = &snap_w[w];
    printk("IO-STRESS: worker=%d pid=%d submitted=%d completed=%d eagain_pool=%d poll_hits=%d data_err=%d watchdog=%d fail=%d first=%d/%d/%d/%d last=%d/%d/%d/%d hash=0x%x\n",
           w, ws->pid, ws->submitted, ws->completed, ws->eagain_pool,
           ws->poll_hits, ws->data_errors, ws->watchdog_tripped, ws->failures,
           w, ws->first_id, ws->first_gen, ws->first_blk,
           w, ws->last_id, ws->last_gen, ws->last_blk, ws->trace_hash);
    if (!ws->started || !ws->finished || ws->pid <= 0) {
      printk("IO-STRESS: FAIL worker %d did not finish cleanly\n", w);
      failures++;
    }
    if (ws->watchdog_tripped) {
      printk("IO-STRESS: FAIL worker %d watchdog timeout\n", w);
      failures++;
    }
    if (ws->data_errors > 0) {
      printk("IO-STRESS: FAIL 1024-byte fixture pattern (worker=%d errors=%d)\n",
             w, ws->data_errors);
      failures++;
    }
    if (ws->completed != IO_STRESS_READS_PER_WORKER ||
        ws->submitted != IO_STRESS_READS_PER_WORKER || ws->failures != 0) {
      printk("IO-STRESS: FAIL worker %d counts submitted=%d completed=%d fail=%d\n",
             w, ws->submitted, ws->completed, ws->failures);
      failures++;
    }
    for (int u = 0; u < w; u++) {
      if (snap_w[u].pid == ws->pid) {
        printk("IO-STRESS: FAIL duplicate worker pid %d\n", ws->pid);
        failures++;
      }
    }
    total_submitted += ws->submitted;
    total_completed += ws->completed;
    total_eagain_pool += ws->eagain_pool;
    total_data_errors += ws->data_errors;
  }

  uint expected_total = IO_STRESS_NWORKERS * IO_STRESS_READS_PER_WORKER;
  uint delta_sub = st.submitted - stress.before_stats.submitted;
  uint delta_comp = st.completed - stress.before_stats.completed;
  uint delta_err = st.errors - stress.before_stats.errors;
  uint delta_rel = st.released - stress.before_stats.released;
  uint delta_async = ds.completed_async - stress.before_desc.completed_async;
  uint delta_enq = qc.enqueued - stress.before_q.enqueued;
  uint delta_disp = qc.dispatched - stress.before_q.dispatched;

  if (total_submitted != expected_total || total_completed != expected_total) {
    printk("IO-STRESS: FAIL total worker reads=%d/%d expected=%d\n",
           total_submitted, total_completed, expected_total);
    failures++;
  }
  if (st.free_req != IO_NREQ || st.queued != 0 || st.inflight != 0 ||
      st.done != 0 || st.error != 0) {
    printk("IO-STRESS: FAIL pool drain free_req=%d queued=%d inflight=%d done=%d error=%d\n",
           st.free_req, st.queued, st.inflight, st.done, st.error);
    failures++;
  }
  if (ds.free_desc != NUM || qcount != 0) {
    printk("IO-STRESS: FAIL descriptor/queue drain free_desc=%d qcount=%d\n",
           ds.free_desc, qcount);
    failures++;
  }
  if (delta_sub != expected_total || delta_comp != expected_total ||
      delta_err != 0 || delta_rel != expected_total ||
      delta_async != expected_total || delta_enq != expected_total ||
      delta_disp != expected_total) {
    printk("IO-STRESS: FAIL cumulative accounting sub=%d comp=%d err=%d rel=%d async=%d enq=%d disp=%d\n",
           delta_sub, delta_comp, delta_err, delta_rel, delta_async, delta_enq, delta_disp);
    failures++;
  }
  if (st.eagain_pool == 0 || total_eagain_pool == 0) {
    printk("IO-STRESS: FAIL pool exhaustion was not exercised (eagain_pool=%d)\n",
           st.eagain_pool);
    failures++;
  }
  if (st.max_inflight != 2) {
    printk("IO-STRESS: FAIL unexpected max_inflight=%d\n", st.max_inflight);
    failures++;
  }

  printk("IO-STRESS: stats workers=%d total_reads=%d submitted=%d completed=%d errors=%d released=%d max_inflight=%d free_req=%d free_desc=%d queued=%d inflight=%d done=%d error=%d eagain_pool=%d eagain_desc=%d q_enqueued=%d q_dispatched=%d q_eagain=%d head_reuse=%d data_errors=%d\n",
         IO_STRESS_NWORKERS, total_completed, st.submitted, st.completed,
         st.errors, st.released, st.max_inflight, st.free_req, ds.free_desc,
         st.queued, st.inflight, st.done, st.error, st.eagain_pool,
         ds.eagain_desc, qc.enqueued, qc.dispatched, qc.eagain,
         ds.head_reuse, total_data_errors);
  printk("IO-STRESS: %s failures=%d\n", failures == 0 ? "PASS" : "FAIL", failures);
  return failures;
}

int
io_stress_selftest(int op)
{
  if (op == -1)
    return io_stress_begin();
  if (op == -2)
    return io_stress_finish();
  return io_stress_run_worker(op);
}
#endif // IO_STRESS_SELFTEST
