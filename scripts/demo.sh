#!/usr/bin/env bash
#
# demo.sh — chạy demo ngắn (khoảng 20–30 giây) để chứng minh base dự án hoạt động.
#
# Dùng cho:
#   - check-in / báo cáo tiến độ tuần 1 với giảng viên
#   - tự kiểm tra máy mới sau khi clone (thay cho việc mở từng lệnh)
#   - quay video demo dự phòng trước buổi demo chính thức
#
# Sáu phần: môi trường → build → boot → test → baseline đã đo → hạ tầng chờ.
#
# Cách dùng:
#   bash scripts/demo.sh                 # demo đầy đủ (~25 giây)
#   bash scripts/demo.sh --no-qemu       # bỏ phần boot/test, chỉ in thông tin
#   bash scripts/demo.sh --results-dir results/local/demo
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NO_QEMU=0
RESULTS_DIR="results/local/demo"
while [ $# -gt 0 ]; do
    case "$1" in
        --no-qemu) NO_QEMU=1; shift ;;
        --results-dir) RESULTS_DIR="${2:?}"; shift 2 ;;
        --results-dir=*) RESULTS_DIR="${1#*=}"; shift ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "Tham số không hợp lệ: $1" >&2; exit 2 ;;
    esac
done

FAIL=0
section() {
    echo
    echo "================================================================"
    echo " $1"
    echo "================================================================"
}
item() { printf '  %-34s %s\n' "$1" "$2"; }
note() { printf '  -> %s\n' "$*"; }

# ---------------------------------------------------------------------------
section "1/6. MÔI TRƯỜNG & PIN XV6"
# ---------------------------------------------------------------------------
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    item "Distro:" "${PRETTY_NAME:-?}"
fi
item "Kernel:" "$(uname -srm)"
item "CPU / RAM:" "$(nproc) CPU / $(free -h 2>/dev/null | awk '/^Mem:/{print $2}')"
item "Project commit:" "$(git rev-parse --short HEAD 2>/dev/null || echo '?') $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
item "xv6 pin:" "$(cut -d' ' -f1-2 .xv6-commit 2>/dev/null)"
item "RISC-V gcc:" "$(riscv64-linux-gnu-gcc --version 2>/dev/null | head -n1 || echo 'THIẾU')"
if command -v qemu-system-riscv64 >/dev/null 2>&1; then
    item "QEMU:" "$(qemu-system-riscv64 --version | head -n1)"
else
    item "QEMU:" "THIẾU (cài qemu-system-misc)"
    FAIL=1
fi
if [ -e /dev/kvm ]; then
    note "Có /dev/kvm (có thể tăng tốc QEMU nếu muốn, hiện dùng TCG như Makefile)"
else
    note "Không có /dev/kvm — QEMU chạy TCG (chậm hơn KVM, vẫn đúng chức năng)"
fi

# ---------------------------------------------------------------------------
section "2/6. BUILD MỘT LỆNH"
# ---------------------------------------------------------------------------
START=$(date +%s)
if make -s -j"$(nproc)" kernel/kernel fs.img; then
    item "make kernel/kernel fs.img:" "OK ($(($(date +%s) - START)) giây)"
    item "kernel/kernel:" "$(du -h kernel/kernel | cut -f1)"
    item "fs.img:" "$(du -h fs.img | cut -f1)"
else
    item "build:" "FAIL"
    FAIL=1
fi

# ---------------------------------------------------------------------------
section "3/6. BOOT XV6 TRONG QEMU (CPUS=1)"
# ---------------------------------------------------------------------------
if [ "$NO_QEMU" -eq 1 ]; then
    note "bỏ qua theo --no-qemu"
elif python3 tests/runner.py --case boot-smoke --results-dir "$RESULTS_DIR" >/tmp/et4290-demo-boot.txt 2>&1; then
    sed -n '/--- serial console ---/,$p' "$RESULTS_DIR/logs/boot-smoke.log" | sed '1d' | sed '/^$/d; s/^/  /'
    echo
    note "PASS: xv6 boot, init chạy, shell nhận lệnh (log: $RESULTS_DIR/logs/boot-smoke.log)"
else
    sed 's/^/  /' /tmp/et4290-demo-boot.txt
    note "FAIL: boot smoke (xem log trong $RESULTS_DIR)"
    FAIL=1
fi

# ---------------------------------------------------------------------------
section "4/6. TEST HARNESS — PASS/FAIL TỪNG CASE (make test-fast)"
# ---------------------------------------------------------------------------
if [ "$NO_QEMU" -eq 1 ]; then
    note "bỏ qua theo --no-qemu"
elif make -s test-fast; then
    note "PASS: harness chạy được, in PASS/FAIL từng case (log: results/local/)"
else
    note "FAIL: test-fast"
    FAIL=1
fi

# ---------------------------------------------------------------------------
section "5/6. BASELINE STOCK ĐÃ ĐO (bằng chứng tuần 1)"
# ---------------------------------------------------------------------------
BASELINE="$(ls -dt results/baseline/*/ 2>/dev/null | head -n1 || true)"
if [ -n "${BASELINE:-}" ] && [ -f "${BASELINE}summary.md" ]; then
    sed 's/^/  /' "${BASELINE}summary.md"
    echo
    note "Thư mục bằng chứng: $BASELINE"
    note "Chi tiết protocol: docs/baseline.md"
else
    note "chưa có results/baseline/ — chạy 'make baseline' (~19 phút) trước buổi demo"
fi

# ---------------------------------------------------------------------------
section "6/6. HẠ TẦNG CHỜ CHO TUẦN 2 TRỞ ĐI"
# ---------------------------------------------------------------------------
make -s list-tests | sed 's/^/  /'
echo
note "Thiết kế + rủi ro:      docs/architecture.md"
note "Kịch bản demo 20 phút:  docs/demo.md"
note "Việc tuần 1 phải xong:  docs/week1.md"
note "Việc cần chốt với GV:   README.md mục 'Việc cần chốt với giảng viên'"
note "Lệnh tiếp theo:         make qemu CPUS=4  |  make test  |  make baseline"

# ---------------------------------------------------------------------------
section "KẾT QUẢ DEMO"
# ---------------------------------------------------------------------------
if [ "$FAIL" -eq 0 ]; then
    echo "  => TẤT CẢ PASS: môi trường + build + boot + test + baseline đều sẵn sàng."
    exit 0
else
    echo "  => CÓ PHẦN FAIL: xem log ở trên; chạy 'make env-check' để chẩn đoán chi tiết."
    exit 1
fi
