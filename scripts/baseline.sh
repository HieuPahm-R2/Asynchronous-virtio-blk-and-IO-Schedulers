#!/usr/bin/env bash
#
# baseline.sh — đo baseline stock xv6 (chưa sửa kernel) và lưu bằng chứng.
#
# Kết quả vào results/baseline/<timestamp>/ gồm:
#   build.log   log build sạch
#   meta.json   commit, toolchain, host, từng case
#   summary.md  bảng PASS/FAIL
#   logs/*.log  serial console từng case
#
# Baseline chỉ có giá trị khi source kernel/user đúng pin xv6 (không dirty).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TAG="${BASELINE_TAG:-baseline}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
RUN_DIR="results/baseline/${STAMP}"

echo "== ET4290 stock baseline — $STAMP =="
echo "== xv6 pin: $(head -n 1 .xv6-commit 2>/dev/null || echo '?') =="

# Cảnh báo nếu source đang bị sửa — baseline phải là stock.
DIRTY_SRC="$(git status --porcelain -- kernel user mkfs Makefile 2>/dev/null | head -n 20 || true)"
if [ -n "$DIRTY_SRC" ]; then
    echo "!! CẢNH BÁO: source kernel/user/Makefile đang khác commit gốc:" >&2
    echo "$DIRTY_SRC" | sed 's/^/   /' >&2
    echo "!! Baseline này sẽ KHÔNG phải stock sạch. Nên commit/stash trước." >&2
fi

mkdir -p "$RUN_DIR/logs"
echo "== Build sạch =="
make clean >/dev/null 2>&1 || true
make -j"$(nproc)" kernel/kernel fs.img 2>&1 | tee "$RUN_DIR/build.log"

echo
echo "== Chạy test (tag=$TAG) =="
set +e
python3 tests/runner.py --tag "$TAG" --results-dir "$RUN_DIR"
RC=$?
set -e

{
    echo
    echo "## Ghi chú"
    echo
    echo "- Chạy lúc: $(date -Iseconds)"
    echo "- Lệnh: \`make baseline\` (build sạch + tag=$TAG)"
    echo "- Ý nghĩa: baseline stock xv6-riscv để so sánh với bản async/scheduler sau này."
    echo "- Giới hạn: QEMU TCG (không KVM) — số liệu tuyệt đối phụ thuộc máy;"
    echo "  chỉ dùng để so sánh cùng máy, cùng QEMU command line."
} >>"$RUN_DIR/NOTES.md"

echo
echo "== Xong baseline: $RUN_DIR =="
if [ "$RC" -ne 0 ]; then
    echo "!! Có case FAIL — xem $RUN_DIR/summary.md" >&2
else
    echo "   tóm tắt: $RUN_DIR/summary.md"
fi
exit "$RC"
