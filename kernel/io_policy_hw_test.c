// W4-H01: real DMA with fixed queued inputs, checked by the independent D21/D22
// host model. Holding software reaping never fabricates device completions.
#ifdef IO_POLICY_HW_SELFTEST
#include "types.h"
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "spinlock.h"
#include "fs.h"
#include "virtio.h"
#include "io_request.h"
#include "io_queue_test.h"

#define BASE (FSSIZE - 32)
static int failures;
static struct ioq_trace_ev events[IOQ_TRACE_N];

static void
check(int ok, char *message)
{
  if (!ok) {
    failures++;
    printk("IO-REAL: FAIL %s\n", message);
  }
}

static uint
now(void)
{
  struct io_snapshot snap;
  io_get_snapshot(&snap);
  return snap.ticks_now;
}

static void
emit_event(int name, struct ioq_trace_ev *ev)
{
  if (ev->kind == IOQ_EV_DISPATCH)
    printk("IO-REAL: case=%d EV D pol=%d rsn=%d seq=%d blk=%d hb=%d ha=%d db=%d da=%d bat=%d ep=%d\n",
           name, ev->policy, ev->reason, ev->seq, ev->blockno, ev->head_before,
           ev->head_after, ev->dir_before, ev->dir_after, ev->batch_after, ev->epoch);
  else if (ev->kind == IOQ_EV_BOUNDARY)
    printk("IO-REAL: case=%d EV B bnd=%d hb=%d ha=%d db=%d da=%d ep=%d\n",
           name, ev->boundary, ev->head_before, ev->head_after, ev->dir_before,
           ev->dir_after, ev->epoch);
  else if (ev->kind == IOQ_EV_SWITCH)
    printk("IO-REAL: case=%d EV S old=%d new=%d hb=%d ha=%d da=%d bat=%d ep=%d\n",
           name, ev->old_policy, ev->policy, ev->head_before, ev->head_after,
           ev->dir_after, ev->batch_after, ev->epoch);
  else
    check(0, "unknown trace event");
}

