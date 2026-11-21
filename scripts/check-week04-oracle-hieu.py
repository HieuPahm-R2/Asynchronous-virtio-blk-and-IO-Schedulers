#!/usr/bin/env python3
"""W4-I01 harness - oracle độc lập deadline/switch + snapshot + mutant (Hiếu).

Chạy trên checkout W4 (Lợi L01/L02 + I01 Hiếu). Các bước:

  1. Build `-DIOQ_SELFTEST`, boot CPUS=1 và CPUS=4. Trên cùng log:
     - oracle độc lập I01 `tests/cases/ioq_deadline.py` (D21) và
       `tests/cases/ioq_policy_switch.py` (D22/D23) phải PASS;
     - regression: oracle SCAN tuần 3 và FCFS tuần 2 vẫn PASS.
  2. Mutant (negative control): bỏ ưu tiên expired (`dl-m1`), commit batch khi
     EAGAIN (`dl-m3`), reset tuổi khi switch (`sw-m2`) - do L01/L02 tạo - và 3
     mutant I01 (`i01-m1` sai thứ tự expiry, `i01-m2` no-op tăng epoch,
     `i01-m3` không reset batch). Oracle độc lập phải FAIL cho từng mutant;
     `git apply -R` trong finally, không để mutant lọt vào revision.
  3. READ thật cơ bản (IO_HW_SELFTEST, CPUS=1): chạy suite sẵn có để lấy dòng
     `IO-SNAP` với latency samples > 0 (đo trên tick 100 ms; chỉ là mẫu cơ bản,
     không thay H01/H02).
  4. Build production, xác minh hook test vắng trong `kernel/kernel`.
  5. `python3 scripts/check_text.py`, `git diff --check`.

Kết quả: `results/week04/oracle-hieu/<host>-<timestamp>/`
(log, meta.json, summary.md, source.patch, untracked-source/).
Đây là test MOCK cho deadline/switch + một mẫu READ thật cho timing; không
chứng minh SCAN real/deadline real 10 boot (H01/G02) hay máy thứ hai (H02).

    python3 scripts/check-week04-oracle-hieu.py
    python3 scripts/check-week04-oracle-hieu.py --no-mutants --results-dir DIR
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
TEST_HOOKS = (
    r"\b(?:ioq_selftest|io_queue_set_policy|io_queue_set_scan_start_for_test|"
    r"io_queue_set_submit_for_test|io_queue_set_clock_for_test|io_hw_selftest|"
    r"virtio_test_\w+|io_test_\w+)\b"
)
MUTANT_ORACLE = {
    "scan-": "SCAN",
    "sw-": "SWITCH",
    "dl-": "DEADLINE",
    "i01-m1": "DEADLINE",
    "i01-m2": "SWITCH",
    "i01-m3": "SWITCH",
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Dùng lại build/boot của harness tuần 2 (không tự rebuild công thức khác).
H = load("week02_harness", ROOT / "scripts/check-week02-hoang.py")
DEAD = load("ioq_deadline", ROOT / "tests/cases/ioq_deadline.py")
SW = load("ioq_policy_switch", ROOT / "tests/cases/ioq_policy_switch.py")
POL = load("ioq_policy", ROOT / "tests/cases/ioq_policy.py")
SCAN = load("ioq_scan", ROOT / "tests/cases/ioq_scan.py")
FCFS = load("ioq_fcfs", ROOT / "tests/cases/ioq_fcfs.py")


def out(cmd):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True).stdout.strip()


def run(cmd, check=True):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=check)


def build(outdir, mode, tc, flag=None):
    return H.build(outdir, mode, tc, flag)


def boot_text(logpath, cpus, hw=False):
    """Boot và trả log; boot lỗi/panic vẫn trả log để oracle chấm."""
    try:
        text, record = H.boot(logpath, cpus, hw=hw)
        return text, True, record
    except RuntimeError:
        return (logpath.read_text() if logpath.exists() else ""), False, {}


def queue_oracle_errors(text):
    errors = []
    errors += [f"I01 deadline: {x}" for x in DEAD.check(text)]
    errors += [f"I01 switch: {x}" for x in SW.check(text)]
    errors += [f"L02 policy oracle: {x}" for x in POL.check(text)]
    errors += [f"SCAN tuần 3: {x}" for x in SCAN.check(text)]
    errors += [f"FCFS tuần 2: thiếu {p}" for p in
               [p for p in FCFS.CASES[0]["expect"] if not re.search(p, text, re.M)]]
    return errors


def mutant_errors(kind, text):
    if kind == "DEADLINE":
        return DEAD.check(text)
    if kind == "SWITCH":
        return SW.check(text)
    return SCAN.check(text)


def parse_snap(text):
    lines = [ln for ln in text.replace("\r", "").splitlines() if ln.startswith("IO-SNAP: ")]
    if not lines:
        return None
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", lines[-1])}


def snap_errors(snap):
    errors = []
    if snap is None:
        return ["thiếu dòng IO-SNAP (snapshot thật)"]
    if snap["S"] != snap["Q"] + snap["I"] + snap["C"] + snap["E"]:
        errors.append("SNAP S != Q+I+C+E")
    if snap["C"] + snap["E"] != snap["R"] + snap["D"] + snap["X"]:
        errors.append("SNAP C+E != R+D+X")
    if 16 != snap["F"] + snap["Q"] + snap["I"] + snap["D"] + snap["X"]:
        errors.append("SNAP pool balance != 16")
    if not (snap["Q"] == snap["I"] == snap["D"] == snap["X"] == 0):
        errors.append("SNAP chưa drain (Q/I/D/X phải 0)")
    if snap["fdesc"] != 8:
        errors.append("SNAP free_desc != 8 sau drain")
    if snap["lat_samples"] <= 0:
        errors.append("SNAP latency samples = 0 (không đo được tick)")
    if snap["wait_sum"] > snap["total_sum"] or snap["service_sum"] > snap["total_sum"]:
        errors.append("SNAP vi phạm wait/service <= total")
    if snap["total_max"] > 0 and snap["zero_total"] > snap["lat_samples"]:
        errors.append("SNAP zero_total > samples")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-mutants", action="store_true")
    ap.add_argument("--no-hardware", action="store_true", help="bỏ bước READ thật")
    ap.add_argument("--results-dir", type=Path)
    args = ap.parse_args()

    try:
        tc = H.resolve_toolchain(None)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    gcc, nm = tc["cc"], tc["nm"]
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    outdir = (args.results_dir or ROOT / "results/week04/oracle-hieu" /
              f"{socket.gethostname()}-{stamp}").resolve()
    if outdir.exists():
        print(f"ERROR: results dir đã tồn tại: {outdir}", file=sys.stderr)
        return 2

    def version(exe):
        r = run([exe, "--version"], check=False)
        return (r.stdout + r.stderr).splitlines()[0] if (r.stdout + r.stderr) else exe

    xv6_pin = (ROOT / ".xv6-commit").read_text().strip() if (ROOT / ".xv6-commit").is_file() else "unknown"
    # Chụp trạng thái source TRƯỚC khi tạo thư mục kết quả, để "dirty" chỉ nói
    # về source đã kiểm, không bị chính output của harness làm bẩn.
    meta = {
        "card": ["W4-G01", "W4-I01"], "started_at": dt.datetime.now().astimezone().isoformat(),
        "host": platform.platform(), "hostname": socket.gethostname(),
        "head": out(["git", "rev-parse", "HEAD"]),
        "branch": out(["git", "branch", "--show-current"]),
        "xv6_pin": xv6_pin,
        "dirty": out(["git", "status", "--porcelain"]),
        "results_dir": str(outdir.relative_to(ROOT)) if outdir.is_relative_to(ROOT) else str(outdir),
        "toolchain": {"toolprefix": tc["toolprefix"], "cc": tc["cc_realpath"],
                      "nm": tc["nm_realpath"]},
        "versions": {"cc": version(gcc), "nm": version(nm),
                     "qemu": version("qemu-system-riscv64"), "make": version("make")},
        "runs": [], "mutants": [], "repo_checks": {}, "builds": {},
    }
    outdir.mkdir(parents=True, exist_ok=False)
    (outdir / "source.patch").write_text(out(["git", "diff", "--binary", "HEAD"]) + "\n")
    (outdir / "untracked-source").mkdir()
    for rel in out(["git", "ls-files", "--others", "--exclude-standard"]).splitlines():
        p = ROOT / rel
        if p.is_file() and rel.split("/")[0] in ("kernel", "scripts", "tests"):
            target = outdir / "untracked-source" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)

    errors = []
    try:
        # -- 1. oracle chính trên mock CPU1/4 ------------------------------
        meta["builds"]["queue"] = build(outdir, "queue", tc, "EXTRA_CFLAGS=-DIOQ_SELFTEST")
        for cpus in (1, 4):
            text, booted, record = boot_text(outdir / f"policy-cpus{cpus}.log", cpus)
            errs = queue_oracle_errors(text)
            if not booted:
                errs.append("boot/panic/timeout")
            status = "FAIL" if errs else "PASS"
            meta["runs"].append({"mode": "I01-oracle-mock", "cpus": cpus, "status": status,
                                 "errors": errs, "log": f"policy-cpus{cpus}.log"})
            print(f"I01 oracle mock cpus={cpus} (deadline+switch+snapshot+SCAN+FCFS): {status}",
                  flush=True)
            errors += [f"cpus={cpus}: {x}" for x in errs]

        # -- 2. mutant ----------------------------------------------------
        if not args.no_mutants:
            patches = sorted((ROOT / "tests/mutants").glob("i01-*.patch")) + \
                sorted((ROOT / "tests/mutants").glob("dl-*.patch")) + \
                sorted((ROOT / "tests/mutants").glob("sw-*.patch"))
            for patch in patches:
                name = patch.stem
                kind = next((v for k, v in MUTANT_ORACLE.items() if name.startswith(k)), "")
                if not kind:
                    errors.append(f"mutant {name}: không map được oracle")
                    continue
                run(["git", "apply", str(patch)])
                try:
                    build(outdir, name, tc, "EXTRA_CFLAGS=-DIOQ_SELFTEST")
                    text, booted, _ = boot_text(outdir / f"{name}-cpus1.log", 1)
                finally:
                    run(["git", "apply", "-R", str(patch)])
                caught = bool(mutant_errors(kind, text))
                meta["mutants"].append({"name": name, "oracle": kind, "caught": caught,
                                        "log": f"{name}-cpus1.log"})
                print(f"mutant {name} ({kind}): "
                      f"{'EXPECTED_FAIL' if caught else 'NOT CAUGHT'}", flush=True)
                if not caught:
                    errors.append(f"mutant {name} không bị oracle {kind} bắt")

        # -- 3. READ thật cơ bản + latency snapshot -----------------------
        if not args.no_hardware:
            meta["builds"]["hardware"] = build(outdir, "hardware", tc, "IO_HW_SELFTEST=1")
            text, booted, _ = boot_text(outdir / "hw-cpus1-snap.log", 1, hw=True)
            hw_errors, _stats = H.check_hw(text)
            snap = parse_snap(text)
            snap_errors_list = snap_errors(snap)
            errs = hw_errors + snap_errors_list
            if not booted:
                errs.append("boot/panic/timeout")
            status = "FAIL" if errs else "PASS"
            meta["runs"].append({"mode": "real-read-timing", "cpus": 1, "status": status,
                                 "errors": errs, "snap": snap,
                                 "log": "hw-cpus1-snap.log"})
            print(f"READ thật cơ bản + IO-SNAP cpus=1: {status}", flush=True)
            errors += [f"real-read: {x}" for x in errs]
    except Exception as exc:  # build/git apply lỗi...
        errors.append(f"lỗi harness: {exc}")
    finally:
        # -- 4. production restore + hook absence -------------------------
        try:
            meta["builds"]["production"] = build(outdir, "production", tc)
            leaked = sorted(set(re.findall(TEST_HOOKS, out([nm, "kernel/kernel"]))))
            meta["production_hooks_absent"] = not leaked
            if leaked:
                errors.append(f"hook test lọt vào production: {leaked}")
        except Exception as exc:
            errors.append(f"build production lỗi: {exc}")

        # -- 5. repo checks ----------------------------------------------
        ct = run([sys.executable, "scripts/check_text.py"], check=False)
        meta["repo_checks"]["check-text"] = {"rc": ct.returncode,
                                            "tail": (ct.stdout + ct.stderr).strip().splitlines()[-3:]}
        if ct.returncode != 0:
            errors.append("scripts/check_text.py FAIL")
        dc = run(["git", "diff", "--check"], check=False)
        meta["repo_checks"]["git-diff-check"] = {"rc": dc.returncode,
                                                "output": (dc.stdout + dc.stderr).strip()}
        if dc.returncode != 0:
            errors.append("git diff --check FAIL")

        meta["finished_at"] = dt.datetime.now().astimezone().isoformat()
        meta["status"] = "FAIL" if errors else "PASS"
        meta["errors"] = errors
        (outdir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")

        lines = ["# W4-I01 — Oracle độc lập deadline/switch + snapshot + mutant\n",
                 f"- Status: **{meta['status']}**",
                 f"- HEAD: `{meta['head']}` (`{meta['branch']}`)",
                 f"- xv6 pin: `{meta['xv6_pin']}`",
                 f"- TOOLPREFIX: `{tc['toolprefix']}`",
                 f"- Dirty lúc chạy: `{'có' if meta['dirty'] else 'không'}`\n",
                 "## 1. Oracle độc lập I01 trên mock (CPU1/4)"]
        lines += [f"- CPUS={r['cpus']}: {r['status']} ({r['log']})"
                  for r in meta["runs"] if r["mode"] == "I01-oracle-mock"]
        lines += ["", "## 2. Mutant (EXPECTED_FAIL)"]
        lines += [f"- {m['name']} [{m['oracle']}]: "
                  f"{'EXPECTED_FAIL' if m['caught'] else 'NOT CAUGHT'} ({m['log']})"
                  for m in meta["mutants"]]
        hw = [r for r in meta["runs"] if r["mode"] == "real-read-timing"]
        lines += ["", "## 3. READ thật cơ bản + snapshot timing"]
        lines += [f"- CPUS={r['cpus']}: {r['status']} ({r['log']})" for r in hw]
        if hw and hw[0].get("snap"):
            s = hw[0]["snap"]
            lines.append(f"- IO-SNAP: samples={s['lat_samples']}, wait_sum={s['wait_sum']}, "
                         f"wait_max={s['wait_max']}, service_sum={s['service_sum']}, "
                         f"service_max={s['service_max']}, total_sum={s['total_sum']}, "
                         f"total_max={s['total_max']}, zero_total={s['zero_total']} tick")
        lines += ["", "## 4. Production + repo checks",
                  f"- production hooks absent: {meta.get('production_hooks_absent')}",
                  f"- check-text rc: {meta['repo_checks'].get('check-text', {}).get('rc')}",
                  f"- git diff --check rc: {meta['repo_checks'].get('git-diff-check', {}).get('rc')}",
                  "",
                  "MOCK deadline/switch: không chứng minh READ thật/seek/latency vật lý.",
                  "READ thật ở đây chỉ 1 boot CPU1 cho mẫu snapshot/timing; acceptance",
                  "SCAN/deadline real 10 boot và máy thứ hai thuộc H01/H02/G02.",
                  "Tick = 100 ms trên QEMU pin: mẫu 0 nghĩa là dưới 1 tick, không phải 0 ms."]
        if errors:
            lines += ["", "## Lỗi"] + [f"- {e}" for e in errors]
        (outdir / "summary.md").write_text("\n".join(lines) + "\n")
        print(f"{meta['status']}: {outdir}", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
