#!/usr/bin/env python3
"""W3-L02 (Lợi): kiểm SCAN logic MOCK bằng oracle Python độc lập + mutant.

Các bước (mỗi lần đổi cờ build đều make clean):
  1. build EXTRA_CFLAGS=-DIOQ_SELFTEST, boot CPUS=1 và CPUS=4;
     oracle tests/cases/ioq_scan.py phải PASS, oracle FCFS tuần 2 (ioq_fcfs.py)
     phải vẫn PASS trên cùng log (giữ chuẩn FCFS).
  2. với từng mutant trong tests/mutants/scan-*.patch: git apply tạm, build, boot
     CPUS=1, oracle phải FAIL (EXPECTED_FAIL); luôn git apply -R sau đó.
  3. build production, kiểm hook test (ioq_selftest, io_queue_set_policy, ...)
     KHÔNG có trong kernel/kernel.

Kết quả: results/week03/scan-oracle/<host>-<timestamp>/ (log, meta.json, summary.md).
Đây là test MOCK: không chứng minh gì về READ thật hay seek vật lý (G02 lo phần đó).

    python3 scripts/check-week03-scan.py            # đủ bước
    python3 scripts/check-week03-scan.py --no-mutants
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import platform
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_HOOKS = r"\b(?:ioq_selftest|io_queue_set_policy|io_queue_set_scan_start_for_test|io_queue_set_submit_for_test)\b"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Dùng lại build/boot của harness tuần 2 (boot QEMU trực tiếp, không tự rebuild).
H = load("week02_harness", ROOT / "scripts/check-week02-hoang.py")
SCAN = load("ioq_scan", ROOT / "tests/cases/ioq_scan.py")
FCFS = load("ioq_fcfs", ROOT / "tests/cases/ioq_fcfs.py")


def out(cmd):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True).stdout.strip()


def tool(name):
    # Cùng thứ tự dò như Makefile: unknown-elf trước, rồi linux-gnu.
    for prefix in ("riscv64-unknown-elf-", "riscv64-linux-gnu-", "riscv64-elf-"):
        if shutil.which(prefix + name):
            return prefix + name
    raise SystemExit(f"không tìm thấy công cụ RISC-V '{name}' (unknown-elf/linux-gnu)")


def boot_text(logpath, cpus):
    """Boot và trả về log; boot lỗi/panic vẫn trả log để oracle chấm."""
    try:
        text, _ = H.boot(logpath, cpus)
        return text, True
    except RuntimeError:
        return logpath.read_text() if logpath.exists() else "", False


def fcfs_errors(text):
    return [p for p in FCFS.CASES[0]["expect"] if not re.search(p, text, re.M)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-mutants", action="store_true", help="bỏ qua bước mutant")
    ap.add_argument("--results-dir", type=Path)
    args = ap.parse_args()

    gcc, nm = tool("gcc"), tool("nm")
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    outdir = (args.results_dir or ROOT / "results/week03/scan-oracle" / f"{socket.gethostname()}-{stamp}").resolve()
    outdir.mkdir(parents=True, exist_ok=False)
    meta = {
        "started_at": dt.datetime.now().astimezone().isoformat(),
        "host": platform.platform(), "head": out(["git", "rev-parse", "HEAD"]),
        "branch": out(["git", "branch", "--show-current"]),
        "dirty": out(["git", "status", "--porcelain"]),
        "versions": {x: out([x, "--version"]).splitlines()[0] for x in (gcc, "qemu-system-riscv64")},
        "runs": [], "mutants": [],
    }
    (outdir / "source.patch").write_text(out(["git", "diff", "--binary", "HEAD"]) + "\n")
    errors = []
    try:
        H.build(outdir, "queue", "EXTRA_CFLAGS=-DIOQ_SELFTEST")
        for cpus in (1, 4):
            text, booted = boot_text(outdir / f"scan-cpus{cpus}.log", cpus)
            e = SCAN.check(text) + [f"FCFS tuần 2: thiếu {p}" for p in fcfs_errors(text)]
            if not booted:
                e.append("boot/panic/timeout")
            status = "FAIL" if e else "PASS"
            meta["runs"].append({"mode": "scan-mock", "cpus": cpus, "status": status, "errors": e,
                                 "log": f"scan-cpus{cpus}.log"})
            print(f"scan mock cpus={cpus}: {status}", flush=True)
            errors += [f"cpus={cpus}: {x}" for x in e]

        if not args.no_mutants:
            for patch in sorted((ROOT / "tests/mutants").glob("scan-*.patch")):
                name = patch.stem
                subprocess.run(["git", "apply", str(patch)], cwd=ROOT, check=True)
                try:
                    H.build(outdir, name, "EXTRA_CFLAGS=-DIOQ_SELFTEST")
                    text, booted = boot_text(outdir / f"{name}-cpus1.log", 1)
                finally:
                    subprocess.run(["git", "apply", "-R", str(patch)], cwd=ROOT, check=True)
                e = SCAN.check(text)
                caught = bool(e)
                meta["mutants"].append({"name": name, "caught": caught, "first_errors": e[:3],
                                        "log": f"{name}-cpus1.log"})
                print(f"mutant {name}: {'EXPECTED_FAIL' if caught else 'NOT CAUGHT'}", flush=True)
                if not caught:
                    errors.append(f"mutant {name} không bị oracle bắt")
    except Exception as exc:  # build lỗi, git apply lỗi...
        errors.append(f"lỗi harness: {exc}")
    finally:
        try:
            H.build(outdir, "production")
            leaked = sorted(set(re.findall(TEST_HOOKS, out([nm, "kernel/kernel"]))))
            meta["production_hooks_absent"] = not leaked
            if leaked:
                errors.append(f"hook test lọt vào production: {leaked}")
        except Exception as exc:
            errors.append(f"build production lỗi: {exc}")
        meta["finished_at"] = dt.datetime.now().astimezone().isoformat()
        meta["status"] = "FAIL" if errors else "PASS"
        meta["errors"] = errors
        (outdir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
        lines = [f"# W3-L02 SCAN oracle (MOCK)\n", f"- Status: {meta['status']}",
                 f"- HEAD: `{meta['head']}` (dirty: {'có' if meta['dirty'] else 'không'})",
                 f"- Toolchain: {meta['versions']}\n"]
        lines += [f"- scan-mock CPUS={r['cpus']}: {r['status']} ({r['log']})" for r in meta["runs"]]
        lines += [f"- mutant {m['name']}: {'EXPECTED_FAIL' if m['caught'] else 'NOT CAUGHT'} ({m['log']})"
                  for m in meta["mutants"]]
        lines.append(f"- production hooks absent: {meta.get('production_hooks_absent')}")
        lines.append("\nMOCK driver: không phải bằng chứng READ thật/seek vật lý.")
        if errors:
            lines.append("\n## Lỗi\n" + "\n".join(f"- {e}" for e in errors))
        (outdir / "summary.md").write_text("\n".join(lines) + "\n")
        print(f"{meta['status']}: {outdir}", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
