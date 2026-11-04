// PTO-12/13/19 - Hoàng. Real virtio READ tests from init's process context.
// Only a dedicated IO_HW_SELFTEST kernel runs these tests. The host supplies
// an isolated image with known patterns in verified-free tail blocks; this
// code never writes raw disk data or runs on an ordinary production image.
#ifdef IO_HW_SELFTEST
#include "types.h"
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "spinlock.h"
#include "sleeplock.h"
#include "fs.h"
#include "buf.h"
#include "virtio.h"
#include "io_request.h"
#include "io_queue_test.h"

#define FIXTURE (FSSIZE - 32)
static int failures;
static int gap_seen;

static void
check(int ok, char *what)
{
  if (!ok) {
    failures++;
    printk("IO-HWTEST: FAIL %s\n", what);
  }
}

static void
end_case(char *name, int before)
{
  printk("IO-HWTEST: %s %s\n", name, failures == before ? "PASS" : "FAIL");
}

static int
matches(void *ptr, uint block)
{
  uchar *data = ptr;
  if (data == 0)
    return 0;
  for (uint i = 0; i < BSIZE; i++)
    if (data[i] != (uchar)(block * 17 + i * 31 + (i >> 8) * 7))
      return 0;
  return 1;
}

static struct io_handle
submit(uint block)
{
  struct io_handle h = { -1, 0 };
  check(aio_read_submit(ROOTDEV, block, &h) == 0, "submit fixture");
  return h;
}

static void
finish(struct io_handle h, uint block)
{
  check(aio_wait(h) == 0, "wait real read");
  check(aio_poll(h) == 1, "poll DONE");
  check(matches(aio_data(h), block), "1024-byte fixture pattern");
  check(aio_release(h) == 0, "release terminal");
}

static void
drained(void)
{
  struct io_stats st;
  struct io_desc_stats ds;
  struct spinlock *lk = virtio_disk_io_lock();
  io_get_stats(&st);
  virtio_disk_get_stats(&ds);
  check(st.free_req == IO_NREQ && st.queued == 0 && st.inflight == 0 &&
        st.done == 0 && st.error == 0, "request pool fully drained");
  check(ds.free_desc == NUM, "all descriptors returned");
  acquire(lk);
  check(io_queue_count_locked() == 0, "FCFS queue empty");
  release(lk);
}

static void
await_used(uint n)
{
  // Bounded scheduling loop, not a lucky sleep or fabricated device result.
  for (int i = 0; i < 200000; i++) {
    if (virtio_test_used_count() >= n)
      return;
    yield();
  }
  check(0, "real DMA used entries arrived");
}

static void
gap_reap(void)
{
  gap_seen = 1;
  virtio_test_unhold_locked(); // already holding io_lock after sleep_prepare
}

