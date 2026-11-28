// PTO-41 driver selftest. Run only on a copied image populated by the host.
#ifdef IO_MERGE_SELFTEST
#include "types.h"
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "spinlock.h"
#include "fs.h"
#include "io_request.h"

#define FIXTURE (FSSIZE - 32)

enum read_result {
  READ_OK,
  INJECTED_ERROR,
  DEVICE_ERROR,
};

struct read_group {
  int count;
  struct io_request *req[IO_MERGE_MAX_CHILDREN];
  struct io_handle handle[IO_MERGE_MAX_CHILDREN];
};

static void
expect(int ok, char *message)
{
  if (!ok) {
    printk("IO-MERGE: FAIL %s\n", message);
    panic("io_merge_selftest");
  }
}

static void
stage(struct read_group *group, uint first, int count, int reverse)
{
  group->count = count;
  for (int i = 0; i < count; i++) {
    uint block = first + (reverse ? count - 1 - i : i);
    struct io_request *req = io_merge_test_stage_locked(block);
    group->req[i] = req;
    group->handle[i] = (struct io_handle){req->id, req->gen};
  }
}

static int
submit(struct read_group *group)
{
  return virtio_disk_try_submit_merged_read(group->req, group->count);
}

static int
shared_head(struct read_group *group)
{
  int head = group->req[0]->head;
  for (int i = 0; i < group->count; i++)
    expect(head >= 0 && group->req[i]->head == head &&
           group->req[i]->state == IO_INFLIGHT, "shared inflight head");
  return head;
}

static void
expect_queued(struct read_group *group)
{
  for (int i = 0; i < group->count; i++)
    expect(group->req[i]->state == IO_QUEUED && group->req[i]->head == IO_NIL,
           "failed submit leaves group queued");
}

static void
finish(struct read_group *group, int error)
{
  for (int i = 0; i < group->count; i++) {
    struct io_handle h = group->handle[i];
    uint block = group->req[i]->blockno;
    expect(aio_wait(h) == (error ? IO_EIO : 0), "wait result");
    expect(aio_poll(h) == (error ? IO_EIO : 1), "poll result");
    uchar *data = aio_data(h);
    if (error) {
      expect(data == 0, "error has no readable data");
    } else {
      expect(data != 0, "successful child has data");
      uint checksum = 2166136261U;
      for (uint j = 0; j < BSIZE; j++) {
        expect(data[j] == (uchar)(block * 17 + j * 31 + (j >> 8) * 7),
               "child block bytes");
        checksum = (checksum ^ data[j]) * 16777619U;
      }
      printk("IO-MERGE: child block=%d bytes=%d fnv1a=%x\n", block, BSIZE, checksum);
    }
    expect(aio_release(h) == 0, "release terminal child");
    expect(aio_poll(h) == IO_ENOENT, "stale generation rejected");
  }
}

static void
require_used(uint count)
{
  uint since = ticks;
  while (virtio_test_used_count() < count)
    expect(ticks - since < 30, "device did not post used entries");
}

static void
one_command(uint first, int count, int reverse, enum read_result result)
{
  struct spinlock *lock = virtio_disk_io_lock();
  struct io_merge_test_snapshot before, after;
  struct io_stats req_before, req_after;
  struct read_group group;

  if (result != READ_OK)
    virtio_test_hold_used(1);

  acquire(lock);
  virtio_merge_test_snapshot_locked(&before);
  io_get_stats_locked(&req_before);
  stage(&group, first, count, reverse);
  expect(submit(&group) == 0, "submit merged read");
  int head = shared_head(&group);
  release(lock);

  if (result != READ_OK) {
    require_used(1);
    for (int i = 0; i < count; i++) {
      expect(aio_poll(group.handle[i]) == 0, "child stays live until reaped");
      expect(aio_release(group.handle[i]) == IO_EBUSY, "early release denied");
    }
    if (result == INJECTED_ERROR)
      virtio_test_status(group.handle[0], 1);
    virtio_test_hold_used(0);
  }
  finish(&group, result != READ_OK);

  acquire(lock);
  io_get_stats_locked(&req_after);
  virtio_merge_test_snapshot_locked(&after);
  release(lock);
  expect((uint16)(after.published - before.published) == 1 &&
         (uint16)(after.reaped - before.reaped) == 1 &&
         after.used_head == (uint)head, "exactly one published and used head");
  expect(after.free_bounce == before.free_bounce, "bounce reclaimed");
  expect(req_after.completed - req_before.completed == (result == READ_OK ? count : 0) &&
         req_after.errors - req_before.errors == (result == READ_OK ? 0 : count),
         "terminal count per child");
  char *label = result == READ_OK ? "read" :
                result == DEVICE_ERROR ? "device-EIO" : "injected-EIO";
  printk("IO-MERGE: %s children=%d reverse=%d published=1 used=1 head=%d PASS\n",
         label, count, reverse, head);
}

