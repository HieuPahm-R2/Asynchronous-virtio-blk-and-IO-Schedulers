#!/usr/bin/env python3
"""W4-L01/L02 (Lợi): kiểm DEADLINE + đổi policy khi có tải (MOCK) + mutant.

Các bước (mỗi lần đổi cờ build đều make clean):
  1. build EXTRA_CFLAGS=-DIOQ_SELFTEST, boot CPUS=1 và CPUS=4; trên cùng log:
     oracle tests/cases/ioq_policy.py (deadline/switch, tuần 4) phải PASS,
     oracle SCAN tuần 3 (ioq_scan.py) và FCFS tuần 2 (ioq_fcfs.py) vẫn PASS.
  2. mutant tests/mutants/dl-*.patch, sw-*.patch (chấm bằng oracle tuần 4) và
     scan-*.patch (chấm bằng oracle SCAN): git apply tạm, build, boot CPUS=1,
     oracle phải FAIL (EXPECTED_FAIL); luôn git apply -R trong finally.
  3. build production, kiểm hook test KHÔNG có trong kernel/kernel.

Kết quả: results/week04/policy-mock/<host>-<timestamp>/ (log, meta.json, summary.md).
Đây là test MOCK (driver giả 2 slot, đồng hồ giả): không chứng minh READ thật,
seek vật lý hay latency. SCAN/deadline READ thật là H01/H02 của Hoàng.

    python3 scripts/check-week04-policy.py            # đủ bước
    python3 scripts/check-week04-policy.py --no-mutants
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
TEST_HOOKS = r"\b(?:ioq_selftest|io_queue_set_policy|io_queue_set_scan_start_for_test|io_queue_set_submit_for_test|io_queue_set_clock_for_test)\b"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Dùng lại build/boot của harness tuần 2 (boot QEMU trực tiếp, không tự rebuild).
H = load("week02_harness", ROOT / "scripts/check-week02-hoang.py")
SCAN = load("ioq_scan", ROOT / "tests/cases/ioq_scan.py")
POL = load("ioq_policy", ROOT / "tests/cases/ioq_policy.py")
FCFS = load("ioq_fcfs", ROOT / "tests/cases/ioq_fcfs.py")


def out(cmd):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True).stdout.strip()


def tool(name):
    # Cùng thứ tự dò như Makefile: unknown-elf trước, rồi linux-gnu.
    for prefix in ("riscv64-unknown-elf-", "riscv64-linux-gnu-", "riscv64-elf-"):
        if shutil.which(prefix + name):
            return prefix + name
    raise SystemExit(f"không tìm thấy công cụ RISC-V '{name}' (unknown-elf/linux-gnu)")


# Tương thích cả harness cũ (build(outdir, mode, flag)) và harness sau W3-H01
# của Hoàng (build(outdir, mode, tc, flag) + resolve_toolchain()).
TC = H.resolve_toolchain(None) if hasattr(H, "resolve_toolchain") else None


def build(outdir, mode, flag=None):
    if TC is not None:
        return H.build(outdir, mode, TC, flag)
    return H.build(outdir, mode, flag)


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

    gcc, nm = (TC["cc"], TC["nm"]) if TC else (tool("gcc"), tool("nm"))
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    outdir = (args.results_dir or ROOT / "results/week04/policy-mock" / f"{socket.gethostname()}-{stamp}").resolve()
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
        build(outdir, "queue", "EXTRA_CFLAGS=-DIOQ_SELFTEST")
        for cpus in (1, 4):
            text, booted = boot_text(outdir / f"policy-cpus{cpus}.log", cpus)
            e = POL.check(text) + [f"SCAN tuần 3: {x}" for x in SCAN.check(text)] + \
                [f"FCFS tuần 2: thiếu {p}" for p in fcfs_errors(text)]
            if not booted:
                e.append("boot/panic/timeout")
            status = "FAIL" if e else "PASS"
            meta["runs"].append({"mode": "policy-mock", "cpus": cpus, "status": status, "errors": e,
                                 "log": f"policy-cpus{cpus}.log"})
            print(f"policy mock cpus={cpus} (deadline+switch+SCAN+FCFS): {status}", flush=True)
            errors += [f"cpus={cpus}: {x}" for x in e]

        if not args.no_mutants:
            patches = sorted((ROOT / "tests/mutants").glob("dl-*.patch")) + \
                sorted((ROOT / "tests/mutants").glob("sw-*.patch")) + \
                sorted((ROOT / "tests/mutants").glob("scan-*.patch"))
            for patch in patches:
                name = patch.stem
                oracle = SCAN if name.startswith("scan-") else POL
                subprocess.run(["git", "apply", str(patch)], cwd=ROOT, check=True)
                try:
                    build(outdir, name, "EXTRA_CFLAGS=-DIOQ_SELFTEST")
                    text, booted = boot_text(outdir / f"{name}-cpus1.log", 1)
                finally:
                    subprocess.run(["git", "apply", "-R", str(patch)], cwd=ROOT, check=True)
                e = oracle.check(text)
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
            build(outdir, "production")
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
        lines = [f"# W4-L01/L02 deadline + runtime switch (MOCK)\n", f"- Status: {meta['status']}",
                 f"- HEAD: `{meta['head']}` (dirty: {'có' if meta['dirty'] else 'không'})",
                 f"- Toolchain: {meta['versions']}\n"]
        lines += [f"- policy-mock CPUS={r['cpus']}: {r['status']} ({r['log']})" for r in meta["runs"]]
        lines += [f"- mutant {m['name']}: {'EXPECTED_FAIL' if m['caught'] else 'NOT CAUGHT'} ({m['log']})"
                  for m in meta["mutants"]]
        lines.append(f"- production hooks absent: {meta.get('production_hooks_absent')}")
        lines.append(f"- Deadline D21: READ expire={POL.EXPIRE} tick, batch={POL.BATCH} (đề xuất, chờ G01)")
        lines.append("\nMOCK driver + đồng hồ giả: không phải bằng chứng READ thật/seek/latency.")
        if errors:
            lines.append("\n## Lỗi\n" + "\n".join(f"- {e}" for e in errors))
        (outdir / "summary.md").write_text("\n".join(lines) + "\n")
        print(f"{meta['status']}: {outdir}", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
