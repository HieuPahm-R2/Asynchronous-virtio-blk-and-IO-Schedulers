// kernel/io_queue_test.c: self-test MOCK cho queue FCFS (W2-L02) và SCAN logic
// (W3-L02), Lợi. T07 backpressure, T11 drain/counters, T13 in trace cho oracle
// Python; IOQSCAN: 8 nhóm FCFS/SCAN + unlink, kernel chỉ IN trace, oracle Python
// (tests/cases/ioq_scan.py) tự tính expected.
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
#define NMAX       8 // số request tối đa của một ca SCAN
#define MOCK_SLOTS 2 // giả lập: driver nhận tối đa 2 request cùng lúc

// Khoá riêng của test: self-test chạy lúc boot, chưa cần io_lock của driver.
static struct spinlock test_lock;
static struct io_request reqs[NMAX];
static struct io_request *mock_slot[MOCK_SLOTS];
static int accepted[NMAX]; // số lần driver giả nhận mỗi request
static int mock_cap = MOCK_SLOTS; // số slot driver giả đang mở (0 = đóng cổng)
static int fails;

static int
mock_submit(struct io_request *r)
{
  for (int i = 0; i < MOCK_SLOTS && i < mock_cap; i++) {
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

static void ioq_scan_selftest(void);

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

  ioq_scan_selftest();
}

// ---------------------------------------------------------------------------
// W3-L02: self-test MOCK cho SCAN logic (contract docs/week03/interface.md).
// Mỗi ca: nạp đủ queue khi driver giả đang ĐÓNG (trace tĩnh), mở cổng, rồi
// hoàn tất ngược thứ tự (slot cao trước) cho tới khi drain. Kernel chỉ kiểm
// bất biến tài nguyên/commit; THỨ TỰ đúng do oracle Python tính độc lập.
// ---------------------------------------------------------------------------

struct scan_case {
  char *name;
  int policy;   // IO_POLICY_FCFS / IO_POLICY_SCAN
  uint head;    // logical head ban đầu
  int dir;      // IO_DIR_UP / IO_DIR_DOWN
  int cap;      // số slot driver giả khi mở cổng (1 => EAGAIN giữa vòng)
  int n;
  uint blocks[NMAX];
};

// Fixture giống hệt tests/cases/ioq_scan.py (SCAN_CASES).
static struct scan_case scan_cases[] = {
  { "fcfs",      IO_POLICY_FCFS, 40, IO_DIR_UP,   2, 5, { 70, 20, 90, 10, 50 } },
  { "scan-up",   IO_POLICY_SCAN, 40, IO_DIR_UP,   2, 5, { 70, 20, 90, 10, 50 } },
  { "scan-down", IO_POLICY_SCAN, 40, IO_DIR_DOWN, 2, 5, { 70, 20, 90, 10, 50 } },
  { "opposite",  IO_POLICY_SCAN, 40, IO_DIR_UP,   2, 2, { 10, 20 } },
  { "empty",     IO_POLICY_SCAN, 40, IO_DIR_UP,   2, 0, { 0 } },
  { "single",    IO_POLICY_SCAN, 0,  IO_DIR_UP,   2, 1, { 5 } },
  { "tie-head",  IO_POLICY_SCAN, 40, IO_DIR_UP,   2, 4, { 60, 40, 60, 40 } },
  { "eagain",    IO_POLICY_SCAN, 40, IO_DIR_UP,   1, 3, { 50, 70, 20 } },
  { "edge-up",   IO_POLICY_SCAN, 40, IO_DIR_UP,   2, 3, { 70, 20, FSSIZE - 1 } },
  { "edge-down", IO_POLICY_SCAN, 40, IO_DIR_DOWN, 2, 3, { 0, 30, 50 } },
};
#define NSCAN (sizeof(scan_cases) / sizeof(scan_cases[0]))

static int scan_fails;
static struct ioq_trace_ev evs[IOQ_TRACE_N];

static void
scheck(char *c, char *name, int ok)
{
  printk("IOQSCAN %s CHK %s %s\n", c, name, ok ? "PASS" : "FAIL");
  if (!ok)
    scan_fails++;
}

static void
reset_case(int policy, uint head, int dir)
{
  io_queue_init();
  io_queue_set_submit_for_test(mock_submit);
  io_queue_set_policy(policy);
  io_queue_set_scan_start_for_test(head, dir);
  for (int i = 0; i < MOCK_SLOTS; i++)
    mock_slot[i] = 0;
  for (int i = 0; i < NMAX; i++) {
    memset(&reqs[i], 0, sizeof(reqs[i]));
    accepted[i] = 0;
  }
  mock_cap = 0; // đóng cổng: mọi try-submit trả IO_EAGAIN
}

static void
add_req(int i, uint blockno)
{
  reqs[i].id = i;
  reqs[i].gen = 1;
  reqs[i].op = IO_OP_READ;
  reqs[i].dev = ROOTDEV;
  reqs[i].blockno = blockno;
  reqs[i].head = IO_NIL;
  reqs[i].state = IO_ALLOCATED;
  io_queue_enqueue_locked(&reqs[i]);
  io_dispatch_locked(); // như aio_read_submit: dispatch ngay sau enqueue
}

// Sau một lần dispatch dừng vì EAGAIN, trạng thái đã commit phải khớp đúng
// sự kiện cuối cùng trong trace, và số BOUNDARY trong trace = counter.
static int
commit_consistent(uint head0, int dir0)
{
  struct ioq_scan_state st;
  struct ioq_counters c;
  int n, nb = 0;
  uint h = head0;
  int d = dir0;

  io_queue_get_scan_state_locked(&st);
  io_queue_get_counters_locked(&c);
  n = io_queue_trace_snapshot_locked(evs, IOQ_TRACE_N);
  for (int i = 0; i < n; i++) {
    if (evs[i].kind == IOQ_EV_BOUNDARY)
      nb++;
    h = evs[i].head_after;
    d = evs[i].dir_after;
  }
  return st.logical_head == h && st.direction == d && nb == c.boundary_events &&
         st.boundary_events == c.boundary_events;
}

static void
print_trace(char *name, int n)
{
  for (int i = 0; i < n; i++) {
    if (evs[i].kind == IOQ_EV_DISPATCH)
      printk("IOQSCAN %s EV D seq=%d blk=%d hb=%d ha=%d db=%d da=%d\n", name,
             evs[i].seq, evs[i].blockno, evs[i].head_before, evs[i].head_after,
             evs[i].dir_before, evs[i].dir_after);
    else
      printk("IOQSCAN %s EV B bnd=%d hb=%d ha=%d db=%d da=%d\n", name,
             evs[i].boundary, evs[i].head_before, evs[i].head_after,
             evs[i].dir_before, evs[i].dir_after);
  }
  printk("IOQSCAN %s END n=%d\n", name, n);
}

static void
run_scan_case(struct scan_case *sc)
{
  struct ioq_scan_state st;
  struct ioq_counters c;
  int ok, n, ok_eagain = 1, ok_special = 1;

  acquire(&test_lock);
  reset_case(sc->policy, sc->head, sc->dir);
  for (int i = 0; i < sc->n; i++)
    add_req(i, sc->blocks[i]);

  // Cổng đóng: EAGAIN mọi lần => không commit gì (D16).
  io_queue_get_scan_state_locked(&st);
  io_queue_get_counters_locked(&c);
  ok = io_queue_count_locked() == sc->n && st.logical_head == sc->head &&
       st.direction == sc->dir && st.boundary_events == 0 &&
       io_queue_trace_snapshot_locked(evs, IOQ_TRACE_N) == 0 &&
       c.dispatched == 0 && (sc->n == 0 || c.eagain == sc->n);
  for (int i = 0; i < sc->n; i++)
    if (reqs[i].state != IO_QUEUED || accepted[i] != 0)
      ok = 0;
  int ok_closed = ok;

  // Mở cổng và drain; completion ngược thứ tự (slot cao trước).
  mock_cap = sc->cap;
  io_dispatch_locked();
  for (int guard = 0; guard < 100 && inflight() > 0; guard++) {
    if (io_queue_count_locked() > 0 && !commit_consistent(sc->head, sc->dir))
      ok_eagain = 0;
    // Ca "eagain": khi chỉ còn block 20 bị chặn sau 70, biên chưa được commit.
    if (sc->cap == 1 && io_queue_count_locked() == 1 && reqs[2].state == IO_QUEUED) {
      io_queue_get_scan_state_locked(&st);
      if (st.boundary_events != 0 || st.direction != IO_DIR_UP || st.logical_head != 70)
        ok_special = 0;
    }
    mock_complete(mock_slot[1] ? 1 : 0);
  }

  io_queue_get_counters_locked(&c);
  ok = io_queue_count_locked() == 0 && inflight() == 0 &&
       c.enqueued == (uint)sc->n && c.dispatched == (uint)sc->n && c.trace_overflow == 0;
  for (int i = 0; i < sc->n; i++)
    if (accepted[i] != 1 || reqs[i].state != IO_DONE)
      ok = 0;
  int ok_drain = ok;
  int ok_final = commit_consistent(sc->head, sc->dir);
  n = io_queue_trace_snapshot_locked(evs, IOQ_TRACE_N);
  io_queue_set_submit_for_test(0);
  release(&test_lock);

  scheck(sc->name, "closed-no-commit", ok_closed);
  scheck(sc->name, "eagain-no-commit", ok_eagain && ok_special);
  scheck(sc->name, "drain-each-once", ok_drain);
  scheck(sc->name, "state-matches-trace", ok_final);
  print_trace(sc->name, n);
}

// D17: gỡ request QUEUED ở giữa, đầu, cuối rồi enqueue thêm; FCFS phải còn
// đúng các seq còn lại theo thứ tự và tail mới phải nối đúng.
static void
run_unlink_case(void)
{
  static uint blocks[NTEST] = { 7, 2, 9, 1, 4 };
  int ok = 1, n;

  acquire(&test_lock);
  reset_case(IO_POLICY_FCFS, 0, IO_DIR_UP);
  for (int i = 0; i < NTEST; i++)
    add_req(i, blocks[i]);
  io_queue_remove_locked(&reqs[2]); // giữa
  if (io_queue_count_locked() != 4) ok = 0;
  io_queue_remove_locked(&reqs[0]); // đầu
  if (io_queue_count_locked() != 3) ok = 0;
  io_queue_remove_locked(&reqs[4]); // cuối
  if (io_queue_count_locked() != 2) ok = 0;
  add_req(5, 3);                    // seq 6 phải nối sau seq 4 (tail mới)
  if (io_queue_count_locked() != 3) ok = 0;

  mock_cap = MOCK_SLOTS;
  io_dispatch_locked();
  for (int guard = 0; guard < 100 && inflight() > 0; guard++)
    mock_complete(mock_slot[1] ? 1 : 0);
  if (io_queue_count_locked() != 0)
    ok = 0;
  for (int i = 0; i < 6; i++) {
    int removed = (i == 0 || i == 2 || i == 4);
    if (accepted[i] != (removed ? 0 : 1))
      ok = 0;
  }
  n = io_queue_trace_snapshot_locked(evs, IOQ_TRACE_N);
  io_queue_set_submit_for_test(0);
  release(&test_lock);

  scheck("unlink", "head-mid-tail", ok);
  print_trace("unlink", n);
}

static void
ioq_scan_selftest(void)
{
  for (int i = 0; i < NSCAN; i++)
    run_scan_case(&scan_cases[i]);
  run_unlink_case();

  // Trả queue về trạng thái production (FCFS, head 0) cho code thật.
  acquire(&test_lock);
  io_queue_init();
  mock_cap = MOCK_SLOTS;
  release(&test_lock);
  printk("IOQSCAN DONE fail=%d\n", scan_fails);
}

#endif // IOQ_SELFTEST
