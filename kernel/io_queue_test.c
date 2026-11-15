// kernel/io_queue_test.c: self-test MOCK cho queue FCFS (W2-L02), SCAN logic
// (W3-L02), deadline + đổi policy khi có tải (W4-L01/L02), Lợi. T07 backpressure, T11 drain/counters, T13 in trace cho oracle
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
#include "virtio.h" // W4-I01: NUM cho kiểm bất biến descriptor trong snapshot
#include "io_request.h"
#include "io_queue_test.h"

#define NTEST      5
#define NMAX       12 // số request tối đa của một ca SCAN/deadline (<= IO_NREQ)
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
static void ioq_dl_selftest(void);
static void ioq_i01_selftest(void);

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
  ioq_dl_selftest();
  ioq_i01_selftest(); // W4-I01: fixture độc lập + snapshot/accounting

  // Trả queue về trạng thái production (FCFS, head 0) cho code thật.
  acquire(&test_lock);
  io_queue_init();
  mock_cap = MOCK_SLOTS;
  release(&test_lock);
  printk("IOQSCAN DONE fail=%d\n", scan_fails);
}

// ---------------------------------------------------------------------------
// W4-L01/L02: self-test MOCK cho DEADLINE và đổi policy khi có tải.
// Mỗi ca là một kịch bản thao tác (ADD/TICK/CAP/DONE/SW/DRAIN) chạy trên driver
// giả 2 slot và đồng hồ giả. Kernel chỉ kiểm bất biến (commit khớp trace, mỗi
// request đúng một lần, tuổi/seq/gen giữ nguyên) và IN trace + bản ghi SW;
// THỨ TỰ đúng do oracle Python tests/cases/ioq_policy.py tự mô phỏng kịch bản.
// ---------------------------------------------------------------------------

enum { OP_END = 0, OP_ADD, OP_TICK, OP_CAP, OP_DONE, OP_SW, OP_DRAIN };

struct dl_op {
  int op;
  int arg; // ADD: blockno; TICK: số tick; CAP: số slot mở; SW: policy
};

#define DL_NOPS 32
#define DL_NSW  10

struct dl_case {
  char *name;
  int policy; // policy ban đầu (chọn trước enqueue, D19)
  uint clock0;
  struct dl_op ops[DL_NOPS];
};

#define A(b) { OP_ADD, (b) }
#define T(n) { OP_TICK, (n) }
#define C(n) { OP_CAP, (n) }
#define DN   { OP_DONE, 0 }
#define SW(p) { OP_SW, (p) }
#define DR   { OP_DRAIN, 0 }
#define F IO_POLICY_FCFS
#define S IO_POLICY_SCAN
#define DL IO_POLICY_DEADLINE

// Fixture giống hệt tests/cases/ioq_policy.py (DL_CASES).
static struct dl_case dl_cases[] = {
  // L01: chưa có request quá hạn -> block thấp nhất, batch 4 rồi FIFO.
  { "dl-position", DL, 1000, { C(0), A(70), A(20), A(90), A(10), A(50), A(30), C(1), DR } },
  // L01: request cũ quá hạn đi trước request mới ở block thấp hơn.
  { "dl-expired-first", DL, 1000, { C(0), A(500), T(30), A(10), A(20), T(25), C(1), DR } },
  // L01: hai request cùng expiry -> hòa theo seq; request chưa quá hạn đi sau.
  { "dl-tie-expiry", DL, 1000, { C(0), A(300), A(200), T(20), A(5), T(40), C(1), DR } },
  // L01: request cũ ở block cao bị chặn bởi luồng block thấp -> FIFO ở biên batch.
  { "dl-batch-boundary", DL, 1000, { C(0), A(1000), A(9), A(8), A(7), A(6), A(5), A(4), C(1), DR } },
  // L01: luồng request mới liên tục; request cũ được phục vụ khi quá hạn/biên batch.
  { "dl-old-vs-stream", DL, 1000, { C(1), A(1), A(900), A(2), T(30), DN, A(3), T(30), DN, A(4),
                                    DN, A(5), DN, A(6), DR } },
  // L01: EAGAIN nhiều lần không được làm tăng batch/commit gì.
  { "dl-eagain", DL, 1000, { C(0), A(40), A(30), A(20), A(10), A(60), C(1), DN, C(0), A(5), A(15),
                             C(1), DR } },
  // L01: đồng hồ wrap qua 0xffffffff: so tuổi phải wrap-safe.
  { "dl-wrap", DL, 0xfffffff0U, { C(0), A(100), T(40), A(50), T(20), C(1), DR } },
  // L02: đủ 6 chiều chuyển, mỗi lần switch đều có Q>0 và I>0.
  { "sw-all6", F, 1000, { C(0), A(300), A(100), A(700), A(200), A(600), A(50), A(800), A(400), C(2),
                          SW(S), DN, SW(DL), T(60), DN, SW(S), DN, SW(F), DN, SW(DL), DN, SW(F),
                          DR } },
  // L02: no-op cùng policy, enum sai -> không đổi gì; queue rỗng vẫn switch được.
  { "sw-noop-invalid", F, 1000, { SW(F), SW(7), SW(-1), SW(S), SW(S), C(0), A(30), A(10), C(1),
                                  SW(3), SW(DL), SW(DL), DR } },
  // L02: tuổi giữ nguyên qua switch: request vào lúc FCFS vẫn quá hạn dưới DEADLINE.
  { "sw-keep-age", F, 1000, { C(1), A(1), A(400), T(45), SW(DL), T(10), A(5), A(6), DN, DR } },
  // L02: vào SCAN dùng block dispatch cuối của FCFS làm head, chiều UP; EAGAIN sau switch.
  { "sw-scan-head", F, 1000, { C(1), A(300), A(100), A(500), A(200), SW(S), C(0), A(350), C(1), DR } },
};
#define NDL (sizeof(dl_cases) / sizeof(dl_cases[0]))

