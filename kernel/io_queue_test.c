// kernel/io_queue_test.c: self-test MOCK cho queue FCFS (W2-L02, Lợi).
// T07 backpressure, T11 drain/counters, T13 in trace cho oracle Python.
// Driver giả 2 slot, KHÔNG đụng đĩa: không dùng để kết luận gì về thiết bị thật.
// Chỉ build khi bật: EXTRA_CFLAGS=-DIOQ_SELFTEST (docs/week02/loi.md).

#ifdef IOQ_SELFTEST

#include "types.h"
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "spinlock.h"
#include "fs.h"
#include "io_request.h"
#include "io_queue_test.h"

#define NTEST      5
#define MOCK_SLOTS 2 // giả lập: driver nhận tối đa 2 request cùng lúc

// Khoá riêng của test: self-test chạy lúc boot, chưa cần io_lock của driver.
static struct spinlock test_lock;
static struct io_request reqs[NTEST];
static struct io_request *mock_slot[MOCK_SLOTS];
static int accepted[NTEST]; // số lần driver giả nhận mỗi request
static int fails;

static int
mock_submit(struct io_request *r)
{
  for (int i = 0; i < MOCK_SLOTS; i++) {
    if (mock_slot[i] == 0) {
      mock_slot[i] = r;
      r->state = IO_INFLIGHT;
      accepted[r->id]++;
      return 0;
    }
  }
  return IO_EAGAIN;
}

// Giả lập IRQ: hoàn tất request ở slot s rồi kích dispatch.
// Không có submit mới nào ở đây: đó chính là điều T07 kiểm.
static void
mock_complete(int s)
{
  struct io_request *r = mock_slot[s];

  mock_slot[s] = 0;
  r->status = 0;
  r->state = IO_DONE;
  io_dispatch_locked();
}

static int
inflight(void)
{
  int c = 0;

  for (int i = 0; i < MOCK_SLOTS; i++)
    if (mock_slot[i])
      c++;
  return c;
}

static void
check(char *test, char *name, int ok)
{
  printk("IOQTEST MOCK %s %s %s\n", test, name, ok ? "PASS" : "FAIL");
  if (!ok)
    fails++;
}

void
ioq_selftest(void)
{
  // Fixture cố định, block KHÔNG tăng dần: FCFS phải theo seq, không theo block.
  static uint blocks[NTEST] = { 7, 2, 9, 1, 4 };
  struct ioq_counters c;
  uint trace[NTEST * 2];
  int ok, n;

  initlock(&test_lock, "ioq_test");
  io_queue_init();
  io_queue_set_submit_for_test(mock_submit);

  acquire(&test_lock);
  for (int i = 0; i < NTEST; i++) {
    reqs[i].id = i;
    reqs[i].gen = 1;
    reqs[i].op = IO_OP_READ;
    reqs[i].dev = ROOTDEV;
    reqs[i].blockno = blocks[i];
    reqs[i].head = IO_NIL;
    reqs[i].state = IO_ALLOCATED;
    io_queue_enqueue_locked(&reqs[i]);
    io_dispatch_locked();
  }

  // Sau 5 submit với 2 slot: 2 INFLIGHT, 3 còn QUEUED, đã gặp EAGAIN.
  io_queue_get_counters_locked(&c);
  check("T07", "two-inflight", inflight() == 2);
  check("T07", "three-queued", io_queue_count_locked() == 3);
  check("T07", "eagain-seen", c.eagain > 0);
  ok = 1;
  for (int i = 2; i < NTEST; i++)
    if (reqs[i].state != IO_QUEUED)
      ok = 0;
  check("T07", "eagain-keeps-queued", ok);

  // Hoàn tất 1 request, KHÔNG submit thêm: request seq 3 phải tự được gửi.
  mock_complete(0);
  check("T07", "progress-after-complete", reqs[2].state == IO_INFLIGHT);

  // Drain, cố ý hoàn tất slot cao trước (thứ tự completion khác thứ tự dispatch).
  for (int guard = 0; guard < 100 && inflight() > 0; guard++)
    mock_complete(mock_slot[1] ? 1 : 0);

  io_queue_get_counters_locked(&c);
  check("T11", "drain-queue-empty", io_queue_count_locked() == 0);
  check("T11", "drain-no-inflight", inflight() == 0);
  check("T11", "counters", c.enqueued == NTEST && c.dispatched == NTEST);
  ok = 1;
  for (int i = 0; i < NTEST; i++)
    if (accepted[i] != 1 || reqs[i].state != IO_DONE)
      ok = 0;
  check("T07", "each-dispatched-once", ok);
  n = io_queue_trace_locked(trace, NTEST * 2);

  // Trả queue về trạng thái sạch cho code thật (io_init sẽ init lại lần nữa).
  io_queue_init();
  io_queue_set_submit_for_test(0);
  release(&test_lock);

  // In trace để oracle bên Python so. Kernel KHÔNG tự so thứ tự với đáp án.
  printk("IOQTEST MOCK T13 seq=");
  for (int i = 0; i < n; i++)
    printk("%d%s", trace[i], i + 1 < n ? "," : "");
  printk("\n");
  printk("IOQTEST MOCK T13 blk=");
  for (int i = 0; i < n; i++)
    printk("%d%s", reqs[trace[i] - 1].blockno, i + 1 < n ? "," : "");
  printk("\n");
  printk("IOQTEST MOCK DONE fail=%d\n", fails);
}

#endif // IOQ_SELFTEST
