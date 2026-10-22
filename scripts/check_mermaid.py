#!/usr/bin/env python3
"""Lint các khối Mermaid trong tài liệu markdown (không cần cài Mermaid).

Bắt các lỗi cú pháp phổ biến đã từng làm Mermaid báo "Parse error":
  - nhãn cạnh `|...|` chứa ký tự đặc biệt (`(`, `)`, `;`) mà không đặt trong ngoặc kép;
  - nhãn cạnh chứa `->` (rất dễ bị tokenizer hiểu sai).

Cách dùng:
    python3 scripts/check_mermaid.py          # quét mọi *.md trong git
    python3 scripts/check_mermaid.py -v

Quy ước an toàn: nhãn cạnh chứa ký tự đặc biệt thì viết
    A -->|"b.disk = 0, wakeup(b)"| B
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
EDGE_LABEL = re.compile(r"\|([^|\n]+)\|")
# Ký tự đặc biệt khiến nhãn chưa quote bị Mermaid hiểu sai.
RISKY = re.compile(r"[();]|->")


def tracked_markdown() -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
        )
        if proc.returncode == 0:
            return [ROOT / line for line in proc.stdout.splitlines() if line]
    except FileNotFoundError:
        pass
    return sorted(ROOT.rglob("*.md"))


def main(argv: list[str]) -> int:
    verbose = "-v" in argv or "--verbose" in argv
    problems = 0
    blocks = 0
    for path in tracked_markdown():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for block_no, m in enumerate(MERMAID_BLOCK.finditer(text), 1):
            blocks += 1
            start_line = text[: m.start()].count("\n") + 2
            for line_no, line in enumerate(m.group(1).splitlines(), 1):
                for label in EDGE_LABEL.finditer(line):
                    raw = label.group(1).strip()
                    if raw.startswith('"') and raw.endswith('"'):
                        continue
                    if RISKY.search(raw):
                        problems += 1
                        print(
                            f"FAIL {path.relative_to(ROOT)} block {block_no} "
                            f"(dòng ~{start_line + line_no - 1}): nhãn cạnh cần quote: |{raw}|"
                        )
                        print('     sửa thành: |"..."| và tránh ";" / "->" trong nhãn')
    print()
    if problems == 0:
        print(f"== check-mermaid: PASS — {blocks} khối Mermaid, không thấy lỗi cú pháp phổ biến ==")
        return 0
    print(f"== check-mermaid: FAIL — {problems} nhãn cần sửa ==")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