static void
run_case(int name, int source, int target, int expire)
{
  static uint offsets[7] = {10, 11, 28, 2, 20, 0, 15};
  struct io_handle handles[7];
  uint seq[7], age[7];
  struct spinlock *lk = virtio_disk_io_lock();
  struct ioq_policy_state ps, before_retry, after_retry;
  struct ioq_scan_state scan;
  struct io_snapshot start, finish;
  int before = failures, ntrace;

  check(io_set_policy(source) == 0, "set source policy");
  virtio_test_hold_used(1);
  for (int i = 0; i < 7; i++) {
    handles[i].id = -1;
    handles[i].gen = 0;
    check(aio_read_submit(ROOTDEV, BASE + offsets[i], &handles[i]) == 0, "submit");
    acquire(lk);
    struct io_request *r = io_lookup_handle_locked(handles[i]);
    int valid = r != 0;
    seq[i] = r ? r->enqueue_seq : 0;
    age[i] = r ? r->t_enqueue : 0;
    // The first two requests occupy all complete chains. Clear only the test
    // trace at this stable boundary; do not reset policy, counters, or slots.
    if (i == 1)
      ioq_hw_trace_reset_locked_for_test();
    release(lk);
    check(valid, "lookup live handle");
  }
  if (expire) {
    uint deadline_start = now();
    while ((uint)(now() - deadline_start) < IOQ_DL_READ_EXPIRE)
      yield();
  }

  acquire(lk);
  io_snapshot_locked(&start);
  io_queue_get_policy_state_locked(&ps);
  io_queue_get_scan_state_locked(&scan);
  release(lk);
  check(start.inflight == 2 && start.queued == 5, "two real chains, five queued");
  printk("IO-REAL: case=%d INIT src=%d dst=%d expired=%d pol=%d ep=%d head=%d dir=%d bat=%d last=%d has=%d tick=%d q=%d i=%d\n",
         name, source, target, expire, ps.policy, ps.epoch, scan.logical_head,
         scan.direction, ps.batch_count, ps.last_block, ps.has_last,
         start.ticks_now, start.queued, start.inflight);
  for (int i = 2; i < 7; i++)
    printk("IO-REAL: case=%d INPUT seq=%d blk=%d tick=%d\n",
           name, seq[i], BASE + offsets[i], age[i]);

  check(io_set_policy(target) == 0, "runtime switch");
  acquire(lk);
  // Invalid/no-op APIs must not change an epoch or emit another switch.
  io_queue_get_policy_state_locked(&before_retry);
  int no_op = io_queue_set_policy_locked(target);
  int invalid = io_queue_set_policy_locked((enum io_policy)99);
  io_dispatch_locked(); // driver has no full chain: must return EAGAIN
  io_queue_get_policy_state_locked(&after_retry);
  int preserved = memcmp(&before_retry, &after_retry, sizeof(before_retry)) == 0;
  for (int i = 0; i < 7; i++) {
    struct io_request *r = io_lookup_handle_locked(handles[i]);
    if (!r || r->gen != handles[i].gen || r->enqueue_seq != seq[i] ||
        r->t_enqueue != age[i])
      preserved = 0;
  }
  release(lk);
  check(no_op == 0 && invalid == IO_EINVAL, "no-op/invalid return codes");
  check(preserved, "switch/EAGAIN/no-op keep state, gen/seq/arrival");

  virtio_test_hold_used(0);
  for (int i = 0; i < 7; i++) {
    check(aio_wait(handles[i]) == 0, "wait real completion");
    uchar *data = aio_data(handles[i]);
    int equal = data != 0;
    for (uint j = 0; data && j < BSIZE; j++)
      if (data[j] != (uchar)((BASE + offsets[i]) * 17 + j * 31 + (j >> 8) * 7))
        equal = 0;
    check(equal, "1024-byte fixture pattern");
    check(aio_release(handles[i]) == 0, "release exactly once");
    check(aio_poll(handles[i]) == IO_ENOENT, "released handle is stale");
  }
  acquire(lk);
  io_snapshot_locked(&finish);
  ntrace = io_queue_trace_snapshot_locked(events, IOQ_TRACE_N);
  release(lk);
  for (int i = 0; i < ntrace; i++)
    emit_event(name, &events[i]);
  check(finish.free_req == IO_NREQ && finish.desc.free_desc == NUM &&
        finish.queued == 0 && finish.inflight == 0 && finish.done == 0 &&
        finish.error == 0 && finish.submitted == finish.completed &&
        finish.completed == finish.released && finish.errors == 0,
        "all slots/descriptors drained");
  check(finish.trace_overflow == 0, "short trace must be complete");
  printk("IO-REAL: case=%d END tick=%d S=%d C=%d E=%d R=%d F=%d fd=%d ovf=%d n=%d fail=%d samples=%d zero_total=%d wait_sum=%d service_sum=%d total_sum=%d\n",
         name, finish.ticks_now, finish.submitted, finish.completed,
         finish.errors, finish.released, finish.free_req, finish.desc.free_desc,
         finish.trace_overflow, ntrace, failures - before,
         finish.latency.samples, finish.latency.zero_total, finish.latency.wait_sum,
         finish.latency.service_sum, finish.latency.total_sum);
}

int
io_policy_hw_selftest(void)
{
  int name = 0;
  for (int p = 0; p < IO_NPOLICY; p++)
    run_case(name++, p, p, 0);
  for (int src = 0; src < IO_NPOLICY; src++)
    for (int dst = 0; dst < IO_NPOLICY; dst++)
      if (src != dst)
        run_case(name++, src, dst, 0);
  run_case(name++, IO_POLICY_DEADLINE, IO_POLICY_DEADLINE, 1);
  printk("IO-REAL: DONE cases=%d fail=%d\n", name, failures);
  return failures;
}
#endif
