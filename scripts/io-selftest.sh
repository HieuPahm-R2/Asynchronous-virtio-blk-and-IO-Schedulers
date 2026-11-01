#!/usr/bin/env bash
#
# io-selftest.sh — W2-I02 test-only helper.
#
# Boot the kernel that was JUST built with -DIO_SELFTEST directly in QEMU,
# capture the serial log and kill it after a timeout. Unlike
# scripts/run-qemu.sh, this never invokes `make`, so a build made with
# IO_SELFTEST=1 cannot be silently re-linked without the flag (make does not
# track CFLAGS changes). The caller (`make test-io`) greps the log for the
# PASS/FAIL lines.
#
# Usage: bash scripts/io-selftest.sh [--cpus N] [--timeout S] [--log FILE]
#
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

QEMU="${QEMU:-qemu-system-riscv64}"
CPUS=1
TIMEOUT=30
LOG="results/local/io-selftest.log"

while [ $# -gt 0 ]; do
    case "$1" in
        -c|--cpus) CPUS="${2:?}"; shift 2 ;;
        -t|--timeout) TIMEOUT="${2:?}"; shift 2 ;;
        -l|--log) LOG="${2:?}"; shift 2 ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        *) echo "Tham số không hợp lệ: $1" >&2; exit 2 ;;
    esac
done

if [ ! -f kernel/kernel ] || [ ! -f fs.img ]; then
    echo "io-selftest: thiếu kernel/kernel hoặc fs.img — build trước bằng 'make IO_SELFTEST=1'" >&2
    exit 2
fi

mkdir -p "$(dirname "$LOG")"
: > "$LOG"

setsid "$QEMU" \
    -machine virt -bios none -kernel kernel/kernel -m 128M -smp "$CPUS" -nographic \
    -global virtio-mmio.force-legacy=false \
    -drive file=fs.img,if=none,format=raw,id=x0 \
    -device virtio-blk-device,drive=x0,bus=virtio-mmio-bus.0 \
    >"$LOG" 2>&1 &
PID=$!

(
    sleep "$TIMEOUT"
    kill -TERM -- "-$PID" 2>/dev/null || true
    sleep 2
    kill -KILL -- "-$PID" 2>/dev/null || true
) &
WATCHDOG=$!

wait "$PID"
RC=$?
kill "$WATCHDOG" 2>/dev/null || true
wait "$WATCHDOG" 2>/dev/null || true

# 143/137 = stopped by the watchdog after timeout, which is the normal exit for
# an interactive xv6 boot (QEMU keeps running until killed).
case "$RC" in
    0|143|137) exit 0 ;;
    *) exit "$RC" ;;
esac
