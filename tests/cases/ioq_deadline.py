#!/usr/bin/env python3
"""W4-I01 oracle độc lập cho DEADLINE (D21) - Phạm Trung Hiếu.

Oracle này tính expected bằng mô hình ``tests/cases/ioq_w4_model.py`` (viết từ
contract docs/week04/interface.md D21, KHÔNG đọc code C và KHÔNG lấy trace kernel
làm đáp án), rồi so với log QEMU của self-test ``IOQI01``:

- CHK * PASS cho cả 5 nhóm kiểm của kernel (commit/drain/age/overflow/snapshot);
- chuỗi event ``EV`` (DISPATCH/BOUNDARY/SWITCH) đúng thứ tự và đúng trường;
- ``END n`` đúng số event;
- dòng ``SNAP`` khớp counters model: enqueued/dispatched/eagain, dl_expired,
  dl_fifo, policy_switches/epoch, batch, last_block, boundary_events,
  trace_overflow, snapshot kế toán (D23) và latency (mock = 0 sample).

Không thay thế SCAN oracle tuần 3 (``ioq_scan.py``) hay FCFS oracle tuần 2.

Dùng:
    python3 tests/cases/ioq_deadline.py            # in expected từng ca
    python3 tests/cases/ioq_deadline.py LOG        # chấm một serial log
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ioq_w4_model as M  # noqa: E402


def _deadline_cases(exp):
    return {k: v for k, v in exp.items() if M.is_deadline_case(k)}


def check(text):
    """Chấm log; trả danh sách lỗi (rỗng = PASS)."""
    errors = []
    exp = _deadline_cases(M.expected())
    parsed, done_fail, panic = M.parse_log(text)

    if panic:
        errors.append("panic trong log")
    if done_fail is None:
        errors.append("thiếu marker 'IOQI01 DONE fail=' (timeout/không chạy)")
    elif done_fail != 0:
        errors.append(f"kernel báo IOQI01 DONE fail={done_fail}")

    for name, item in exp.items():
        got = parsed.get(name)
        if got is None:
            errors.append(f"{name}: không có output IOQI01")
            continue
        for c in M.CHECKS:
            if got["checks"].get(c) != "PASS":
                errors.append(f"{name}: CHK {c} không PASS")
        if got["events"] != item["events"]:
            errors.append(f"{name}: event sai\n  expected={item['events']}\n  actual  ={got['events']}")
        if got["switches"] != item["switches"]:
            errors.append(f"{name}: bản ghi SW sai (deadline case không được switch)")
        if got["end_n"] != len(item["events"]):
            errors.append(f"{name}: END n={got['end_n']} expected {len(item['events'])}")
        if got["snap"] is None:
            errors.append(f"{name}: thiếu dòng SNAP")
        else:
            errors += M.snapshot_errors(name, got["snap"], item["snap"])

    errors += M.coverage_errors(M.expected())
    return errors


def main(argv):
    if len(argv) == 1:
        for name, item in _deadline_cases(M.expected()).items():
            print(name)
            for event in item["switches"] + item["events"]:
                print("   ", event)
            print("    SNAP", item["snap"])
        errors = M.coverage_errors(M.expected())
        print("coverage:", "OK" if not errors else errors)
        return 0
    if len(argv) != 2:
        print(__doc__)
        return 2
    errs = check(Path(argv[1]).read_text(encoding="utf-8", errors="replace"))
    for err in errs:
        print("FAIL:", err)
    print("PASS" if not errs else f"FAIL ({len(errs)} lỗi)")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
