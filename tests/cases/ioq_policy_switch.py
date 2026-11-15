#!/usr/bin/env python3
"""W4-I01 oracle độc lập cho runtime SWITCH (D22) và snapshot (D23) - Hiếu.

Cùng mô hình contract ``tests/cases/ioq_w4_model.py`` (không đọc code C, không
lấy trace kernel làm đáp án). Kiểm trên log self-test ``IOQI01``:

1. Bản ghi ``SW pol= rc= q= i= ep=``: enum sai -> -22 và không đổi; cùng policy
   -> no-op rc 0; khác -> rc 0, epoch +1. Kiểm cả 6 chiều chuyển giữa 3 policy và
   yêu cầu ít nhất một lần switch có Q>0 và I>0.
2. Chuỗi ``EV`` đúng thứ tự: switch không làm mất/trùng request, không đổi
   enqueue_seq/tuổi; vào SCAN lấy last_block (mọi policy) làm head, dir UP; vào
   DEADLINE reset batch.
3. Dòng ``SNAP``: counters switch/epoch, snapshot kế toán D23 và latency (mock 0).
4. Marker ``IOQI01 DONE fail=0``; không panic; không timeout.

Dùng:
    python3 tests/cases/ioq_policy_switch.py           # in expected từng ca
    python3 tests/cases/ioq_policy_switch.py LOG       # chấm một serial log
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ioq_w4_model as M  # noqa: E402


def _switch_cases(exp):
    return {k: v for k, v in exp.items() if M.is_switch_case(k)}


def _transition_pairs(parsed):
    pairs = set()
    for got in parsed.values():
        for event in got["events"]:
            if event.startswith("S "):
                old = int(event.split("old=")[1].split()[0])
                new = int(event.split("new=")[1].split()[0])
                pairs.add((old, new))
    return pairs


def check(text):
    errors = []
    exp = _switch_cases(M.expected())
    parsed, done_fail, panic = M.parse_log(text)

    if panic:
        errors.append("panic trong log")
    if done_fail is None:
        errors.append("thiếu marker 'IOQI01 DONE fail=' (timeout/không chạy)")
    elif done_fail != 0:
        errors.append(f"kernel báo IOQI01 DONE fail={done_fail}")

    loaded_switches = 0
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
            errors.append(f"{name}: bản ghi SW sai\n  expected={item['switches']}\n  actual  ={got['switches']}")
        for record in got["switches"]:
            q = int(record.split("q=")[1].split()[0])
            i = int(record.split("i=")[1].split()[0])
            rc = int(record.split("rc=")[1].split()[0])
            if q > 0 and i > 0 and rc == 0:
                loaded_switches += 1
        if got["end_n"] != len(item["events"]):
            errors.append(f"{name}: END n={got['end_n']} expected {len(item['events'])}")
        if got["snap"] is None:
            errors.append(f"{name}: thiếu dòng SNAP")
        else:
            errors += M.snapshot_errors(name, got["snap"], item["snap"])

    need = {(a, b) for a in M.POLICIES for b in M.POLICIES if a != b}
    missing = sorted(need - _transition_pairs(parsed))
    if missing:
        errors.append(f"thiếu chiều switch: {missing}")
    if loaded_switches < 1:
        errors.append("không có lần switch nào quan sát Q>0 và I>0")
    # Không được tăng epoch cho no-op/invalid: model đã so bản ghi SW từng ca.
    errors += M.coverage_errors(M.expected())
    return errors


def main(argv):
    if len(argv) == 1:
        for name, item in _switch_cases(M.expected()).items():
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
