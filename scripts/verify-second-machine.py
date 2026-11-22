#!/usr/bin/env python3
"""W5-H01 — Verify a clean candidate on a second physical machine (Lợi).

Mục đích: chạy lại **candidate sạch** (SHA đã chốt ở W5-G01) trên một **host khác
host Hoàng** và thu một gói bằng chứng độc lập: policy/switch READ thật CPU1/4,
oracle độc lập I01 + 6 mutant, (tuỳ chọn `--full`) regression FCFS 20 boot và repo
checks. Script chạy trên checkout **đích** (target) nhưng không sửa target: mọi kết
quả ghi vào `--results-dir` của repo điều phối (thường nằm ở checkout main).

Quy tắc (theo kế hoạch tuần 5 §W5-H01):
  - Target phải là git checkout **sạch** (`git status --porcelain` rỗng) đúng SHA.
  - Hostname phải **khác** host của Hoàng (mặc định `nguyen-van-hoang-20233413`);
    CPU1/4 trên cùng host không được tính là hai máy.
  - Một checkout chỉ chạy một build/harness tại một thời điểm (các suite chạy tuần tự).
  - Ghi SHA/dirty/machine/OS/toolchain/lệnh/raw log vào `second-machine.json` +
    `summary.md`; negative EXPECTED_FAIL báo riêng, không cộng vào PASS.
  - Thiếu một suite bắt buộc ⇒ overall FAIL; suite không chạy ghi **NOT RUN**.

Ví dụ (chạy từ checkout main, target là clone sạch của candidate):

    python3 scripts/verify-second-machine.py \
      --target /path/to/clean-candidate \
      --results-dir results/week05/second-machine/$(hostname)-$(date +%Y%m%d-%H%M%S) \
      --full --operator "Lợi (theo phân công W5-H01)" \
      --toolprefix riscv64-linux-gnu-

`--full` = policy/switch + oracle + FCFS regression (20 boot) + check-text/diff-check.
Không có `--full`: chỉ policy/switch + oracle.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

OTHER_HOST_DEFAULT = "nguyen-van-hoang-20233413"
CANDIDATE_PREFIXES = (
    "riscv64-unknown-elf-",
    "riscv64-elf-",
    "riscv64-none-elf-",
    "riscv64-linux-gnu-",
    "riscv64-unknown-linux-gnu-",
)
SUITE_TIMEOUT = 3600


def output(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True).stdout.strip()


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe_toolprefix(target, explicit):
    if explicit:
        return explicit
    try:
        r = subprocess.run(["make", "-s", "print-toolprefix"], cwd=target,
                           text=True, capture_output=True, check=False)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except OSError:
        pass
    for cand in CANDIDATE_PREFIXES:
        objdump = shutil.which(cand + "objdump")
        if not objdump:
            continue
        try:
            info = subprocess.check_output([objdump, "-i"], cwd=target, text=True,
                                           stderr=subprocess.STDOUT)
        except (OSError, subprocess.CalledProcessError):
            continue
        if "elf64-big" in info:
            return cand
    raise RuntimeError("không tìm thấy toolchain RISC-V (unknown-elf/linux-gnu)")


def tool_versions(prefix):
    versions = {}
    for tool in (prefix + "gcc", prefix + "nm", "qemu-system-riscv64", "make", "python3"):
        exe = shutil.which(tool)
        if not exe:
            versions[tool] = "MISSING"
            continue
        try:
            r = subprocess.run([exe, "--version"], text=True, capture_output=True, check=False)
            versions[tool] = (r.stdout + r.stderr).splitlines()[0]
        except OSError:
            versions[tool] = exe
    return versions


def clean_state(target):
    return {
        "dirty": output(["git", "status", "--porcelain"], target),
        "sha": output(["git", "rev-parse", "HEAD"], target),
        "branch": output(["git", "branch", "--show-current"], target),
        "remote": output(["git", "remote", "get-url", "origin"], target),
    }


def run_suite(name, command, target, logdir, timeout=SUITE_TIMEOUT):
    """Chạy một suite tuần tự, lưu stdout+stderr, trả record."""
    log = logdir / f"{name}.log"
    started = dt.datetime.now()
    with log.open("w", encoding="utf-8") as fh:
        fh.write("$ " + " ".join(command) + "\n\n")
        fh.flush()
        try:
            proc = subprocess.run(command, cwd=target, text=True, stdout=fh,
                                  stderr=subprocess.STDOUT, timeout=timeout)
            rc = proc.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            rc = -1
            timed_out = True
    duration = (dt.datetime.now() - started).total_seconds()
    print(f"  {name}: rc={rc}{' TIMEOUT' if timed_out else ''} ({duration:.0f}s)", flush=True)
    return {"name": name, "command": command, "exit_code": rc, "timeout": timed_out,
            "duration_s": round(duration, 1), "log": log.name}


def suite_meta(suite_outdir):
    """Đọc meta.json/summary.md của suite để lấy status + đếm PASS/EXPECTED_FAIL/FAIL."""
    meta_path = suite_outdir / "meta.json"
    summary_path = suite_outdir / "summary.md"
    info = {"status": "UNKNOWN", "runs": [], "errors": [], "meta": None,
            "summary": summary_path.name if summary_path.exists() else None}
    if not meta_path.exists():
        return info
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return info
    info["meta"] = meta_path.name
    info["status"] = meta.get("status", "UNKNOWN")
    info["errors"] = meta.get("errors", [])[:10]
    counts = {"PASS": 0, "EXPECTED_FAIL": 0, "FAIL": 0, "OTHER": 0}
    for record in meta.get("runs", []):
        status = record.get("status", "")
        counts[status if status in counts else "OTHER"] += 1
    mutants = meta.get("mutants", [])
    for mutant in mutants:
        if mutant.get("caught"):
            counts["EXPECTED_FAIL"] += 1
        else:
            counts["FAIL"] += 1
    info["runs"] = meta.get("runs", [])
    info["mutants"] = [{"name": m.get("name"), "caught": bool(m.get("caught"))}
                       for m in mutants]
    info["counts"] = counts
    return info


def repo_checks(target, logdir):
    checks = {}
    for name, command in (("check-text", [sys.executable, "scripts/check_text.py"]),
                          ("git-diff-check", ["git", "diff", "--check"])):
        log = logdir / f"repo-{name}.log"
        with log.open("w", encoding="utf-8") as fh:
            fh.write("$ " + " ".join(command) + "\n\n")
            fh.flush()
            proc = subprocess.run(command, cwd=target, text=True, stdout=fh,
                                  stderr=subprocess.STDOUT, check=False)
        checks[name] = {"exit_code": proc.returncode, "log": log.name}
        print(f"  repo {name}: rc={proc.returncode}", flush=True)
    return checks


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, type=Path, help="clean candidate checkout")
    ap.add_argument("--results-dir", required=True, type=Path)
    ap.add_argument("--full", action="store_true",
                    help="thêm FCFS regression 20 boot + check-text/diff-check")
    ap.add_argument("--toolprefix", default=None)
    ap.add_argument("--operator", default=os.environ.get("USER", "unknown"))
    ap.add_argument("--other-host", default=OTHER_HOST_DEFAULT,
                    help="host của máy đã chạy candidate (Hoàng); hostname này phải khác")
    ap.add_argument("--stress-repeat", type=int, default=5)
    ap.add_argument("--allow-same-host", action="store_true",
                    help="hạ mức kiểm tra hai máy thành cảnh báo (không nên dùng)")
    args = ap.parse_args()

    target = args.target.resolve()
    outdir = args.results_dir.resolve()
    host = socket.gethostname()
    started = dt.datetime.now().astimezone()

    if not (target / ".git").exists():
        print(f"ERROR: target không phải git checkout: {target}", file=sys.stderr)
        return 2
    if outdir.exists():
        print(f"ERROR: results dir đã tồn tại: {outdir}", file=sys.stderr)
        return 2
    if outdir == target or target in outdir.parents:
        print("ERROR: results dir phải nằm ngoài target để giữ target sạch", file=sys.stderr)
        return 2

    for required in ("scripts/check-week04-hoang.py", "scripts/check-week04-oracle-hieu.py",
                     "scripts/check_text.py"):
        if not (target / required).is_file():
            print(f"ERROR: target thiếu {required} (sai candidate?)", file=sys.stderr)
            return 2
    if args.full and not (target / "scripts/check-week02-hoang.py").is_file():
        print("ERROR: target thiếu scripts/check-week02-hoang.py", file=sys.stderr)
        return 2

    other_host = args.other_host.strip()
    same_host = host == other_host
    if same_host and not args.allow_same_host:
        print(f"ERROR: hostname '{host}' trùng host đã chạy ({other_host}); "
              f"CPU1/4 trên cùng host không tính là máy thứ hai.", file=sys.stderr)
        return 2

    state_start = clean_state(target)
    if state_start["dirty"]:
        print("ERROR: target không sạch (git status --porcelain khác rỗng):", file=sys.stderr)
        print(state_start["dirty"], file=sys.stderr)
        return 2
    if not state_start["sha"]:
        print("ERROR: không đọc được SHA của target", file=sys.stderr)
        return 2

    try:
        toolprefix = probe_toolprefix(target, args.toolprefix)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    versions = tool_versions(toolprefix)

    outdir.mkdir(parents=True, exist_ok=False)
    (outdir / "logs").mkdir()

    py = sys.executable
    suites = []
    errors = []
    try:
        # -- 1. policy/switch real CPU1/4 + negative + production restore --
        cmd = [py, "scripts/check-week04-hoang.py", "--mode", "all",
               "--repeat", str(args.stress_repeat), "--cpus", "1", "4",
               "--toolprefix", toolprefix,
               "--results-dir", str(outdir / "real-and-switch")]
        suites.append(run_suite("real-and-switch", cmd, target, outdir / "logs"))

        # -- 2. oracle độc lập I01 + mutant + READ thật snapshot ----------
        cmd = [py, "scripts/check-week04-oracle-hieu.py",
               "--results-dir", str(outdir / "independent-oracle")]
        suites.append(run_suite("independent-oracle", cmd, target, outdir / "logs"))

        # -- 3. regression FCFS 20 boot + pool/queue mock (--full) ---------
        if args.full:
            cmd = [py, "scripts/check-week02-hoang.py", "--repeat", "10",
                   "--toolprefix", toolprefix,
                   "--results-dir", str(outdir / "fcfs-regression")]
            suites.append(run_suite("fcfs-regression", cmd, target, outdir / "logs"))

        # -- 4. repo checks (--full) --------------------------------------
        checks = repo_checks(target, outdir / "logs") if args.full else {}
    except Exception as exc:  # noqa: BLE001 - harness lỗi phải vào summary
        errors.append(f"harness exception: {exc}")
        checks = {}

    state_end = clean_state(target)
    if state_end["dirty"]:
        errors.append("target bị dirty sau khi chạy (harness không được sửa source)")

    # -- tổng hợp ----------------------------------------------------------
    suite_records = []
    for suite in suites:
        suite_dir = outdir / suite["name"]
        info = suite_meta(suite_dir) if suite["name"] == "real-and-switch" or \
            suite["name"] == "independent-oracle" or suite["name"] == "fcfs-regression" else {}
        status = info.get("status", "UNKNOWN")
        if suite["exit_code"] != 0 or status not in ("PASS",):
            errors.append(f"suite {suite['name']} status={status} rc={suite['exit_code']}")
        suite_records.append({
            **{k: v for k, v in suite.items() if k != "runs"},
            "status": status,
            "expected_fail": info.get("counts", {}).get("EXPECTED_FAIL", 0),
            "pass_runs": info.get("counts", {}).get("PASS", 0),
            "fail_runs": info.get("counts", {}).get("FAIL", 0),
            "mutants": info.get("mutants", []),
            "suite_meta": info.get("meta"),
            "suite_summary": info.get("summary"),
            "first_errors": info.get("errors", []),
        })
        print(f"  {suite['name']}: {status} "
              f"(PASS={info.get('counts', {}).get('PASS', 0)}, "
              f"EXPECTED_FAIL={info.get('counts', {}).get('EXPECTED_FAIL', 0)})", flush=True)

    overall = "FAIL" if errors else "PASS"
    record = {
        "card": "W5-H01",
        "purpose": "verify clean candidate on a second physical host (not Hoang host)",
        "operator": args.operator,
        "machine": {
            "hostname": host,
            "host": platform.platform(),
            "os": f"{platform.system()} {platform.release()}",
            "other_host": other_host,
            "different_from_other_host": not same_host,
            "same_host_override": bool(same_host and args.allow_same_host),
        },
        "candidate": {
            "path": str(target),
            "sha": state_start["sha"],
            "branch": state_start["branch"],
            "remote": state_start["remote"],
            "dirty_start": state_start["dirty"],
            "dirty_end": state_end["dirty"],
            "xv6_pin": (target / ".xv6-commit").read_text().strip()
            if (target / ".xv6-commit").is_file() else "unknown",
            "clean": not state_start["dirty"] and not state_end["dirty"],
        },
        "toolchain": {"toolprefix": toolprefix, "versions": versions},
        "verifier_script_sha256": sha256_file(Path(__file__).resolve()),
        "started_at": started.isoformat(),
        "arguments": vars(args) | {"target": str(target), "results_dir": str(outdir)},
        "suites": suite_records,
        "repo_checks": checks,
        "expected_fail": sum(s["expected_fail"] for s in suite_records),
        "not_run": ([] if args.full else ["fcfs-regression (chưa dùng --full)"]),
        "status": overall,
        "errors": errors,
        "notes": [
            "CPU1/4 trên cùng host không tính là hai máy; host này khác host đã chạy candidate.",
            "QEMU virtio-blk không chứng minh seek vật lý; 0 tick nghĩa là dưới 1 tick (≈100 ms), không phải 0 ms.",
            "Negative control EXPECTED_FAIL báo riêng, không cộng vào PASS.",
        ],
    }
    record["finished_at"] = dt.datetime.now().astimezone().isoformat()
    (outdir / "second-machine.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = ["# W5-H01 — Candidate verification trên máy thứ hai", "",
             f"- Status: **{overall}**",
             f"- Candidate SHA: `{state_start['sha']}` ({state_start['branch'] or 'detached'})",
             f"- Source sạch: start={not bool(state_start['dirty'])}, end={not bool(state_end['dirty'])}",
             f"- Operator: {args.operator}",
             f"- Máy: `{host}` — {record['machine']['os']}",
             f"- Host khác host đã chạy (`{other_host}`): {not same_host}",
             f"- Toolchain: `{toolprefix}`", "",
             "## Môi trường", "",
             "| Hạng mục | Giá trị |", "| :--- | :--- |",
             f"| Hostname | `{host}` |",
             f"| OS / kernel | {record['machine']['os']} / {platform.release()} |",
             f"| Python | {versions.get('python3', 'MISSING')} |",
             f"| Compiler | {versions.get(toolprefix + 'gcc', 'MISSING')} |",
             f"| QEMU | {versions.get('qemu-system-riscv64', 'MISSING')} |",
             f"| Make | {versions.get('make', 'MISSING')} |",
             f"| xv6 pin | `{record['candidate']['xv6_pin']}` |", "",
             "## Kết quả suite", "",
             "| Suite | Kết quả | PASS | EXPECTED_FAIL | FAIL | Log/meta |",
             "| :--- | :---: | :---: | :---: | :---: | :--- |"]
    for s in suite_records:
        lines.append(f"| {s['name']} | **{s['status']}** | {s['pass_runs']} | "
                     f"{s['expected_fail']} | {s['fail_runs']} | "
                     f"`logs/{s['log']}`, `{s['name']}/summary.md` |")
    lines += ["", f"- EXPECTED_FAIL tổng: **{record['expected_fail']}** (không cộng vào PASS)"]
    mutants = [(s["name"], m["name"], m["caught"]) for s in suite_records
               for m in s.get("mutants", [])]
    if mutants:
        lines += ["", "## Negative control (EXPECTED_FAIL riêng)", "",
                  "| Suite | Mutant | Kết quả |", "| :--- | :--- | :---: |"]
        lines += [f"| {suite} | {name} | "
                  f"{'EXPECTED_FAIL' if caught else 'NOT CAUGHT'} |"
                  for suite, name, caught in mutants]
    if record["not_run"]:
        lines += ["", "## NOT RUN"] + [f"- {x}" for x in record["not_run"]]
    if checks:
        lines += ["", "## Repo checks"] + [
            f"- {k}: rc={v['exit_code']}" for k, v in checks.items()]
    lines += ["", "## Lưu ý"] + [f"- {n}" for n in record["notes"]]
    if errors:
        lines += ["", "## Lỗi"] + [f"- {e}" for e in errors]
    (outdir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{overall}: {outdir}", flush=True)
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