static void
pressure(int use_single)
{
  struct spinlock *lock = virtio_disk_io_lock();
  struct read_group active[2], pending;
  struct io_merge_test_snapshot before, after;
  struct io_desc_stats desc_before, desc_after;

  virtio_test_hold_used(1);
  acquire(lock);
  for (int i = 0; i < 2; i++) {
    stage(&active[i], FIXTURE + 16 + i * 2, use_single ? 1 : 2, 0);
    int rc = use_single ? virtio_disk_try_submit_read(active[i].req[0]) :
                         submit(&active[i]);
    expect(rc == 0, "fill descriptor queue");
  }
  stage(&pending, FIXTURE + 20, 2, 1);
  virtio_merge_test_snapshot_locked(&before);
  virtio_disk_get_stats_locked(&desc_before);
  expect(before.free_bounce == (use_single ? 2 : 0) &&
         desc_before.free_desc == 2, "expected pressure setup");

  expect(submit(&pending) == IO_EAGAIN, "resource pressure returns EAGAIN");
  expect_queued(&pending);
  virtio_merge_test_snapshot_locked(&after);
  virtio_disk_get_stats_locked(&desc_after);
  expect(after.published == before.published && after.reaped == before.reaped &&
         after.free_bounce == before.free_bounce &&
         desc_after.free_desc == desc_before.free_desc &&
         desc_after.eagain_desc - desc_before.eagain_desc == (uint)use_single,
         "failed reservation changes no resources");
  release(lock);

  require_used(2);
  virtio_test_hold_used(0);

  acquire(lock);
  expect(submit(&pending) == 0, "retry succeeds after reaping");
  release(lock);

  for (int i = 0; i < 2; i++)
    finish(&active[i], 0);
  finish(&pending, 0);
  printk("IO-MERGE: %s-pressure EAGAIN retry=OK PASS\n",
         use_single ? "descriptor" : "bounce");
}

static void
invalid_group(void)
{
  struct spinlock *lock = virtio_disk_io_lock();
  struct read_group group;
  struct io_merge_test_snapshot before, after;

  acquire(lock);
  stage(&group, FIXTURE + 24, 2, 0);
  virtio_merge_test_snapshot_locked(&before);
  group.req[1]->blockno++;
  expect(submit(&group) == IO_EINVAL, "reject gap");
  group.req[1]->blockno = group.req[0]->blockno;
  expect(submit(&group) == IO_EINVAL, "reject duplicate");
  group.req[1]->blockno++;
  expect_queued(&group);
  virtio_merge_test_snapshot_locked(&after);
  expect(after.published == before.published && after.free_bounce == before.free_bounce,
         "invalid groups publish nothing");
  expect(submit(&group) == 0, "submit corrected group");
  release(lock);
  finish(&group, 0);
  printk("IO-MERGE: gap duplicate EINVAL recovery=OK PASS\n");
}

int
io_merge_selftest(void)
{
  one_command(FIXTURE, 2, 0, READ_OK);
  one_command(FIXTURE + 2, 3, 1, READ_OK);
  one_command(FIXTURE + 5, 4, 1, READ_OK);
  one_command(FIXTURE + 9, 4, 0, INJECTED_ERROR);
  // The host truncates the last four verified-free blocks of the image.
  // This read straddles QEMU's device capacity; no status override is used.
  one_command(FSSIZE - 6, 4, 0, DEVICE_ERROR);
  pressure(0);
  pressure(1);
  invalid_group();

  struct io_stats req;
  struct io_desc_stats desc;
  struct io_merge_test_snapshot ring;
  struct spinlock *lock = virtio_disk_io_lock();
  acquire(lock);
  io_get_stats_locked(&req);
  virtio_disk_get_stats_locked(&desc);
  virtio_merge_test_snapshot_locked(&ring);
  release(lock);
  expect(req.free_req == IO_NREQ && desc.free_desc == 8 && ring.free_bounce == 2 &&
         req.queued == 0 && req.inflight == 0 && req.done == 0 && req.error == 0 &&
         req.completed + req.errors == req.submitted && req.released == req.submitted,
         "all resources recovered");
  printk("IO-MERGE: drain done=%d error=%d released=%d free_req=%d free_desc=%d free_bounce=%d\n",
         req.completed, req.errors, req.released, req.free_req, desc.free_desc, ring.free_bounce);
  printk("IO-MERGE: PASS\n");
  return 0;
}
#endif
