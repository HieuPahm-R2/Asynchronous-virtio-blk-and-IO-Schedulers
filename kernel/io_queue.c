// kernel/io_queue.c: pending queue + dispatcher (W2-L01 FCFS, W3-L01 SCAN logic,
// W4-L01 deadline, W4-L02 runtime switch; Lợi).
// Contract: kernel/io_request.h, docs/week02/interface.md (D5, D6, D8),
// docs/week03/interface.md (D11-D20) và docs/week04/interface.md (D21/D22, đề xuất).
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
//   - DEADLINE (W4-L01, D21 đề xuất): tuổi = now - t_enqueue (so wrap-safe).
//     Có request quá hạn (tuổi >= IOQ_DL_READ_EXPIRE) thì lấy expiry sớm nhất,
//     hòa theo seq. Không có: chọn block thấp nhất (hòa seq); sau IOQ_DL_BATCH
//     lần chọn theo vị trí liên tiếp thì lấy FIFO cũ nhất. Đây là ngưỡng tuổi để
//     ưu tiên dispatch, KHÔNG bảo đảm hoàn tất trước hạn (không phải EDF).
// Chọn (pick) là hàm thuần; head/direction/batch/trace/unlink chỉ được commit SAU
// khi driver nhận request. IO_EAGAIN không commit gì cả (D16).
// Đổi policy khi có tải (W4-L02, D22): io_queue_set_policy_locked(), xem dưới.

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

  // W4-L01/L02: trạng thái deadline/switch đã commit.
  uint batch_count; // số lần DEADLINE chọn theo vị trí liên tiếp
  uint last_block;  // block của dispatch thành công gần nhất, mọi policy
  int has_last;     // 0 cho tới dispatch thành công đầu tiên
  uint epoch;       // +1 mỗi lần switch đã commit

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

// Nguồn thời gian của deadline = ticks của xv6 (đơn vị tick, ~100 ms trên QEMU
// mặc định của pin). Đọc một word KHÔNG lấy tickslock, giống t_enqueue tuần 2:
// giữ io_lock rồi acquire tickslock sẽ mở thêm một thứ tự khóa không cần thiết.
// Build self-test có thể thay bằng đồng hồ giả để fixture xác định.
#ifdef IOQ_SELFTEST
static uint (*clock_fn)(void);

void
io_queue_set_clock_for_test(uint (*fn)(void))
{
  clock_fn = fn;
}

static uint
now_locked(void)
{
  return clock_fn ? clock_fn() : ticks;
}
#else
static uint
now_locked(void)
{
  return ticks;
}
#endif

// Tuổi wrap-safe: đúng khi tuổi thực < 2^31 tick (miền đã chốt ở D21).
static int
dl_expired(struct io_request *r, uint now)
{
  return (int)(now - r->t_enqueue) >= IOQ_DL_READ_EXPIRE;
}

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
  req->t_enqueue = now_locked(); // tuổi deadline tính từ đây, không reset (D21/D22)
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

// DEADLINE (D21), hàm thuần: trả candidate và lý do; không sửa batch/trace.
static struct io_request *
deadline_pick_locked(uint now, enum ioq_reason *rsn)
{
  struct io_request *best = 0;

  *rsn = IOQ_RSN_NONE;
  if (q.head == IO_NIL)
    return 0;

  // Bước 1: expired có expiry sớm nhất. Expiry = t_enqueue + hằng số, nên so
  // t_enqueue (wrap-safe); duyệt theo thứ tự liên kết = seq nên hòa giữ seq nhỏ.
  for (int id = q.head; id != IO_NIL; id = q.by_id[id]->next) {
    struct io_request *r = q.by_id[id];
    if (!dl_expired(r, now))
      continue;
    if (best == 0 || (int)(r->t_enqueue - best->t_enqueue) < 0)
      best = r;
  }
  if (best) {
    *rsn = IOQ_RSN_EXPIRED;
    return best;
  }

  // Bước 2: chạm giới hạn batch -> FIFO cũ nhất (đầu hàng, seq nhỏ nhất).
  if (q.batch_count >= IOQ_DL_BATCH) {
    *rsn = IOQ_RSN_FIFO;
    return q.by_id[q.head];
  }

  // Bước 3: block thấp nhất, hòa seq (chỉ thay khi nhỏ hơn hẳn).
  for (int id = q.head; id != IO_NIL; id = q.by_id[id]->next) {
    struct io_request *r = q.by_id[id];
    if (best == 0 || r->blockno < best->blockno)
      best = r;
  }
  *rsn = IOQ_RSN_POSITION;
  return best;
}

static void
trace_add_locked(struct ioq_trace_ev *ev)
{
  if (q.ntrace < IOQ_TRACE_N)
    q.trace[q.ntrace++] = *ev;
  else
    q.cnt.trace_overflow++;
}

