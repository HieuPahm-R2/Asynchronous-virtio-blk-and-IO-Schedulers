// kernel/io_queue.c: pending queue + dispatcher FCFS (W2-L01, Lợi).
// Contract: kernel/io_request.h và docs/week02/interface.md (D5, D6, D8).
//
// Queue chỉ quyết định THỨ TỰ và gọi driver. Không cấp/thu hồi slot (việc của
// io_request.c) và không đụng descriptor (việc của virtio_disk.c).
// Mọi hàm *_locked: người gọi đang giữ io_lock (= virtio_disk_io_lock()),
// không acquire lại, không ngủ, không cấp phát, không printk (có thể chạy trong IRQ).

#include "types.h"
#include "param.h"
#include "riscv.h"
#include "defs.h"
#include "io_request.h"
#include "io_queue_test.h"

#define IOQ_TRACE_N 64

static struct {
  int head;                          // id của request QUEUED đầu hàng, IO_NIL nếu rỗng
  int tail;                          // id của request QUEUED cuối hàng
  int count;                         // số request QUEUED
  uint next_seq;                     // enqueue_seq kế tiếp, bắt đầu từ 1
  struct io_request *by_id[IO_NREQ]; // id -> request, để đi theo liên kết req->next
  struct ioq_counters cnt;
  uint trace[IOQ_TRACE_N];           // enqueue_seq theo thứ tự dispatch (cho test)
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
}

// Thêm req vào CUỐI hàng. Vì enqueue_seq tăng dần và luôn thêm ở cuối,
// đầu hàng luôn là request có enqueue_seq nhỏ nhất (đúng FCFS).
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

// Policy FCFS: request đầu hàng. Tách riêng để tuần sau thêm SCAN/deadline
// mà không sửa vòng dispatch.
static struct io_request *
fcfs_pick_locked(void)
{
  return q.head == IO_NIL ? 0 : q.by_id[q.head];
}

// Bỏ request đầu hàng ra khỏi queue (chỉ gọi sau khi driver đã nhận nó).
static void
pop_head_locked(void)
{
  struct io_request *r = q.by_id[q.head];

  q.head = r->next;
  if (q.head == IO_NIL)
    q.tail = IO_NIL;
  r->next = IO_NIL;
  q.by_id[r->id] = 0;
  q.count--;
}

// Gửi xuống driver càng nhiều càng tốt, theo thứ tự enqueue_seq.
// Gặp IO_EAGAIN đầu tiên thì dừng: request ở nguyên đầu hàng, giữ enqueue_seq,
// vẫn QUEUED. Lần completion sau sẽ gọi lại hàm này; không spin chờ ở đây.
void
io_dispatch_locked(void)
{
  struct io_request *r;

  while ((r = fcfs_pick_locked()) != 0) {
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

    pop_head_locked();
    q.cnt.dispatched++;
    if (q.ntrace < IOQ_TRACE_N)
      q.trace[q.ntrace++] = r->enqueue_seq;
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

int
io_queue_trace_locked(uint *out, int max)
{
  int n = q.ntrace < max ? q.ntrace : max;

  for (int i = 0; i < n; i++)
    out[i] = q.trace[i];
  return n;
}
