#!/usr/bin/env python3
"""Build, boot, shell/filesystem and reboot-persistence evidence for T1-05H.

Runs stock xv6 without changing kernel/user sources. Each CPU setting gets
a fresh filesystem; its second boot reuses that filesystem deliberately.
This is a smoke check, not the full usertests/grind baseline.
"""

import argparse
import datetime as dt
import json
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from qemu import QemuSession  # noqa: E402


def capture(command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path)
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
    out = args.results_dir or ROOT / "results/local" / now.strftime("hoang-week01-%Y%m%d-%H%M%S")
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    metadata = {
        "started_at": now.isoformat(), "project_commit": capture(["git", "rev-parse", "HEAD"])["stdout"].strip(),
        "xv6_pin": (ROOT / ".xv6-commit").read_text().strip(),
        "source_status": capture(["git", "status", "--porcelain", "--", "kernel", "user", "mkfs", "Makefile", "mk"])["stdout"],
        "host": platform.platform(), "os_release": Path("/etc/os-release").read_text(),
        "tools": {tool: capture([tool, "--version"])["stdout"].splitlines()[:1]
                  for tool in ["riscv64-unknown-elf-gcc", "riscv64-unknown-elf-ld", "qemu-system-riscv64", "make", "python3"]},
        "scope": "Smoke only; no usertests/grind/full regression or async implementation", "checks": [],
    }
    build = capture(["make", "-B", "-j4", "kernel/kernel", "fs.img"])
    (out / "build.log").write_text(build["stdout"] + build["stderr"])
    metadata["checks"].append({"name": "build", "status": "PASS" if build["exit_code"] == 0 else "FAIL", "command": build["command"], "exit_code": build["exit_code"]})
    if build["exit_code"] == 0:
        for cpus in [1, 4]:
            token = f"HOANG_W01_CPUS{cpus}_20261023"
            for phase in ["write-read", "reboot-read"]:
                check = {"name": f"{phase}-cpus{cpus}", "cpus": cpus, "status": "FAIL", "commands": []}
                started = time.monotonic()
                q = QemuSession(cpus=cpus, fresh_fs=(phase == "write-read"))
                try:
                    with q:
                        q.expect(r"\$ $", timeout=30)

                        def shell(command, expected=None):
                            check["commands"].append(command)
                            since = len(q.raw)
                            q.send(command)
                            q.expect([r"\$ $", *([expected] if expected else [])], since=since, timeout=30,
                                     reject=[r"^panic:", r"^exec .*failed", r"^open .*failed", r"^cat: cannot open"])

                        shell("ls", r"README")
                        if phase == "write-read":
                            shell(f"echo {token} > hcheck")
                        shell("cat hcheck", "^" + re.escape(token) + "$")
                        shell("sync")
                        if phase == "reboot-read":
                            shell("rm hcheck")
                            shell("sync")
                        check["status"] = "PASS"
                except Exception as exc:
                    check["error"] = str(exc)
                finally:
                    check["duration_s"] = round(time.monotonic() - started, 3)
                    check["serial_log"] = check["name"] + ".log"
                    (out / check["serial_log"]).write_text(q.raw)
                    metadata["checks"].append(check)
                    print(f"{check['status']} {check['name']} ({check['duration_s']}s)", flush=True)
                if check["status"] != "PASS":
                    break
    metadata["finished_at"] = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).isoformat()
    metadata["passed"] = sum(c["status"] == "PASS" for c in metadata["checks"])
    metadata["failed"] = sum(c["status"] != "PASS" for c in metadata["checks"])
    (out / "checks.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    summary = ["# Kiểm chứng máy Hoàng - tuần 1", "", f"Commit: `{metadata['project_commit']}`", "",
               "| Check | Kết quả |", "| --- | --- |"]
    summary.extend(f"| {c['name']} | {c['status']} |" for c in metadata["checks"])
    summary.extend(["", "Chỉ là smoke; usertests/grind, stress 30 phút và max_inflight: NOT RUN.",
                    "Reboot bằng cách kết thúc QEMU sau sync rồi mở lại cùng fs.img; không mô phỏng mất điện.",
                    "Không kết luận tốc độ hoặc độ bền khi host mất điện từ kiểm tra này."])
    (out / "summary.md").write_text("\n".join(summary) + "\n")
    print(f"{metadata['passed']} PASS / {metadata['failed']} FAIL; evidence: {out}")
    return bool(metadata["failed"])


if __name__ == "__main__":
    raise SystemExit(main())
