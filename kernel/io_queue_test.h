// kernel/io_queue_test.h: hook CHỈ dùng cho self-test MOCK của queue (W2-L02, W3-L02).
// Không thuộc contract public; không dùng trong code thật.
#ifndef _IO_QUEUE_TEST_H_
#define _IO_QUEUE_TEST_H_

struct io_request;

// Counters của queue, để test kiểm T07/T11.
struct ioq_counters {
  uint enqueued;   // số request đã vào queue
  uint dispatched; // số request driver đã nhận
  uint eagain;     // số lần dispatch dừng vì driver báo IO_EAGAIN
  uint boundary_events; // W3-L01: số sự kiện biên logic đã commit (D20)
  uint trace_overflow;  // W3-L01: số sự kiện không ghi được vì trace đầy (D18)
};

void io_queue_get_counters_locked(struct ioq_counters *out);
int  io_queue_trace_locked(uint *out, int max); // enqueue_seq theo thứ tự dispatch

#ifdef IOQ_SELFTEST
void io_queue_set_submit_for_test(int (*fn)(struct io_request *));
// W3-L02: đặt head/direction ban đầu cho fixture SCAN (chỉ khi queue chưa dùng).
void io_queue_set_scan_start_for_test(uint head, int dir);
void ioq_selftest(void);
#endif

#endif // _IO_QUEUE_TEST_H_
