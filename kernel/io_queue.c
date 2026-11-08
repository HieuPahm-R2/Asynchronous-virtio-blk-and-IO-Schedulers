// kernel/io_queue.c: pending queue + dispatcher (W2-L01 FCFS, W3-L01 SCAN logic; Lợi).
// Contract: kernel/io_request.h, docs/week02/interface.md (D5, D6, D8) và
// docs/week03/interface.md (D11-D20).
//
// Queue chỉ quyết định THỨ TỰ và gọi driver. Không cấp/thu hồi slot (việc của
// io_request.c) và không đụng descriptor (việc của virtio_disk.c).
// Mọi hàm *_locked: người gọi đang giữ io_lock (= virtio_disk_io_lock()),
// không acquire lại, không ngủ, không cấp phát, không printk (có thể chạy trong IRQ).
//
// Policy:
//   - FCFS (mặc định, production): request có enqueue_seq nhỏ nhất = đầu hàng.
//   - SCAN logic (chỉ chọn được trong build test, D19): chọn request gần
//     logical_head nhất theo chiều hiện tại; hết ứng viên thì ghi sự kiện biên
//     logic (0 hoặc FSSIZE-1) rồi đảo chiều. Không phát READ giả tới biên (D15).
// Chọn (pick) là hàm thuần; head/direction/trace/unlink chỉ được commit SAU khi
// driver nhận request. IO_EAGAIN không commit gì cả (D16).

#include "types.h"
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "fs.h"
#include "io_request.h"
#include "io_queue_test.h"

static struct {
  int head;                          // id của request QUEUED đầu hàng, IO_NIL nếu rỗng
  int tail;                          // id của request QUEUED cuối hàng
  int count;                         // số request QUEUED
  uint next_seq;                     // enqueue_seq kế tiếp, bắt đầu từ 1
  struct io_request *by_id[IO_NREQ]; // id -> request, để đi theo liên kết req->next
  struct ioq_counters cnt;

  // Trạng thái điều phối đã commit (D13). FCFS không dùng head/direction.
  enum io_policy policy;
  uint logical_head;
  enum io_dir direction;

  // Trace hữu hạn các sự kiện đã commit (D18); tràn thì đếm, không ghi đè.
  struct ioq_trace_ev trace[IOQ_TRACE_N];
  int ntrace;
} q;

// Driver nhận request. Bản thật gọi thẳng try-submit của Hoàng (W2-H01);
// build self-test thay bằng driver giả, không cần driver thật để link.
#ifdef IOQ_SELFTEST
static int (*submit_fn)(struct io_request *);

void
io_queue_set_submit_for_test(int (*fn)(struct io_request *))
{
  submit_fn = fn;
}
#else
#define submit_fn virtio_disk_try_submit_read
#endif

void
io_queue_init(void)
{
  memset(&q, 0, sizeof(q));
  q.head = IO_NIL;
  q.tail = IO_NIL;
  q.next_seq = 1;
  q.policy = IO_POLICY_FCFS; // D13/D19: production luôn FCFS
  q.logical_head = 0;
  q.direction = IO_DIR_UP;
}

// Thêm req vào CUỐI hàng. Vì enqueue_seq tăng dần và luôn thêm ở cuối,
// đầu hàng luôn là request có enqueue_seq nhỏ nhất (đúng FCFS), và thứ tự
// liên kết luôn là thứ tự seq (SCAN dùng điều này cho tie-break).
// Queue không bao giờ đầy: số phần tử <= IO_NREQ = số slot của pool.
void
io_queue_enqueue_locked(struct io_request *req)
{
  if (req->state != IO_ALLOCATED)
    panic("io_queue_enqueue: state");
  if (req->id < 0 || req->id >= IO_NREQ || q.by_id[req->id] != 0)
    panic("io_queue_enqueue: id");

  req->enqueue_seq = q.next_seq++; // dưới io_lock -> không bao giờ trùng
  req->t_enqueue = ticks;
  req->next = IO_NIL;
  req->state = IO_QUEUED;

  q.by_id[req->id] = req;
  if (q.tail == IO_NIL)
    q.head = req->id;
  else
    q.by_id[q.tail]->next = req->id;
  q.tail = req->id;
  q.count++;
  q.cnt.enqueued++;
}

