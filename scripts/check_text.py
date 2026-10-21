#!/usr/bin/env python3
"""Kiểm tra lỗi encoding của file text trong repo.

Phát hiện 3 loại lỗi hay gặp khi làm việc đa nền (Windows/PowerShell + WSL/Linux):

1. File không phải UTF-8 hợp lệ.
2. Mojibake — UTF-8 bị đọc như latin1/cp1252 rồi lưu lại: văn bản tiếng Việt bị
   "lỗi font", mỗi ký tự có dấu biến thành 2–3 ký tự latin rác.
3. CRLF trong file thực thi/script (.sh, .py, .mk, Makefile) — bash/gcc có thể lỗi.

Cách dùng:
    python3 scripts/check_text.py          # kiểm tra
    python3 scripts/check_text.py -v       # in cả file đã quét

Exit code 0 nếu sạch, 1 nếu có lỗi.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BINARY_SUFFIXES = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".img", ".gz", ".zip",
    ".o", ".d", ".asm", ".sym", ".bin", ".iso", ".vmdk",
}
# Script cần LF; file khác CRLF chỉ cảnh báo.
MUST_LF_SUFFIXES = {".sh", ".py", ".mk", ".pl"}
MUST_LF_NAMES = {"Makefile", "makefile"}

# Dấu hiệu mojibake của tiếng Việt UTF-8 bị giải mã latin1/cp1252.
# Viết bằng unicode escape để chính file này không bị regex của nó bắt.
# Các chuỗi dưới đây gần như không bao giờ xuất hiện trong văn bản tiếng Việt đúng.
MOJIBAKE_RE = re.compile(
    "(\u00c3[\u0080-\u024f]"
    "|\u00e1\u00ba|\u00e1\u00bb"
    "|\u00c6[\u0080-\u024f]"
    "|\u00c4\u2018"
    "|\u00e2\u00bb|\u00e2\u20ac"
    "|\u00c2[\u0080-\u009f])"
)


def tracked_files() -> list[Path]:
    """Danh sách file do git quản lý; fallback quét cây nếu không có git."""
    try:
        proc = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
        )
        if proc.returncode == 0:
            return [ROOT / line for line in proc.stdout.splitlines() if line]
    except FileNotFoundError:
        pass
    result = []
    for p in ROOT.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            result.append(p)
    return result


def check(path: Path) -> list[str]:
    errors: list[str] = []
    if path.suffix.lower() in BINARY_SUFFIXES:
        return errors
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [f"không đọc được: {exc}"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"không phải UTF-8 hợp lệ: {exc}"]

    for lineno, line in enumerate(text.splitlines(), 1):
        if MOJIBAKE_RE.search(line):
            errors.append(f"dòng {lineno}: mojibake: {line[:100]!r}")

    needs_lf = path.suffix.lower() in MUST_LF_SUFFIXES or path.name in MUST_LF_NAMES
    if needs_lf and b"\r\n" in raw:
        errors.append("có CRLF — file script phải dùng LF (chạy `dos2unix`/sửa editor)")
    return errors


def main(argv: list[str]) -> int:
    verbose = "-v" in argv or "--verbose" in argv
    files = tracked_files()
    total_errors = 0
    checked = 0
    for path in files:
        if not path.is_file():
            continue
        checked += 1
        errs = check(path)
        if errs:
            total_errors += len(errs)
            print(f"FAIL {path.relative_to(ROOT)}")
            for e in errs[:5]:
                print(f"     {e}")
            if len(errs) > 5:
                print(f"     ... và {len(errs) - 5} lỗi nữa")
        elif verbose:
            print(f"OK   {path.relative_to(ROOT)}")

    print()
    if total_errors == 0:
        print(f"== check-text: PASS — {checked} file UTF-8 sạch, không mojibake ==")
        return 0
    print(f"== check-text: FAIL — {total_errors} lỗi trong {checked} file ==")
    print("   Sửa bằng editor lưu UTF-8 (không BOM), line ending LF cho script;")
    print("   hoặc `git checkout -- <file>` nếu file trên đĩa bị hỏng.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
