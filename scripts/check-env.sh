#!/usr/bin/env bash
#
# check-env.sh — kiểm tra môi trường phát triển ET4290 đã sẵn sàng chưa.
#
# Kiểm tra: OS, toolchain RISC-V, QEMU, công cụ phụ, pin xv6, build sạch và
# boot thử 1 lần. Exit code 0 nếu mọi thứ OK.
#
# Cách dùng:
#   bash scripts/check-env.sh            # đầy đủ (build + boot smoke ~15s)
#   bash scripts/check-env.sh --quick    # chỉ kiểm tra version, không build/boot
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

QUICK=0
for arg in "$@"; do
    case "$arg" in
        --quick) QUICK=1 ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "Tham số không hợp lệ: $arg" >&2; exit 2 ;;
    esac
done

fail=0
warn=0
ok() { printf '  [ OK ] %s\n' "$*"; }
bad() { printf '  [FAIL] %s\n' "$*"; fail=$((fail + 1)); }
warning() { printf '  [WARN] %s\n' "$*"; warn=$((warn + 1)); }

echo "== Hệ điều hành =="
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "  distro: ${PRETTY_NAME:-unknown}"
else
    warning "không đọc được /etc/os-release (không phải Linux?)"
fi
echo "  kernel: $(uname -r)"
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "  môi trường: WSL2"
else
    echo "  môi trường: Linux (không phải WSL)"
fi
echo "  CPU: $(nproc)  |  RAM: $(free -h 2>/dev/null | awk '/^Mem:/{print $2}')"
echo "  thư mục: $ROOT"

echo
echo "== Pin xv6-riscv =="
if [ -f .xv6-commit ]; then
    echo "  $(cat .xv6-commit)"
    ok "đã ghi pin xv6 (.xv6-commit)"
else
    bad "thiếu .xv6-commit — không biết đang dựa trên commit xv6 nào"
fi

echo
echo "== Toolchain =="
check_cmd() {
    local label="$1" cmd="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        ok "$label: $("$cmd" --version 2>/dev/null | head -n 1)"
        return 0
    fi
    bad "$label: thiếu lệnh '$cmd'"
    return 1
}

check_cmd "make" make
check_cmd "git" git
check_cmd "python3" python3
check_cmd "bc" bc
if command -v perl >/dev/null 2>&1; then
    ok "perl: $(perl -e 'print $^V' 2>/dev/null)"
else
    bad "perl: thiếu lệnh 'perl' (cần cho user/usys.pl)"
fi

CC=""
for cand in riscv64-linux-gnu-gcc riscv64-unknown-elf-gcc riscv64-elf-gcc riscv64-none-elf-gcc; do
    if command -v "$cand" >/dev/null 2>&1; then
        CC="$cand"
        break
    fi
done
if [ -n "$CC" ]; then
    ok "RISC-V gcc: $("$CC" --version | head -n 1)  (TOOLPREFIX tự nhận diện)"
else
    bad "không tìm thấy RISC-V gcc (gói gcc-riscv64-linux-gnu)"
fi

if command -v qemu-system-riscv64 >/dev/null 2>&1; then
    QEMU_VER="$(qemu-system-riscv64 --version | head -n 1)"
    ok "$QEMU_VER"
    qv="$(echo "$QEMU_VER" | sed -nE 's/^QEMU emulator version ([0-9]+\.[0-9]+).*/\1/p')"
    if [ -n "$qv" ] && [ "$(echo "$qv >= 7.2" | bc)" -eq 1 ]; then
        ok "QEMU >= 7.2"
    else
        bad "QEMU phải >= 7.2 (Makefile yêu cầu); hiện tại: ${qv:-?}"
    fi
else
    bad "thiếu qemu-system-riscv64 (Ubuntu 24.04: gói qemu-system-misc; Ubuntu 26.04+: gói qemu-system-riscv)"
fi

command -v gdb-multiarch >/dev/null 2>&1 \
    && ok "gdb-multiarch (debug kernel)" \
    || warning "thiếu gdb-multiarch — chỉ cần khi debug bằng GDB"

command -v clang-format >/dev/null 2>&1 \
    && ok "clang-format ($(clang-format --version))" \
    || warning "thiếu clang-format — cần cho 'make fmt' và CI"

echo
echo "== Dung lượng đĩa =="
AVAIL_KB="$(df -Pk "$ROOT" | awk 'NR==2{print $4}')"
AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
if [ "$AVAIL_KB" -gt $((1024 * 1024)) ]; then
    ok "còn ${AVAIL_GB} GiB trống tại $(df -Pk "$ROOT" | awk 'NR==2{print $6}')"
else
    warning "chỉ còn ${AVAIL_GB} GiB trống — cần thêm cho fs.img/build"
fi

if [ "$QUICK" -eq 1 ]; then
    echo
    [ "$fail" -eq 0 ] && echo "== OK (quick): môi trường cơ bản đạt ==" || echo "== CÓ LỖI: xem [FAIL] ở trên =="
    [ "$fail" -eq 0 ] || exit 1
    exit 0
fi

echo
echo "== Build thử (make -j) =="
BUILD_LOG="$(mktemp -t et4290-build.XXXXXX.log)"
if make -j"$(nproc)" kernel/kernel fs.img >"$BUILD_LOG" 2>&1; then
    ok "build kernel/kernel + fs.img thành công ($(du -h kernel/kernel | cut -f1) kernel)"
else
    bad "build thất bại — 30 dòng log cuối:"
    tail -n 30 "$BUILD_LOG" | sed 's/^/        /'
fi
rm -f "$BUILD_LOG"

echo
echo "== Boot smoke (QEMU, CPUS=1) =="
if python3 tests/runner.py --case boot-smoke \
    --results-dir results/local/env-check 2>&1 | sed 's/^/  /'; then
    ok "QEMU boot xv6 và shell trả lời"
else
    bad "boot smoke thất bại — xem results/local/env-check/"
fi

echo
if [ "$fail" -eq 0 ]; then
    echo "== MÔI TRƯỜNG SẴN SÀNG (cảnh báo: $warn) =="
    echo "   make qemu              # boot xv6"
    echo "   make test              # chạy test suite"
    echo "   make baseline          # ghi baseline stock vào results/"
    exit 0
else
    echo "== CÓ $fail LỖI — sửa theo gợi ý ở trên rồi chạy lại =="
    echo "   Gợi ý: sudo bash scripts/setup-env.sh"
    exit 1
fi