// Gỡ req khỏi danh sách liên kết ở đầu/giữa/cuối. Giữ head/tail/count/by_id/
// next và enqueue_seq của các request còn lại. Không kiểm state: dispatcher gọi
// hàm này SAU khi driver đã nhận (state đã là INFLIGHT/DONE/ERROR).
static void
unlink_locked(struct io_request *req)
{
  int prev = IO_NIL;
  int cur;

  if (req->id < 0 || req->id >= IO_NREQ || q.by_id[req->id] != req)
    panic("io_queue_unlink: not queued");
  for (cur = q.head; cur != IO_NIL && cur != req->id; cur = q.by_id[cur]->next)
    prev = cur;
  if (cur == IO_NIL)
    panic("io_queue_unlink: missing");

  if (prev == IO_NIL)
    q.head = req->next;
  else
    q.by_id[prev]->next = req->next;
  if (q.tail == req->id)
    q.tail = prev;
  req->next = IO_NIL;
  q.by_id[req->id] = 0;
  q.count--;
}

// D17: gỡ đúng một request QUEUED ở vị trí bất kỳ (test unlink, cancel về sau).
// Không gỡ INFLIGHT/DONE/ERROR: driver/IRQ sở hữu chúng. Request vẫn ở state
// QUEUED; người gọi (cancel/cleanup tương lai) tự quyết định state tiếp theo.
void
io_queue_remove_locked(struct io_request *req)
{
  if (req->state != IO_QUEUED)
    panic("io_queue_remove: state");
  unlink_locked(req);
}

// Policy FCFS: request đầu hàng.
static struct io_request *
fcfs_pick_locked(void)
{
  return q.head == IO_NIL ? 0 : q.by_id[q.head];
}

// Ứng viên gần head nhất theo chiều dir (D14 bước 2). Duyệt theo thứ tự liên
// kết = thứ tự enqueue_seq, chỉ thay khi block "gần hơn" hẳn, nên cùng block
// thì giữ seq nhỏ nhất.
static struct io_request *
scan_nearest_locked(enum io_dir dir)
{
  struct io_request *best = 0;

  for (int id = q.head; id != IO_NIL; id = q.by_id[id]->next) {
    struct io_request *r = q.by_id[id];
    if (dir == IO_DIR_UP) {
      if (r->blockno > q.logical_head && (best == 0 || r->blockno < best->blockno))
        best = r;
    } else {
      if (r->blockno < q.logical_head && (best == 0 || r->blockno > best->blockno))
        best = r;
    }
  }
  return best;
}

// SCAN logic (D14/D15), hàm thuần: không sửa trạng thái.
// *newdir = chiều sau khi chọn; *boundary = 1 nếu phải ghi sự kiện biên trước
// khi dispatch candidate (chỉ commit nếu driver nhận).
static struct io_request *
scan_pick_locked(enum io_dir *newdir, int *boundary)
{
  struct io_request *r;

  *newdir = q.direction;
  *boundary = 0;
  if (q.head == IO_NIL)
    return 0;

  // Bước 1: request tại head, seq nhỏ nhất (thứ tự liên kết = thứ tự seq).
  for (int id = q.head; id != IO_NIL; id = q.by_id[id]->next)
    if (q.by_id[id]->blockno == q.logical_head)
      return q.by_id[id];

  // Bước 2: gần nhất theo chiều hiện tại.
  if ((r = scan_nearest_locked(q.direction)) != 0)
    return r;

  // Bước 3: biên logic tạm, đảo chiều rồi chọn lại.
  *boundary = 1;
  *newdir = q.direction == IO_DIR_UP ? IO_DIR_DOWN : IO_DIR_UP;
  if ((r = scan_nearest_locked(*newdir)) == 0)
    panic("io_queue: scan no candidate"); // queue khác rỗng => không thể xảy ra
  return r;
}

static void
trace_add_locked(struct ioq_trace_ev *ev)
{
  if (q.ntrace < IOQ_TRACE_N)
    q.trace[q.ntrace++] = *ev;
  else
    q.cnt.trace_overflow++;
}

