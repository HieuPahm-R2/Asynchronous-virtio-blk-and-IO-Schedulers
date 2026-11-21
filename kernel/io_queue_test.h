// kernel/io_queue_test.h: hook CHỈ dùng cho self-test MOCK của queue
// (W2-L02, W3-L02, W4-L01/L02, W4-I01).
// Không thuộc contract public; không dùng trong code thật.
//
// W4-I01: `struct ioq_counters` + io_queue_get_counters_locked()/
// io_queue_trace_locked() đã chuyển sang kernel/io_request.h vì snapshot hợp
// nhất (io_snapshot_locked) dùng chúng trong cả build production. File này chỉ
// còn các hook test-only.
#ifndef _IO_QUEUE_TEST_H_
#define _IO_QUEUE_TEST_H_

struct io_request;

#ifdef IOQ_SELFTEST
void io_queue_set_submit_for_test(int (*fn)(struct io_request *));
// W3-L02: đặt head/direction ban đầu cho fixture SCAN (chỉ khi queue chưa dùng).
void io_queue_set_scan_start_for_test(uint head, int dir);
// W4-L01: đồng hồ giả cho fixture deadline (0 = dùng ticks thật).
void io_queue_set_clock_for_test(uint (*fn)(void));
void ioq_selftest(void);
#endif

#endif // _IO_QUEUE_TEST_H_
