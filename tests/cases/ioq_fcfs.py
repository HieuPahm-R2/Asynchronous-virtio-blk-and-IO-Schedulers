"""Self-test MOCK cho queue FCFS (W2-L02, Lợi): T07 backpressure, T11 drain, T13 oracle.

Kernel phải build với -DIOQ_SELFTEST (xem docs/week02/loi.md). Driver giả 2 slot,
không đụng đĩa: KHÔNG dùng kết quả này để nói về max_inflight thiết bị thật.

Oracle tính ở đây, độc lập với code kernel: FCFS = thứ tự enqueue,
KHÔNG theo số block, KHÔNG theo thứ tự completion.
"""

BLOCKS = [7, 2, 9, 1, 4]                         # fixture giống kernel/io_queue_test.c
EXPECTED_SEQ = list(range(1, len(BLOCKS) + 1))   # seq 1..5 theo thứ tự enqueue
EXPECTED_BLK = [BLOCKS[s - 1] for s in EXPECTED_SEQ]


def _csv(xs):
    return ",".join(str(x) for x in xs)


CHECKS = [
    ("T07", "two-inflight"),
    ("T07", "three-queued"),
    ("T07", "eagain-seen"),
    ("T07", "eagain-keeps-queued"),
    ("T07", "progress-after-complete"),
    ("T11", "drain-queue-empty"),
    ("T11", "drain-no-inflight"),
    ("T11", "counters"),
    ("T07", "each-dispatched-once"),
]

CASES = [
    {
        "name": "ioq-fcfs-mock",
        "cpus": 1,
        "tags": ["selftest", "scheduler", "mock"],
        "timeout": 90,
        "expect": [rf"^IOQTEST MOCK {t} {n} PASS" for t, n in CHECKS]
        + [
            rf"^IOQTEST MOCK T13 seq={_csv(EXPECTED_SEQ)}\s*$",
            rf"^IOQTEST MOCK T13 blk={_csv(EXPECTED_BLK)}\s*$",
            r"^IOQTEST MOCK DONE fail=0\s*$",
        ],
        "reject": [r"IOQTEST .* FAIL", r"^panic:"],
        "steps": [
            {"send": "echo BOOT_OK", "expect": [r"^BOOT_OK$"], "timeout": 20},
        ],
        "note": "MOCK 2 slot: FCFS theo enqueue_seq, EAGAIN giữ queue, tự dispatch sau complete",
    },
]