#undef A
#undef T
#undef C
#undef DN
#undef SW
#undef DR
#undef F
#undef S
#undef DL

static uint fake_now;
static int dl_fails;

static uint
fake_clock(void)
{
  return fake_now;
}

struct sw_rec {
  int policy;
  int rc;
  int q;
  int i;
  uint epoch;
};

static void
dcheck(const char *tag, const char *c, const char *name, int ok, int *fails)
{
  printk("%s %s CHK %s %s\n", tag, c, name, ok ? "PASS" : "FAIL");
  if (!ok)
    (*fails)++;
}

// Trạng thái đã commit phải khớp đúng việc phát lại trace từ trạng thái đầu.
static int
dl_commit_consistent(int policy0)
{
  struct ioq_policy_state ps;
  struct ioq_scan_state ss;
  struct ioq_counters c;
  int n, nd = 0, ns = 0, pol = policy0;
  uint head = 0, batch = 0, epoch = 0, last = 0;
  int dir = IO_DIR_UP, has_last = 0;

  io_queue_get_policy_state_locked(&ps);
  io_queue_get_scan_state_locked(&ss);
  io_queue_get_counters_locked(&c);
  n = io_queue_trace_snapshot_locked(evs, IOQ_TRACE_N);
  for (int k = 0; k < n; k++) {
    struct ioq_trace_ev *e = &evs[k];
    if (e->kind == IOQ_EV_DISPATCH) {
      nd++;
      last = e->blockno;
      has_last = 1;
    } else if (e->kind == IOQ_EV_SWITCH) {
      ns++;
      pol = e->policy;
    }
    head = e->head_after;
    dir = e->dir_after;
    batch = e->batch_after;
    epoch = e->epoch;
  }
  return ps.policy == pol && ss.policy == pol && ps.epoch == epoch && ps.batch_count == batch &&
         ss.logical_head == head && ss.direction == dir && ps.has_last == has_last &&
         (!has_last || ps.last_block == last) && c.dispatched == nd &&
         c.policy_switches == ns && ps.switches == ns;
}

static void
print_dl_trace(const char *tag, char *name, int n)
{
  for (int k = 0; k < n; k++) {
    struct ioq_trace_ev *e = &evs[k];
    if (e->kind == IOQ_EV_DISPATCH)
      printk("%s %s EV D pol=%d rsn=%d seq=%d blk=%d hb=%d ha=%d db=%d da=%d bat=%d ep=%d\n",
             tag, name, e->policy, e->reason, e->seq, e->blockno, e->head_before,
             e->head_after, e->dir_before, e->dir_after, e->batch_after, e->epoch);
    else if (e->kind == IOQ_EV_BOUNDARY)
      printk("%s %s EV B bnd=%d hb=%d ha=%d db=%d da=%d ep=%d\n", tag, name, e->boundary,
             e->head_before, e->head_after, e->dir_before, e->dir_after, e->epoch);
    else
      printk("%s %s EV S old=%d new=%d hb=%d ha=%d da=%d bat=%d ep=%d\n", tag, name,
             e->old_policy, e->policy, e->head_before, e->head_after, e->dir_after,
             e->batch_after, e->epoch);
  }
  printk("%s %s END n=%d\n", tag, name, n);
}

