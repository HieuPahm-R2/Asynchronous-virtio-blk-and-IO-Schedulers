"""Oracle độc lập cho SCAN logic (W3-L02, Lợi) theo docs/week03/interface.md D11-D18.

Kernel build với -DIOQ_SELFTEST chạy các ca trong kernel/io_queue_test.c và IN
trace sự kiện đã commit (DISPATCH/BOUNDARY). File này tự tính expected từ fixture
(initial head/direction, danh sách block, thứ tự đến) theo quy tắc của contract,
KHÔNG đọc code C, KHÔNG lấy trace kernel làm đáp án, KHÔNG dùng thứ tự completion.

Mọi ca là trace tĩnh: queue được nạp đủ khi driver giả đóng, rồi mới dispatch.
Driver giả là MOCK (không đụng đĩa): không dùng kết quả để nói về seek vật lý.

Dùng:
    python3 tests/cases/ioq_scan.py LOG     # so một serial log, in PASS/FAIL
    from ioq_scan import check; errors = check(text)
"""
from __future__ import annotations

import re
import sys

FSSIZE = 2000          # miền block MVP 0..FSSIZE-1 (D12)
UP, DOWN = 1, -1
FCFS, SCAN = "fcfs", "scan"

# Fixture: phải giống hệt scan_cases[] trong kernel/io_queue_test.c.
# (tên, policy, head, dir, cap, blocks) -- cap chỉ ảnh hưởng EAGAIN, không ảnh
# hưởng thứ tự (D16), nên oracle không cần nó.
SCAN_CASES = [
    ("fcfs",      FCFS, 40, UP,   2, [70, 20, 90, 10, 50]),   # nhóm 1: FCFS cũ
    ("scan-up",   SCAN, 40, UP,   2, [70, 20, 90, 10, 50]),   # nhóm 2: ví dụ chuẩn §6.2
    ("scan-down", SCAN, 40, DOWN, 2, [70, 20, 90, 10, 50]),   # nhóm 3
    ("opposite",  SCAN, 40, UP,   2, [10, 20]),               # nhóm 4: chỉ ngược chiều (R2)
    ("empty",     SCAN, 40, UP,   2, []),                     # nhóm 5a: queue rỗng (R1)
    ("single",    SCAN, 0,  UP,   2, [5]),                    # nhóm 5b: một request
    ("tie-head",  SCAN, 40, UP,   2, [60, 40, 60, 40]),       # nhóm 6: cùng block + tại head (R3/R5)
    ("eagain",    SCAN, 40, UP,   1, [50, 70, 20]),           # nhóm 7: EAGAIN giữa vòng (R4/R7)
    ("edge-up",   SCAN, 40, UP,   2, [70, 20, FSSIZE - 1]),   # nhóm 8a: tới biên trên rồi đảo
    ("edge-down", SCAN, 40, DOWN, 2, [0, 30, 50]),            # nhóm 8b: tới biên dưới rồi đảo
]

CHECKS = ["closed-no-commit", "eagain-no-commit", "drain-each-once", "state-matches-trace"]


def oracle(policy, head, direction, blocks):
    """Trả về danh sách sự kiện đã commit, dạng chuỗi giống kernel in ra."""
    pending = [(seq, b) for seq, b in enumerate(blocks, start=1)]
    events = []
    while pending:
        if policy == FCFS:
            seq, b = min(pending)                        # seq nhỏ nhất
            events.append(f"D seq={seq} blk={b} hb={head} ha={head} db={direction} da={direction}")
            pending.remove((seq, b))
            continue
        at_head = [p for p in pending if p[1] == head]   # D14 bước 1
        if at_head:
            pick = min(at_head)
        else:
            pick = _nearest(pending, head, direction)    # D14 bước 2
            if pick is None:                             # D15: biên logic rồi đảo chiều
                bnd = FSSIZE - 1 if direction == UP else 0
                events.append(f"B bnd={bnd} hb={head} ha={head} db={direction} da={-direction}")
                direction = -direction
                pick = _nearest(pending, head, direction)
                assert pick is not None
        seq, b = pick
        events.append(f"D seq={seq} blk={b} hb={head} ha={b} db={direction} da={direction}")
        head = b
        pending.remove(pick)
    return events