// Gửi xuống driver càng nhiều càng tốt theo policy.
// Gặp IO_EAGAIN đầu tiên thì dừng và KHÔNG commit gì: request ở nguyên chỗ,
// giữ enqueue_seq, vẫn QUEUED; head/direction/trace/boundary giữ nguyên.
// Lần completion/submit sau sẽ gọi lại hàm này; không spin chờ ở đây.
void
io_dispatch_locked(void)
{
  struct io_request *r;
  enum io_dir newdir;
  int boundary;

  for (;;) {
    if (q.policy == IO_POLICY_SCAN) {
      r = scan_pick_locked(&newdir, &boundary);
    } else {
      r = fcfs_pick_locked();
      newdir = q.direction;
      boundary = 0;
    }
    if (r == 0)
      return; // queue rỗng: không boundary, không đổi head/direction (R1)
    if (r->state != IO_QUEUED)
      panic("io_dispatch: state");

    int rc = submit_fn(r);
    if (rc == IO_EAGAIN) {
      q.cnt.eagain++;
      return;
    }
    if (rc != 0)
      panic("io_dispatch: submit"); // contract: try-submit chỉ trả 0 hoặc IO_EAGAIN
    // Driver đã đặt INFLIGHT trước khi publish. Thiết bị có thể đã báo xong
    // (DONE/ERROR), nhưng không thể vẫn còn QUEUED.
    if (r->state == IO_QUEUED)
      panic("io_dispatch: accepted but QUEUED");

    // ---- commit (driver đã nhận) ----
    struct ioq_trace_ev ev;
    if (boundary) {
      memset(&ev, 0, sizeof(ev));
      ev.kind = IOQ_EV_BOUNDARY;
      ev.policy = q.policy;
      ev.head_before = ev.head_after = q.logical_head; // không có I/O tới biên
      ev.dir_before = q.direction;
      ev.dir_after = newdir;
      ev.boundary = q.direction == IO_DIR_UP ? FSSIZE - 1 : 0;
      trace_add_locked(&ev);
      q.cnt.boundary_events++;
      q.direction = newdir;
    }

    unlink_locked(r);

    memset(&ev, 0, sizeof(ev));
    ev.kind = IOQ_EV_DISPATCH;
    ev.policy = q.policy;
    ev.seq = r->enqueue_seq;
    ev.blockno = r->blockno;
    ev.head_before = q.logical_head;
    ev.dir_before = q.direction;
    if (q.policy == IO_POLICY_SCAN)
      q.logical_head = r->blockno;
    ev.head_after = q.logical_head;
    ev.dir_after = q.direction;
    trace_add_locked(&ev);
    q.cnt.dispatched++;
  }
}

int
io_queue_count_locked(void)
{
  return q.count;
}

void
io_queue_get_counters_locked(struct ioq_counters *out)
{
  *out = q.cnt;
}

// Trace kiểu tuần 2: enqueue_seq của các DISPATCH theo thứ tự (oracle FCFS cũ).
int
io_queue_trace_locked(uint *out, int max)
{
  int n = 0;

  for (int i = 0; i < q.ntrace && n < max; i++)
    if (q.trace[i].kind == IOQ_EV_DISPATCH)
      out[n++] = q.trace[i].seq;
  return n;
}

void
io_queue_get_scan_state_locked(struct ioq_scan_state *out)
{
  out->policy = q.policy;
  out->logical_head = q.logical_head;
  out->direction = q.direction;
  out->boundary_events = q.cnt.boundary_events;
}

int
io_queue_trace_snapshot_locked(struct ioq_trace_ev *out, int max)
{
  int n = q.ntrace < max ? q.ntrace : max;

  for (int i = 0; i < n; i++)
    out[i] = q.trace[i];
  return n;
}

#if defined(IOQ_SELFTEST) || defined(IO_HW_SELFTEST)
// TEST-ONLY (D19): chọn policy trước request đầu tiên. Production không có hàm này.
void
io_queue_set_policy(enum io_policy policy)
{
  if (q.count != 0 || q.cnt.enqueued != 0)
    panic("io_queue_set_policy: queue used");
  if (policy != IO_POLICY_FCFS && policy != IO_POLICY_SCAN)
    panic("io_queue_set_policy: policy");
  q.policy = policy;
}
#endif

#ifdef IOQ_SELFTEST
// TEST-ONLY: đặt head/direction ban đầu cho fixture oracle (ví dụ head=40).
// Cùng điều kiện như set_policy: chỉ khi queue chưa từng nhận request.
void
io_queue_set_scan_start_for_test(uint head, int dir)
{
  if (q.count != 0 || q.cnt.enqueued != 0)
    panic("io_queue_set_scan_start: queue used");
  if (head >= FSSIZE || (dir != IO_DIR_UP && dir != IO_DIR_DOWN))
    panic("io_queue_set_scan_start: arg");
  q.logical_head = head;
  q.direction = dir;
}
#endif