// ---------------------------------------------------------------------------
// W4-I01: snapshot/accounting checks. The kernel checks the invariants that hold
// for every snapshot and that the unified snapshot agrees with the direct
// _locked getters (same lock domain); the independent Python oracle checks the
// counters against its own expected event list (D23).
// ---------------------------------------------------------------------------
static int
snapshot_invariants(const struct io_snapshot *s)
{
  int ok = 1;

  if (s->submitted != s->queued + s->inflight + s->completed + s->errors)
    ok = 0;
  if (s->completed + s->errors != s->released + s->done + s->error)
    ok = 0;
  if (IO_NREQ != s->free_req + s->queued + s->inflight + s->done + s->error)
    ok = 0;
  if (s->policy_switches != s->epoch) // MVP: một switch = một epoch
    ok = 0;
  if (s->desc.free_desc > NUM)
    ok = 0;
  if (s->latency.samples == 0 &&
      (s->latency.wait_sum || s->latency.service_sum || s->latency.total_sum))
    ok = 0;
  return ok;
}

static void
print_snapshot(const char *tag, char *name, const struct io_snapshot *s)
{
  printk("%s %s SNAP ticks=%d S=%d C=%d E=%d R=%d Q=%d I=%d D=%d X=%d F=%d "
         "eq=%d dlx=%d dlf=%d sw=%d ep=%d batch=%d last=%d haslast=%d bnd=%d ovf=%d "
         "fdesc=%d lat_samples=%d wait_sum=%d wait_max=%d service_sum=%d "
         "service_max=%d total_sum=%d total_max=%d zero_total=%d\n",
         tag, name, s->ticks_now, s->submitted, s->completed, s->errors, s->released,
         s->queued, s->inflight, s->done, s->error, s->free_req, s->eagain,
         s->dl_expired, s->dl_fifo, s->policy_switches, s->epoch, s->batch_count,
         s->last_block, s->has_last, s->boundary_events, s->trace_overflow,
         s->desc.free_desc, s->latency.samples, s->latency.wait_sum,
         s->latency.wait_max, s->latency.service_sum, s->latency.service_max,
         s->latency.total_sum, s->latency.total_max, s->latency.zero_total);
}