int
io_hw_selftest(void)
{
  struct io_handle h[IO_NREQ];
  struct io_handle a, b, bad;
  struct io_stats st, before_stats;
  struct io_desc_stats ds, before_desc;
  struct spinlock *lk = virtio_disk_io_lock();
  int before, n0, n1;
  uint trace[64];
  static uint order[5] = { 7, 2, 9, 1, 4 };

  printk("IO-HWTEST: begin real-virtio fixture=%d BSIZE=%d NREQ=%d\n",
         FIXTURE, BSIZE, IO_NREQ);
  before = failures;
  a = submit(FIXTURE);
  finish(a, FIXTURE);
  drained();
  end_case("T01 single-read", before);

  before = failures;
  bad.id = -7;
  bad.gen = 0x1234;
  check(aio_read_submit(ROOTDEV, FIXTURE, 0) == IO_EINVAL, "null output");
  check(aio_read_submit(ROOTDEV + 1, FIXTURE, &bad) == IO_ENODEV, "bad dev");
  check(aio_read_submit(ROOTDEV, FSSIZE, &bad) == IO_ERANGE, "bad block");
  check(bad.id == -7 && bad.gen == 0x1234, "invalid submit leaves output");
  drained();
  end_case("ARGS validation", before);

  before = failures;
  for (int i = 0; i < IO_NREQ; i++)
    h[i] = submit(FIXTURE + i);
  bad.id = -7;
  bad.gen = 0x1234;
  check(aio_read_submit(ROOTDEV, FIXTURE, &bad) == IO_EAGAIN, "pool full EAGAIN");
  check(bad.id == -7 && bad.gen == 0x1234, "pool-full output unchanged");
  io_get_stats(&st);
  check(st.free_req == 0 && st.eagain_pool > 0, "terminal slots still occupy pool");
  for (int i = 0; i < IO_NREQ; i++)
    finish(h[i], FIXTURE + i);
  drained();
  end_case("T02 pool-exhaustion", before);

  before = failures;
  a = submit(FIXTURE);
  finish(a, FIXTURE);
  b = submit(FIXTURE + 1);
  check(a.id == b.id && a.gen != b.gen, "same slot new generation");
  check(aio_poll(a) == IO_ENOENT && aio_wait(a) == IO_ENOENT &&
        aio_release(a) == IO_ENOENT && aio_data(a) == 0, "old handle denied");
  finish(b, FIXTURE + 1);
  end_case("T03 stale-handle", before);

  before = failures;
  virtio_test_hold_used(1);
  a = submit(FIXTURE);
  check(aio_poll(a) == 0 && aio_data(a) == 0, "pending is not readable");
  check(aio_release(a) == IO_EBUSY, "INFLIGHT release refused");
  b = submit(FIXTURE + 1);
  h[0] = submit(FIXTURE + 2); // two chains held; this request stays QUEUED
  acquire(lk);
  struct io_request *pending = io_lookup_handle_locked(h[0]);
  check(pending != 0 && pending->state == IO_QUEUED, "queued state retained");
  release(lk);
  check(aio_release(h[0]) == IO_EBUSY, "QUEUED release refused");
  virtio_test_hold_used(0);
  finish(a, FIXTURE);
  finish(b, FIXTURE + 1);
  finish(h[0], FIXTURE + 2);
  end_case("T04 release-active", before);

  before = failures;
  a = submit(FIXTURE + 3);
  for (int i = 0; i < 200000 && aio_poll(a) == 0; i++)
    yield();
  check(aio_poll(a) == 1, "real IRQ completed before wait");
  finish(a, FIXTURE + 3);
  end_case("T05 complete-before-wait", before);

  before = failures;
  virtio_test_hold_used(1);
  a = submit(FIXTURE + 4);
  await_used(1); // hardware finished; software terminal transition is held
  gap_seen = 0;
  io_hw_set_wait_hook(gap_reap);
  check(aio_wait(a) == 0 && gap_seen, "real-used completion in prepare/sleep gap");
  finish(a, FIXTURE + 4);
  end_case("T06 real-used-gap", before);

  before = failures;
  virtio_test_hold_used(1);
  for (int i = 0; i < 5; i++)
    h[i] = submit(FIXTURE + i);
  io_get_stats(&st);
  virtio_disk_get_stats(&ds);
  check(st.inflight == 2 && st.queued == 3 && ds.free_desc == 2,
        "two inflight three queued two free descriptors");
  check(ds.eagain_desc > 0, "partial descriptor reservation rolled back");
  virtio_test_hold_used(0); // reaping must dispatch without another submit
  for (int i = 0; i < 5; i++)
    finish(h[i], FIXTURE + i);
  drained();
  end_case("T07 descriptor-pressure-progress", before);

  before = failures;
  virtio_disk_get_stats(&before_desc);
  a = submit(FIXTURE + 5);
  check(aio_wait(a) == 0, "A completed but retained");
  check(matches(aio_data(a), FIXTURE + 5), "A retained pattern");
  b = submit(FIXTURE + 6);
  check(aio_wait(b) == 0, "B completed on reusable head");
  virtio_disk_get_stats(&ds);
  check(ds.head_reuse > before_desc.head_reuse, "head reused before A release");
  check(matches(aio_data(a), FIXTURE + 5) &&
        matches(aio_data(b), FIXTURE + 6), "separate staging results intact");
  check(aio_release(a) == 0 && aio_release(b) == 0, "release A and B");
  drained();
  end_case("T08 head-reuse", before);

  before = failures;
  uint reversed = virtio_test_reversed();
  virtio_test_hold_used(1);
  a = submit(FIXTURE + 7);
  b = submit(FIXTURE + 8);
  await_used(2);
  virtio_test_reverse_pair();
  virtio_test_hold_used(0);
  check(virtio_test_reversed() == reversed + 1, "reverse real-used pair consumed");
  finish(a, FIXTURE + 7);
  finish(b, FIXTURE + 8);
  end_case("T09 reversed-used-mapping", before);

  before = failures;
  for (int status = 1; status <= 2; status++) {
    virtio_test_hold_used(1);
    a = submit(FIXTURE + 9);
    await_used(1);
    virtio_test_status(a, status); // synthetic IOERR/UNSUPP AFTER real DMA
    virtio_test_hold_used(0);
    check(aio_wait(a) == IO_EIO && aio_poll(a) == IO_EIO && aio_data(a) == 0,
          "synthetic status returns EIO and no readable data");
    check(aio_release(a) == 0, "release ERROR slot");
    drained();
  }
  end_case("ERROR injected-status", before);

  before = failures;
  virtio_test_hold_used(1);
  a = submit(FIXTURE + 10);
  acquire(lk);
  struct io_request *live = io_lookup_handle_locked(a);
  check(live != 0 && live->state == IO_INFLIGHT && live->head >= 0,
        "submit returned after publish before terminal state");
  release(lk);
  check(aio_poll(a) == 0, "submit did not wait or invent DONE");
  virtio_test_hold_used(0);
  finish(a, FIXTURE + 10);
  end_case("T10 submit-returns-pending", before);

  before = failures;
  virtio_disk_get_stats(&before_desc);
  a = submit(FIXTURE + 11);
  b = submit(FIXTURE + 12);
  struct buf *stock = bread(ROOTDEV, FIXTURE + 31);
  check(matches(stock->data, FIXTURE + 31), "stock read while async active");
  brelse(stock);
  finish(a, FIXTURE + 11);
  finish(b, FIXTURE + 12);
  virtio_disk_get_stats(&ds);
  check(ds.completed_stock > before_desc.completed_stock, "stock owner used hardware");
  drained();
  end_case("T12 stock-async-coexist", before);

  before = failures;
  acquire(lk);
  n0 = io_queue_trace_locked(trace, NELEM(trace));
  struct ioq_counters qc;
  io_queue_get_counters_locked(&qc);
  release(lk);
  virtio_test_hold_used(1);
  for (int i = 0; i < 5; i++)
    h[i] = submit(FIXTURE + order[i]);
  virtio_test_hold_used(0);
  for (int i = 0; i < 5; i++)
    finish(h[i], FIXTURE + order[i]);
  acquire(lk);
  n1 = io_queue_trace_locked(trace, NELEM(trace));
  release(lk);
  check(n1 == n0 + 5, "five real dispatch trace entries");
  printk("IO-HWTEST: T13 seq=");
  for (int i = n0; i < n1; i++) {
    check(trace[i] == qc.enqueued + 1 + i - n0, "FCFS dispatch seq");
    printk("%d%s", trace[i] - qc.enqueued, i + 1 < n1 ? "," : "");
  }
  printk("\n");
  end_case("T13 FCFS-real-dispatch", before);

  before = failures;
  io_get_stats(&before_stats);
  for (int cycle = 0; cycle < 10; cycle++) {
    for (int i = 0; i < 4; i++)
      h[i] = submit(FIXTURE + i);
    for (int i = 0; i < 4; i++)
      finish(h[i], FIXTURE + i);
    drained();
  }
  io_get_stats(&st);
  virtio_disk_get_stats(&ds);
  check(st.submitted - before_stats.submitted == 40, "40 real reads in drain cycles");
  check(st.submitted == st.completed + st.errors, "accepted equals terminal after drain");
  check(st.released == st.submitted, "every accepted request released once");
  check(ds.completed_async == st.completed + st.errors, "driver and request counters match");
  check(st.max_inflight == 2, "observed two published unreaped requests");
  printk("IO-HWTEST: stats submitted=%d completed=%d errors=%d released=%d max_inflight=%d free_req=%d free_desc=%d eagain_desc=%d stock=%d async=%d head_reuse=%d\n",
         st.submitted, st.completed, st.errors, st.released, st.max_inflight,
         st.free_req, ds.free_desc, ds.eagain_desc, ds.completed_stock,
         ds.completed_async, ds.head_reuse);
  end_case("T11 accounting-10-cycles", before);

  printk("IO-HWTEST: %s failures=%d\n", failures == 0 ? "PASS" : "FAIL", failures);
  return failures;
}
#endif
