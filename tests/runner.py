#!/usr/bin/env python3
"""Test runner của dự án ET4290 (xv6-riscv).

Mỗi test case là một entry trong tests/cases/*.py (list CASES). Runner:
  1. build kernel/kernel + fs.img
  2. boot QEMU (CPUS theo case)
  3. gửi lệnh vào shell xv6, so khớp output với các regex mong đợi
  4. in PASS/FAIL từng ca, lưu serial log + meta.json + summary.md

Ví dụ:
    python3 tests/runner.py                 # chạy suite mặc định (trừ tag slow)
    python3 tests/runner.py --list          # liệt kê case
    python3 tests/runner.py --case boot     # chạy case khớp tên
    python3 tests/runner.py --tag baseline  # chạy nhóm baseline
    python3 tests/runner.py --all           # chạy tất cả, gồm stress

Kết quả ghi vào results/local/<timestamp>/ (mặc định) hoặc --results-dir.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import importlib.util
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from qemu import (  # noqa: E402
    BootError,
    BuildError,
    ExpectTimeout,
    PanicDetected,
    QemuSession,
)

CASES_DIR = HERE / "cases"
DEFAULT_TIMEOUT = 120.0
DEFAULT_BOOT_TIMEOUT = 60.0
EXCLUDED_BY_DEFAULT = {"slow", "stress"}

# Shell xv6 in "$ " (không xuống dòng) khi sẵn sàng nhận lệnh. Chờ prompt sau
# mỗi lệnh để không gửi chen vào lúc shell còn in output.
PROMPT = r"\$ $"


# ---------------------------------------------------------------------------
# Nạp test case
# ---------------------------------------------------------------------------
class Case:
    def __init__(self, raw: dict, module: str):
        self.raw = dict(raw)
        self.module = module
        self.name = str(raw["name"])
        self.cpus = int(raw.get("cpus", 3))
        self.tags = list(raw.get("tags", []))
        self.timeout = float(raw.get("timeout", DEFAULT_TIMEOUT))
        self.boot_timeout = float(raw.get("boot_timeout", DEFAULT_BOOT_TIMEOUT))
        self.fresh_fs = bool(raw.get("fresh_fs", True))
        self.survive_s = float(raw.get("survive_s", 0))
        self.note = str(raw.get("note", ""))

        self.steps = []
        for step in raw.get("steps", []):
            self.steps.append(
                {
                    "send": step.get("send"),
                    "expect": _as_list(step.get("expect")),
                    "reject": _as_list(step.get("reject")),
                    "timeout": step.get("timeout"),
                }
            )
        self.expect = _as_list(raw.get("expect"))
        self.reject = _as_list(raw.get("reject"))

    def __repr__(self) -> str:
        return f"<Case {self.name} cpus={self.cpus} tags={self.tags}>"


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def load_cases() -> list[Case]:
    cases: list[Case] = []
    if not CASES_DIR.is_dir():
        return cases
    for path in sorted(CASES_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"et4290_cases_{path.stem}", path)
        if spec is None or spec.loader is None:
            raise SystemExit(f"Không nạp được case module: {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for raw in getattr(mod, "CASES", []):
            cases.append(Case(raw, path.stem))
    names = [c.name for c in cases]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        raise SystemExit(f"Trùng tên test case: {sorted(dup)}")
    return cases


# ---------------------------------------------------------------------------
# Chọn case
# ---------------------------------------------------------------------------
def select_cases(cases: list[Case], args: argparse.Namespace) -> list[Case]:
    selected = []
    for c in cases:
        if args.all:
            pass
        elif args.tag:
            if not (set(args.tag) & set(c.tags)):
                continue
        elif EXCLUDED_BY_DEFAULT & set(c.tags):
            continue
        if args.case and not any(fnmatch.fnmatch(c.name, pat) for pat in args.case):
            continue
        if args.cpus and c.cpus not in args.cpus:
            continue
        selected.append(c)
    return selected


# ---------------------------------------------------------------------------
# Thu thập metadata môi trường
# ---------------------------------------------------------------------------
def _run(args: list[str], timeout: float = 10.0) -> str:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or p.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _mem_total_mb() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 0


def _git_state() -> dict:
    # "dirty" chỉ xét source kernel/user/mkfs + Makefile/mk, không tính log/results.
    return {
        "commit": _run(["git", "rev-parse", "HEAD"]),
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "dirty": bool(
            _run(["git", "status", "--porcelain", "--", "kernel", "user", "mkfs", "Makefile", "mk"])
        ),
    }


def _xv6_pin() -> str:
    path = PROJECT_ROOT / ".xv6-commit"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip().splitlines()[0]
    return ""


def collect_meta(cases: list[Case]) -> dict:
    is_wsl = "microsoft" in platform.release().lower() or "microsoft" in _run(
        ["cat", "/proc/version"]
    ).lower()
    return {
        "schema": 1,
        "tool": "et4290-tests-runner",
        "started_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "git": _git_state(),
        "xv6_pin": _xv6_pin(),
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "kernel": platform.release(),
            "wsl": is_wsl,
            "cpus": os.cpu_count(),
            "mem_total_mb": _mem_total_mb(),
        },
        "toolchain": {
            "riscv_gcc": _run(["riscv64-linux-gnu-gcc", "--version"]).splitlines()[:1],
            "qemu": _run(["qemu-system-riscv64", "--version"]).splitlines()[:1],
            "make": _run(["make", "--version"]).splitlines()[:1],
            "python": sys.version.split()[0],
        },
        "selection": {
            "cases": [c.name for c in cases],
            "cpus": sorted({c.cpus for c in cases}),
        },
    }


# ---------------------------------------------------------------------------
# Chạy một case
# ---------------------------------------------------------------------------
class CaseResult:
    def __init__(self, case: Case, status: str, duration: float, reason: str, log: Path):
        self.case = case
        self.status = status
        self.duration = duration
        self.reason = reason
        self.log = log

    def as_dict(self) -> dict:
        return {
            "name": self.case.name,
            "cpus": self.case.cpus,
            "tags": self.case.tags,
            "status": self.status,
            "duration_s": round(self.duration, 2),
            "reason": self.reason,
            "log": str(self.log.relative_to(self.log.parents[1])),
        }


def run_case(case: Case, results_dir: Path, verbose: bool = False) -> CaseResult:
    started = time.time()
    q = QemuSession(cpus=case.cpus, fresh_fs=case.fresh_fs, verbose=verbose)
    status, reason = "PASS", ""
    try:
        q.start(boot_timeout=case.boot_timeout)
        # Chờ prompt đầu tiên trước khi gửi lệnh.
        q.expect([PROMPT], timeout=case.boot_timeout, since=0)
        step_clock = time.time()
        for i, step in enumerate(case.steps, 1):
            remaining = max(case.timeout - (time.time() - step_clock), 0.5)
            timeout = step["timeout"] or remaining
            timeout = min(float(timeout), remaining)
            since = len(q.raw)
            if step["send"] is not None:
                if verbose:
                    print(f"    [{i}] > {step['send']}")
                q.send(step["send"])
            if step["expect"] or step["reject"]:
                q.expect(
                    step["expect"],
                    timeout=timeout,
                    since=since,
                    reject=step["reject"],
                )
            # Chờ shell sẵn sàng trở lại trước khi gửi lệnh kế tiếp.
            if (
                step["send"] is not None
                and case.survive_s <= 0
                and (step["expect"] or step["reject"])
            ):
                remaining = max(case.timeout - (time.time() - step_clock), 0.5)
                q.expect([PROMPT], timeout=min(30.0, remaining), since=since)
        remaining = max(case.timeout - (time.time() - step_clock), 1.0)
        if case.expect or case.reject:
            q.expect(case.expect, timeout=remaining, since=0, reject=case.reject)
        if case.survive_s > 0:
            q.survive(case.survive_s, reject=case.reject)
    except (BuildError, BootError, ExpectTimeout, PanicDetected) as exc:
        status = "FAIL"
        reason = f"{type(exc).__name__}: {exc}"
    except KeyboardInterrupt:
        status = "FAIL"
        reason = "bị ngắt bởi người dùng (KeyboardInterrupt)"
    finally:
        serial = q.raw
        q.kill()

    duration = time.time() - started
    log = results_dir / "logs" / f"{case.name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# case: {case.name}\n"
        f"# cpus: {case.cpus}\n"
        f"# status: {status}\n"
        f"# duration_s: {duration:.2f}\n"
        f"# reason: {reason or '-'}\n"
        f"# note: {case.note or '-'}\n"
        f"# --- serial console ---\n"
    )
    log.write_text(header + serial, encoding="utf-8")
    return CaseResult(case, status, duration, reason, log)


# ---------------------------------------------------------------------------
# Ghi kết quả
# ---------------------------------------------------------------------------
def write_summary(results_dir: Path, results: list[CaseResult], meta: dict) -> Path:
    passed = sum(1 for r in results if r.status == "PASS")
    failed = len(results) - passed
    lines = [
        "# Kết quả test ET4290",
        "",
        f"- Thời điểm: {meta['started_at']}",
        f"- Project commit: `{meta['git']['commit'][:12]}`"
        f"{' (dirty)' if meta['git']['dirty'] else ''}",
        f"- xv6 pin: `{meta['xv6_pin'][:12]}`",
        f"- Môi trường: {meta['host']['platform']}",
        f"- Số CPU khả dụng: {meta['host']['cpus']}",
        f"- Kết quả: **{passed} PASS / {failed} FAIL**",
        "",
        "| Case | CPUS | Trạng thái | Thời gian (s) | Ghi chú |",
        "| --- | ---: | --- | ---: | --- |",
    ]
    for r in results:
        note = r.reason.splitlines()[0][:160] if r.reason else (r.case.note or "")
        note = note.replace("|", "\\|")
        lines.append(
            f"| `{r.case.name}` | {r.case.cpus} | {r.status} | {r.duration:.2f} | {note} |"
        )
    lines.append("")
    text = "\n".join(lines)
    path = results_dir / "summary.md"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test runner ET4290 cho xv6-riscv",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--list", action="store_true", help="liệt kê test case rồi thoát")
    parser.add_argument("--case", action="append", metavar="GLOB", help="chỉ chạy case khớp tên")
    parser.add_argument("--tag", action="append", metavar="TAG", help="chỉ chạy case có tag")
    parser.add_argument("--all", action="store_true", help="chạy tất cả, kể cả tag slow")
    parser.add_argument("--cpus", action="append", type=int, help="chỉ chạy case có CPUS này")
    parser.add_argument("--results-dir", metavar="DIR", help="thư mục ghi kết quả")
    parser.add_argument("--verbose", action="store_true", help="in lệnh gửi vào shell")
    args = parser.parse_args(argv)

    cases = load_cases()
    selected = select_cases(cases, args)

    if args.list:
        print(f"{'CASE':38s} {'CPUS':>4s} {'TAGS':22s} {'TIMEOUT':>8s}  NOTE")
        for c in cases:
            mark = "*" if c in selected else " "
            print(
                f"{mark}{c.name:37s} {c.cpus:4d} {','.join(c.tags):22s} "
                f"{c.timeout:8.0f}  {c.note}"
            )
        print(f"\nTổng: {len(cases)} case (dấu * = được chọn với tham số hiện tại)")
        return 0

    if not selected:
        print("Không có test case nào được chọn. Xem `python3 tests/runner.py --list`.")
        return 2

    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if args.results_dir:
        results_dir = Path(args.results_dir).resolve()
    else:
        results_dir = PROJECT_ROOT / "results" / "local" / f"tests-{stamp}"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "logs").mkdir(exist_ok=True)

    meta = collect_meta(selected)
    print(f"== ET4290 test runner — {len(selected)} case ==")
    print(f"   kết quả: {results_dir}")
    results: list[CaseResult] = []
    failed_early = False
    for c in selected:
        print(f"--- [{len(results) + 1}/{len(selected)}] {c.name} (CPUS={c.cpus}) ... ", end="", flush=True)
        try:
            r = run_case(c, results_dir, verbose=args.verbose)
        except BuildError as exc:  # build lỗi: các case sau cũng sẽ lỗi
            print(f"FAIL (build): {exc}")
            failed_early = True
            break
        results.append(r)
        print(f"{r.status} ({r.duration:.1f}s)")

    if failed_early and not results:
        return 1

    meta["finished_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    meta["duration_s"] = round(
        sum(r.duration for r in results), 2
    )
    meta["results"] = [r.as_dict() for r in results]
    (results_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = write_summary(results_dir, results, meta)

    passed = sum(1 for r in results if r.status == "PASS")
    failed = len(results) - passed
    print()
    print(f"== Kết quả: {passed} PASS / {failed} FAIL ==")
    for r in results:
        if r.status != "PASS":
            print(f"   FAIL {r.case.name}: {r.reason.splitlines()[0] if r.reason else ''}")
    print(f"   meta:     {results_dir / 'meta.json'}")
    print(f"   summary:  {summary}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