// Chạy một kịch bản fixture (ADD/TICK/CAP/DONE/SW/DRAIN) trên driver giả và
// đồng hồ giả. W4-L01/L02 dùng tag IOQDL; W4-I01 dùng tag IOQI01 và in thêm
// dòng SNAP. Kernel chỉ kiểm bất biến + in trace; thứ tự đúng do oracle Python
// độc lập tính từ contract (D18/D21/D22).
static void
run_scenario(const char *tag, char *name, int policy0, uint clock0,
             const struct dl_op *ops, int want_snap, int *fails)
{
  static uint t0[NMAX], seq0[NMAX], gen0[NMAX];
  struct sw_rec sw[DL_NSW];
  struct ioq_counters c;
  struct io_snapshot snap;
  int nreq = 0, nsw = 0, n, ok_commit = 1, ok_age = 1, ok_drain, overflow = 0;
  int have_snap = 0, ok_snap = 1;

  acquire(&test_lock);
  fake_now = clock0;
  io_queue_set_clock_for_test(fake_clock);
  reset_case(policy0, 0, IO_DIR_UP);
  mock_cap = MOCK_SLOTS;

  for (int k = 0; k < DL_NOPS && ops[k].op != OP_END; k++) {
    const struct dl_op *op = &ops[k];
    switch (op->op) {
    case OP_ADD:
      if (nreq >= NMAX)
        panic("ioq_dl: fixture too big");
      add_req(nreq, op->arg);
      t0[nreq] = reqs[nreq].t_enqueue;
      seq0[nreq] = reqs[nreq].enqueue_seq;
      gen0[nreq] = reqs[nreq].gen;
      nreq++;
      break;
    case OP_TICK:
      fake_now += op->arg;
      break;
    case OP_CAP:
      mock_cap = op->arg;
      io_dispatch_locked();
      break;
    case OP_DONE:
      if (inflight() > 0)
        mock_complete(mock_slot[1] ? 1 : 0);
      break;
    case OP_SW:
      if (nsw < DL_NSW) {
        struct ioq_policy_state ps;
        sw[nsw].policy = op->arg;
        sw[nsw].q = io_queue_count_locked();
        sw[nsw].i = inflight();
        sw[nsw].rc = io_queue_set_policy_locked((enum io_policy)op->arg);
        io_queue_get_policy_state_locked(&ps);
        sw[nsw].epoch = ps.epoch;
        nsw++;
      }
      break;
    case OP_DRAIN:
      mock_cap = MOCK_SLOTS;
      io_dispatch_locked();
      for (int guard = 0; guard < 100 && inflight() > 0; guard++)
        mock_complete(mock_slot[1] ? 1 : 0);
      break;
    }
    if (!dl_commit_consistent(policy0))
      ok_commit = 0;
  }

  io_queue_get_counters_locked(&c);
  ok_drain = io_queue_count_locked() == 0 && inflight() == 0 && c.enqueued == (uint)nreq &&
             c.dispatched == (uint)nreq;
  for (int i = 0; i < nreq; i++) {
    if (accepted[i] != 1 || reqs[i].state != IO_DONE)
      ok_drain = 0;
    if (reqs[i].t_enqueue != t0[i] || reqs[i].enqueue_seq != seq0[i] || reqs[i].gen != gen0[i])
      ok_age = 0;
  }
  overflow = c.trace_overflow;
  if (want_snap) {
    // Cùng lock domain: io_get_snapshot() tự lấy io_lock; đang giữ test_lock
    // (thứ tự test_lock -> io_lock; không nhánh io_lock nào lấy test_lock).
    struct ioq_counters c2;
    struct ioq_policy_state ps2;

    io_get_snapshot(&snap);
    io_queue_get_counters_locked(&c2);
    io_queue_get_policy_state_locked(&ps2);
    have_snap = 1;
    if (!snapshot_invariants(&snap))
      ok_snap = 0;
    // Snapshot phải khớp getter trực tiếp trong cùng lock domain.
    if (snap.policy_switches != c2.policy_switches || snap.dl_expired != c2.dl_expired ||
        snap.dl_fifo != c2.dl_fifo || snap.trace_overflow != c2.trace_overflow ||
        snap.epoch != ps2.epoch || snap.batch_count != ps2.batch_count)
      ok_snap = 0;
  }
  n = io_queue_trace_snapshot_locked(evs, IOQ_TRACE_N);
  io_queue_set_clock_for_test(0);
  io_queue_set_submit_for_test(0);
  release(&test_lock);

  dcheck(tag, name, "commit-matches-trace", ok_commit, fails);
  dcheck(tag, name, "drain-each-once", ok_drain, fails);
  dcheck(tag, name, "age-seq-gen-kept", ok_age, fails);
  dcheck(tag, name, "no-trace-overflow", overflow == 0, fails);
  if (want_snap)
    dcheck(tag, name, "snapshot-invariants", ok_snap, fails);
  for (int k = 0; k < nsw; k++)
    printk("%s %s SW pol=%d rc=%d q=%d i=%d ep=%d\n", tag, name, sw[k].policy, sw[k].rc,
           sw[k].q, sw[k].i, sw[k].epoch);
  print_dl_trace(tag, name, n);
  if (have_snap)
    print_snapshot(tag, name, &snap);
}

static void
ioq_dl_selftest(void)
{
  for (int i = 0; i < NDL; i++)
    run_scenario("IOQDL", dl_cases[i].name, dl_cases[i].policy, dl_cases[i].clock0,
                 dl_cases[i].ops, 0, &dl_fails);
  printk("IOQDL DONE fail=%d\n", dl_fails);
}

// ---------------------------------------------------------------------------
// W4-I01: fixture độc lập cho oracle deadline/switch + snapshot. Khác bộ fixture
// W4-L01/L02 ở trên: có ranh giới tuổi 49/50, wrap, EAGAIN trước/sau candidate,
// switch giữ tuổi, reset batch khi vào DEADLINE và vào SCAN lấy last_block.
// Fixture phải giống tests/cases/ioq_w4_model.py (I01_CASES).
// ---------------------------------------------------------------------------
#define A(b) { OP_ADD, (b) }
#define T(n) { OP_TICK, (n) }
#define C(n) { OP_CAP, (n) }
#define DN   { OP_DONE, 0 }
#define SW(p) { OP_SW, (p) }
#define DR   { OP_DRAIN, 0 }
#define F IO_POLICY_FCFS
#define S IO_POLICY_SCAN
#define DL IO_POLICY_DEADLINE

