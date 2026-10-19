#!/usr/bin/env bash
#
# wsl-init.sh — cấu hình một distro WSL Ubuntu 24.04 vừa import cho dự án ET4290.
#
# Chạy một lần bằng root, từ Windows:
#   wsl -d Ubuntu-24.04 -u root -e bash /mnt/e/ET4290/scripts/wsl/wsl-init.sh
#
# Việc làm: đặt default user = ubuntu, bật sudo NOPASSWD, cho git thao tác
# repo trên /mnt/*, đặt timezone. Không cài package (xem scripts/setup-env.sh).
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Cần chạy bằng root: wsl -d <distro> -u root -e bash $0" >&2
    exit 1
fi

# Ngay sau lần boot đầu tiên, user database có thể chưa sẵn sàng — chờ tối đa 15s.
for _ in $(seq 1 15); do
    id ubuntu >/dev/null 2>&1 && break
    sleep 1
done
if ! id ubuntu >/dev/null 2>&1; then
    echo "Không thấy user 'ubuntu' trong distro này." >&2
    exit 1
fi

cat >/etc/wsl.conf <<'EOF'
[user]
default=ubuntu

[boot]
systemd=true

[automount]
enabled=true

[interop]
enabled=true
appendWindowsPath=true
EOF

echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' >/etc/sudoers.d/90-et4290
chmod 0440 /etc/sudoers.d/90-et4290

# git coi repo trên /mnt/e là an toàn (ownership drvfs)
git config --system --add safe.directory '*' 2>/dev/null || true

ln -sf /usr/share/zoneinfo/Asia/Ho_Chi_Minh /etc/localtime
echo "Asia/Ho_Chi_Minh" >/etc/timezone

echo "wsl-init xong. Cần 'wsl --terminate <distro>' để áp dụng default user."