#ifdef IO_POLICY_HW_SELFTEST
void
ioq_hw_trace_reset_locked_for_test(void)
{
  if (q.count != 0)
    panic("real trace reset: queued");
  q.ntrace = 0;
}
#endif

// Gửi xuống driver càng nhiều càng tốt theo policy.
// Gặp IO_EAGAIN đầu tiên thì dừng và KHÔNG commit gì: request ở nguyên chỗ,
// giữ enqueue_seq, vẫn QUEUED; head/direction/trace/boundary giữ nguyên.
// Lần completion/submit sau sẽ gọi lại hàm này; không spin chờ ở đây.
void
io_dispatch_locked(void)
{
  struct io_request *r;
  enum io_dir newdir;
  enum ioq_reason rsn;
  int boundary;

  for (;;) {
    // Recheck expired trước MỖI lần chọn (D21): now đọc lại mỗi vòng.
    newdir = q.direction;
    boundary = 0;
    rsn = IOQ_RSN_NONE;
    if (q.policy == IO_POLICY_SCAN)
      r = scan_pick_locked(&newdir, &boundary);
    else if (q.policy == IO_POLICY_DEADLINE)
      r = deadline_pick_locked(now_locked(), &rsn);
    else
      r = fcfs_pick_locked();
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
      ev.old_policy = q.policy;
      ev.batch_after = q.batch_count;
      ev.epoch = q.epoch;
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
    if (q.policy == IO_POLICY_DEADLINE) {
      if (rsn == IOQ_RSN_POSITION) {
        q.batch_count++;
      } else {
        q.batch_count = 0; // EXPIRED/FIFO mở batch mới
        if (rsn == IOQ_RSN_EXPIRED)
          q.cnt.dl_expired++;
        else
          q.cnt.dl_fifo++;
      }
    }
    // D22: nhớ block dispatch cuối ở MỌI policy (logical_head chỉ đổi ở SCAN).
    q.last_block = r->blockno;
    q.has_last = 1;
    ev.head_after = q.logical_head;
    ev.dir_after = q.direction;
    ev.reason = rsn;
    ev.batch_after = q.batch_count;
    ev.old_policy = q.policy;
    ev.epoch = q.epoch;
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

void
io_queue_get_policy_state_locked(struct ioq_policy_state *out)
{
  out->policy = q.policy;
  out->epoch = q.epoch;
  out->switches = q.cnt.policy_switches;
  out->batch_count = q.batch_count;
  out->last_block = q.last_block;
  out->has_last = q.has_last;
}

static int
policy_valid(int policy)
{
  return policy == IO_POLICY_FCFS || policy == IO_POLICY_SCAN ||
         policy == IO_POLICY_DEADLINE;
}

// W4-L02 (D22): đổi policy khi đang có tải, tại điểm giữa hai lần dispatch
// (người gọi giữ io_lock nên không có pick nào đang chạy dở). Không đụng queue
// hay request: id/gen/seq/t_enqueue giữ nguyên, INFLIGHT của policy cũ hoàn tất
// bình thường qua IRQ. Không dispatch ở đây; lần pick kế tiếp dùng policy mới.
int
io_queue_set_policy_locked(enum io_policy policy)
{
  struct ioq_trace_ev ev;

  if (!policy_valid(policy))
    return IO_EINVAL; // kiểm enum TRƯỚC mọi thay đổi
  if (policy == q.policy)
    return 0; // no-op: không tăng epoch/counter, không ghi event

  memset(&ev, 0, sizeof(ev));
  ev.kind = IOQ_EV_SWITCH;
  ev.old_policy = q.policy;
  ev.policy = policy;
  ev.head_before = q.logical_head;
  ev.dir_before = q.direction;

  if (policy == IO_POLICY_SCAN) {
    q.logical_head = q.has_last ? q.last_block : 0;
    q.direction = IO_DIR_UP;
  }
  if (policy == IO_POLICY_DEADLINE)
    q.batch_count = 0;
  q.policy = policy;
  q.epoch++;
  q.cnt.policy_switches++;

  ev.head_after = q.logical_head;
  ev.dir_after = q.direction;
  ev.batch_after = q.batch_count;
  ev.epoch = q.epoch;
  trace_add_locked(&ev);
  return 0;
}

#if defined(IOQ_SELFTEST) || defined(IO_HW_SELFTEST)
// TEST-ONLY (D19): chọn policy trước request đầu tiên (cấu hình boot/test,
// không phải switch: không tăng epoch, không ghi event). Đổi khi có tải thì
// dùng io_queue_set_policy_locked() (D22).
void
io_queue_set_policy(enum io_policy policy)
{
  if (q.count != 0 || q.cnt.enqueued != 0)
    panic("io_queue_set_policy: queue used");
  if (!policy_valid(policy))
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