static struct dl_case i01_cases[] = {
  // D21: tuổi 49 < 50 => chưa expired => chọn block thấp (POSITION).
  { "i01-dl-age-before", DL, 500, { C(0), A(40), A(10), T(49), C(1), DN, DN, DR } },
  // D21: tuổi đúng 50 => expired; cùng expiry => hòa theo enqueue_seq.
  { "i01-dl-age-at", DL, 500, { C(0), A(40), A(10), T(50), C(1), DN, DN, DR } },
  // D21: expired (tuổi 51) thắng request mới ở block thấp hơn.
  { "i01-dl-age-after", DL, 500, { C(0), A(40), T(51), A(5), C(1), DN, DN, DR } },
  // D21: 4 lần POSITION rồi FIFO lấy request cũ ở block 1000 (batch boundary).
  { "i01-dl-batch-boundary", DL, 1000, { C(0), A(1000), A(9), A(8), A(7), A(6), A(5), C(1),
                                          DN, DN, DN, DN, DN, DN, DR } },
  // D21/D16: EAGAIN trước candidate (cổng đóng) không commit; sau candidate
  // (chỉ 1 slot) cũng không đổi batch/trace.
  { "i01-dl-eagain", DL, 1000, { C(0), A(40), A(30), T(60), C(1), DN, C(0), DR } },
  // D21: đồng hồ wrap qua 0xFFFFFFFF; tuổi 50 vẫn nhận đúng.
  { "i01-dl-wrap", DL, 0xfffffff0U, { C(0), A(100), T(50), A(50), C(1), DN, DN, DR } },
  // D21: nhiều expired khác tuổi -> expiry (t_enqueue) sớm nhất đi trước.
  { "i01-dl-expired-order", DL, 1000, { C(0), A(500), T(10), A(300), T(60), C(1), DN, DN, DR } },
  // D22: switch giữ nguyên t_enqueue: request cũ vẫn expired dưới DEADLINE.
  { "i01-sw-keep-age", F, 1000, { C(0), A(40), T(45), SW(DL), T(10), A(5), C(1), DN, DN, DR } },
  // D22: no-op cùng policy và enum sai không tăng epoch/counter; queue rỗng
  // vẫn switch được.
  { "i01-sw-noop-invalid", F, 1000, { SW(F), SW(9), SW(-3), SW(S), SW(S), C(0), A(30),
                                      A(10), C(1), SW(9), SW(DL), SW(DL), DR } },
  // D22: vào DEADLINE reset batch_count; nếu không reset thì lần pick kế tiếp
  // thành FIFO (sai thứ tự so với POSITION).
  { "i01-sw-batch-reset", DL, 1000, { C(0), A(1000), A(9), A(8), A(7), A(6), A(5), C(1),
                                      DN, DN, DN, SW(F), SW(DL), DN, DR } },
  // D22: vào SCAN lấy block dispatch thành công cuối (FCFS) làm head, dir UP;
  // switch khi Q>0 và I>0.
  { "i01-sw-scan-head", F, 1000, { C(1), A(300), A(100), A(500), A(200), SW(S), C(0), A(350),
                                   C(1), DR } },
  // D22: đủ 6 chiều chuyển giữa 3 policy, mỗi lần switch đều có Q>0 và I>0.
  { "i01-sw-all6", F, 1000, { C(2), A(300), A(100), A(700), A(200), A(600), A(50), A(800),
                              A(400), SW(S), SW(DL), SW(F), SW(DL), SW(S), SW(F), DR } },
};
#define NI01 (sizeof(i01_cases) / sizeof(i01_cases[0]))

#undef A
#undef T
#undef C
#undef DN
#undef SW
#undef DR
#undef F
#undef S
#undef DL

static int i01_fails;

static void
ioq_i01_selftest(void)
{
  for (int i = 0; i < NI01; i++)
    run_scenario("IOQI01", i01_cases[i].name, i01_cases[i].policy, i01_cases[i].clock0,
                 i01_cases[i].ops, 1, &i01_fails);
  printk("IOQI01 DONE fail=%d\n", i01_fails);
}

#endif // IOQ_SELFTEST
