#!/usr/bin/env bash
#
# run-qemu.sh — boot xv6 trong QEMU (tuỳ chọn CPUS, ghi serial log, timeout).
#
# Thường chỉ cần `make qemu`. Dùng script này khi muốn:
#   - chọn CPUS nhanh:            bash scripts/run-qemu.sh --cpus 4
#   - ghi log để nộp/báo cáo:     bash scripts/run-qemu.sh --log results/local/boot.log
#   - giới hạn thời gian (CI):    bash scripts/run-qemu.sh --timeout 30
#
# Trong QEMU: Ctrl-A rồi X để thoát. Ở chế độ --timeout, script tự kill cả
# process group (make + qemu) sau khi hết giờ.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CPUS="${CPUS:-3}"
LOG=""
TIMEOUT=""
BUILD=1

usage() { sed -n '2,15p' "$0"; }

while [ $# -gt 0 ]; do
    case "$1" in
        -c|--cpus) CPUS="${2:?}"; shift 2 ;;
        -l|--log) LOG="${2:?}"; shift 2 ;;
        -t|--timeout) TIMEOUT="${2:?}"; shift 2 ;;
        --no-build) BUILD=0; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Tham số không hợp lệ: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [ "$BUILD" -eq 1 ]; then
    make -s kernel/kernel fs.img
fi

if [ -z "$TIMEOUT" ]; then
    if [ -n "$LOG" ]; then
        mkdir -p "$(dirname "$LOG")"
        make qemu CPUS="$CPUS" 2>&1 | tee "$LOG"
    else
        make qemu CPUS="$CPUS"
    fi
    exit 0
fi

# --- chế độ có timeout: chạy trong session riêng để kill được cả qemu con ---
[ -n "$LOG" ] || LOG="results/local/run-qemu-cpus${CPUS}.log"
mkdir -p "$(dirname "$LOG")"
: >"$LOG"

setsid make qemu CPUS="$CPUS" >"$LOG" 2>&1 &
PID=$!
(
    sleep "$TIMEOUT"
    kill -TERM -- "-$PID" 2>/dev/null || true
    sleep 3
    kill -KILL -- "-$PID" 2>/dev/null || true
) &
WATCHDOG=$!

set +e
wait "$PID"
RC=$?
set -e
kill "$WATCHDOG" 2>/dev/null || true
wait "$WATCHDOG" 2>/dev/null || true

cat "$LOG"
echo
echo "== (timeout ${TIMEOUT}s) serial log: $LOG =="
# 143/137 = bị watchdog dừng (bình thường khi chỉ cần boot smoke)
case "$RC" in
    0|143|137) exit 0 ;;
    *) exit "$RC" ;;
esac