def _nearest(pending, head, direction):
    if direction == UP:
        cands = [p for p in pending if p[1] > head]
        return min(cands, key=lambda p: (p[1], p[0])) if cands else None
    cands = [p for p in pending if p[1] < head]
    return min(cands, key=lambda p: (-p[1], p[0])) if cands else None


# Ca unlink (D17): FCFS, block 7,2,9,1,4 (seq 1..5); gỡ seq 3 (giữa), seq 1 (đầu),
# seq 5 (cuối); thêm block 3 (seq 6). Còn lại theo FCFS: seq 2, 4, 6.
UNLINK_EXPECTED = [
    "D seq=2 blk=2 hb=0 ha=0 db=1 da=1",
    "D seq=4 blk=1 hb=0 ha=0 db=1 da=1",
    "D seq=6 blk=3 hb=0 ha=0 db=1 da=1",
]


def expected():
    exp = {name: oracle(pol, head, d, blocks) for name, pol, head, d, _cap, blocks in SCAN_CASES}
    exp["unlink"] = UNLINK_EXPECTED
    return exp


def check(text):
    """So serial log với oracle. Trả về danh sách lỗi (rỗng = PASS)."""
    errors = []
    text = text.replace("\r", "")
    if re.search(r"(^|\n)panic:", text):
        errors.append("panic")
    m = re.search(r"^IOQSCAN DONE fail=(\d+)\s*$", text, re.M)
    if not m:
        errors.append("thiếu marker IOQSCAN DONE (timeout/không chạy)")
    elif m.group(1) != "0":
        errors.append(f"kernel báo {m.group(1)} check FAIL")
    for name, events in expected().items():
        checks = CHECKS if name != "unlink" else ["head-mid-tail"]
        for c in checks:
            if not re.search(rf"^IOQSCAN {re.escape(name)} CHK {c} PASS\s*$", text, re.M):
                errors.append(f"{name}: thiếu CHK {c} PASS")
        got = re.findall(rf"^IOQSCAN {re.escape(name)} EV (.*?)\s*$", text, re.M)
        if got != events:
            errors.append(f"{name}: trace sai\n  expected={events}\n  actual  ={got}")
        if not re.search(rf"^IOQSCAN {re.escape(name)} END n={len(events)}\s*$", text, re.M):
            errors.append(f"{name}: END n khác {len(events)}")
    return errors


# Đăng ký cho tests/runner.py (tag selftest => không chạy mặc định; kernel phải
# build với EXTRA_CFLAGS=-DIOQ_SELFTEST, xem scripts/check-week03-scan.py).
CASES = [
    {
        "name": "ioq-scan-mock",
        "cpus": 1,
        "tags": ["selftest", "scheduler", "mock", "scan"],
        "timeout": 90,
        "expect": [
            rf"^IOQSCAN {re.escape(n)} EV {re.escape(ev)}\s*$"
            for n, evs in expected().items() for ev in evs
        ] + [r"^IOQSCAN DONE fail=0\s*$"],
        "reject": [r"IOQSCAN .* FAIL", r"^panic:"],
        "steps": [
            {"send": "echo BOOT_OK", "expect": [r"^BOOT_OK$"], "timeout": 20},
        ],
        "note": "MOCK: SCAN logic theo contract W3-G01; oracle Python độc lập, kiểm cả boundary",
    },
]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        for name, evs in expected().items():
            print(name)
            for e in evs:
                print("   ", e)
        sys.exit(0)
    errs = check(open(sys.argv[1], encoding="utf-8", errors="replace").read())
    for e in errs:
        print("FAIL:", e)
    print("PASS" if not errs else f"FAIL ({len(errs)} lỗi)")
    sys.exit(1 if errs else 0)
