#!/usr/bin/env bash
#
# setup-env.sh — cài toolchain để build & chạy xv6-riscv trên Ubuntu/Debian.
#
# Dùng cho WSL2 Ubuntu 24.04 (khuyến nghị trong kế hoạch) hoặc Linux VM.
# Script idempotent: chạy lại nhiều lần không hỏng môi trường.
#
# Cách dùng:
#   sudo bash scripts/setup-env.sh            # cài đủ toolchain + công cụ đo
#   sudo bash scripts/setup-env.sh --minimal  # chỉ cài thứ tối thiểu để build/boot
#
set -euo pipefail

MINIMAL=0
for arg in "$@"; do
    case "$arg" in
        --minimal) MINIMAL=1 ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "Tham số không hợp lệ: $arg" >&2; exit 2 ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Cần quyền root: sudo bash $0" >&2
    exit 1
fi

if [ ! -r /etc/os-release ]; then
    echo "Không nhận diện được distro (thiếu /etc/os-release)" >&2
    exit 1
fi
# shellcheck disable=SC1091
. /etc/os-release
if [ "${ID:-}" != "ubuntu" ] && [ "${ID:-}" != "debian" ]; then
    echo "Script được kiểm thử trên Ubuntu 24.04; distro hiện tại: ${PRETTY_NAME:-unknown}" >&2
    echo "Vẫn tiếp tục, nhưng tên gói có thể khác." >&2
fi

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

CORE_PKGS=(
    build-essential
    git
    ca-certificates
    curl
    wget
    bc
    perl
    python3
    python3-pip
    python3-venv
    gcc-riscv64-linux-gnu
    binutils-riscv64-linux-gnu
    qemu-system-misc
    gdb-multiarch
    file
    less
)

EXTRA_PKGS=(
    clang-format
    jq
    tree
    rsync
    unzip
    zip
    vim
    tmux
    htop
    python3-matplotlib
)

PKGS=("${CORE_PKGS[@]}")
if [ "$MINIMAL" -eq 0 ]; then
    PKGS+=("${EXTRA_PKGS[@]}")
fi

echo "==> apt-get update"
if ! apt-get update; then
    echo "==> apt-get update lỗi; thử ép IPv4 (một số mạng WSL chỉ có IPv6 lỗi)" >&2
    echo 'Acquire::ForceIPv4 "true";' >/etc/apt/apt.conf.d/99force-ipv4-et4290
    apt-get update
fi

echo "==> Cài gói: ${PKGS[*]}"
apt-get install -y --no-install-recommends "${PKGS[@]}"

echo "==> Dọn cache apt"
apt-get clean

# Locale UTF-8 ổn định cho log/tiếng Việt
if [ -z "${LANG:-}" ] || ! locale -a 2>/dev/null | grep -qi '^C.utf8$'; then
    :
fi
if [ -f /etc/default/locale ]; then
    grep -q '^LANG=' /etc/default/locale 2>/dev/null || echo 'LANG=C.UTF-8' >>/etc/default/locale
fi

echo
echo "==> Kiểm tra phiên bản toolchain"
fail=0
check() {
    local label="$1"; shift
    if command -v "$1" >/dev/null 2>&1; then
        printf '  %-34s %s\n' "$label" "$("$@" 2>&1 | head -n 1)"
    else
        printf '  %-34s %s\n' "$label" "THIẾU: $1"
        fail=1
    fi
}
check "make" make --version
check "git" git --version
check "python3" python3 --version
check "riscv64 gcc" riscv64-linux-gnu-gcc --version
check "riscv64 ld" riscv64-linux-gnu-ld --version
check "riscv64 objcopy" riscv64-linux-gnu-objcopy --version
check "qemu-system-riscv64" qemu-system-riscv64 --version
check "gdb-multiarch" gdb-multiarch --version
check "bc" bc --version

if [ "$fail" -ne 0 ]; then
    echo "==> Cài đặt chưa đầy đủ, xem các dòng THIẾU ở trên" >&2
    exit 1
fi

echo
echo "==> Môi trường sẵn sàng. Tiếp theo:"
echo "    bash scripts/check-env.sh      # kiểm tra đầy đủ, gồm build thử"
echo "    make qemu                      # boot xv6"
