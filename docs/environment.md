# Môi trường phát triển

Mục tiêu: **ba máy trong nhóm dựng được cùng một môi trường**, build và boot
xv6-riscv bằng cùng một commit, để kết quả baseline/benchmark so sánh được.

> Nếu máy bạn là **laptop Ubuntu thật** (không phải WSL), dùng runbook riêng:
> [run-on-ubuntu.md](run-on-ubuntu.md)

## Môi trường chuẩn của dự án

| Hạng mục | Lựa chọn | Ghi chú |
| --- | --- | --- |
| OS | **WSL2 Ubuntu 24.04 LTS** (x86_64) trên Windows 10/11, hoặc Ubuntu 24.04 / **26.04 LTS** VM | Cùng một distro cho cả nhóm; 26.04 vẫn được, chỉ cần ghi version và không trộn số liệu |
| Compiler/binutils | `gcc-riscv64-linux-gnu` (GCC 13.x) | Makefile tự nhận `TOOLPREFIX` |
| QEMU | `qemu-system-riscv64` ≥ 7.2 (gói `qemu-system-misc`) | Makefile có `check-qemu-version` |
| Debug | `gdb-multiarch` | Bắt buộc nếu debug kernel |
| Đo/phân tích | Python 3.12 + matplotlib | Viết script điều khiển QEMU, vẽ đồ thị |
| Build tool | GNU make, bc, perl | `usys.pl` sinh syscall stub; `bc` cho check QEMU |
| Format | `clang-format` | `make fmt` cần clang-format ≥ 19 (xem ghi chú bên dưới) |

Phiên bản chính xác đã cài trên máy dev chuẩn (ghi lại sau khi chạy
`bash scripts/check-env.sh`):

```text
OS        : Ubuntu 24.04 LTS (WSL2, kernel 5.15.167.4-microsoft-standard-WSL2)
gcc       : riscv64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
binutils  : GNU ld (GNU Binutils for Ubuntu) 2.42
qemu      : QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18)
python    : 3.12.3
make      : GNU Make 4.3
gdb       : GNU gdb (Ubuntu 15.1-1ubuntu1~24.04.1) 15.1
clang-fmt : Ubuntu clang-format version 18.1.3 (1ubuntu1)
bc        : bc 1.07.1
xv6 pin   : f780d7850765d74cbdcd1fff4b822d8829f7c9bd (2026-10-15)
```

> Nếu version khác, ghi lại vào báo cáo tuần và mục này để nhóm biết. Không
> trộn môi trường khi so sánh benchmark.

## Cài trên Windows (WSL2) — cách nhanh

Yêu cầu: Windows 10 build ≥ 19041 hoặc Windows 11, đã bật virtualization.

```powershell
# Chỉ cần một lần nếu máy chưa có WSL2
wsl --install --no-distribution

# Trong thư mục repo (PowerShell thường, không cần admin):
powershell -ExecutionPolicy Bypass -File scripts\wsl\import-ubuntu.ps1
```

Script làm các bước sau (có thể làm tay nếu cần):

1. Tải rootfs Ubuntu 24.04 WSL từ `cloud-images.ubuntu.com/wsl/`, kiểm tra SHA256.
2. `wsl --import Ubuntu-24.04 E:\wsl\Ubuntu-24.04 <rootfs.tar.gz> --version 2`.
3. `scripts/wsl/wsl-init.sh` (default user `ubuntu`, sudo NOPASSWD, git
   `safe.directory`, timezone).
4. `scripts/setup-env.sh` (apt install toolchain).
5. `scripts/check-env.sh` (build + boot smoke).

Dùng hằng ngày:

```bash
wsl -d Ubuntu-24.04
cd /mnt/e/ET4290
make qemu
```

### Cài tay (hiểu rõ từng bước)

```powershell
# PowerShell
New-Item -ItemType Directory -Force E:\wsl\downloads, E:\wsl\Ubuntu-24.04 | Out-Null
curl.exe -L -o E:\wsl\downloads\ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz `
  https://cloud-images.ubuntu.com/wsl/releases/24.04/current/ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz
# đối chiếu SHA256 với .../SHA256SUMS
wsl --import Ubuntu-24.04 E:\wsl\Ubuntu-24.04 E:\wsl\downloads\ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz --version 2
wsl -d Ubuntu-24.04 -u root -e bash /mnt/e/ET4290/scripts/wsl/wsl-init.sh
wsl --terminate Ubuntu-24.04
wsl -d Ubuntu-24.04 -u root -e bash /mnt/e/ET4290/scripts/setup-env.sh
wsl -d Ubuntu-24.04 -e bash /mnt/e/ET4290/scripts/check-env.sh
```

## Cài trên Linux / VM

```bash
git clone <repo-url> && cd <repo>
sudo bash scripts/setup-env.sh
bash scripts/check-env.sh
make qemu
```

## Kiểm tra môi trường

```bash
make env-check            # hoặc: bash scripts/check-env.sh
# --quick: chỉ in version, không build/boot
```

`check-env.sh` kiểm tra: distro, WSL, CPU/RAM, toolchain, QEMU ≥ 7.2, pin xv6,
dung lượng đĩa, build `kernel/kernel fs.img`, boot QEMU CPUS=1 và shell trả lời.

## Build & boot

```bash
make                      # build kernel/kernel + fs.img (mặc định)
make qemu                 # boot, CPUS=3 mặc định
make qemu CPUS=1          # 1 CPU (bắt buộc thử với 1 và 4 theo spec)
make qemu CPUS=4
make clean
```

Trong QEMU: `Ctrl-A` rồi `X` để thoát (hoặc đóng terminal).

## Debug với GDB

```bash
# terminal 1
make qemu-gdb CPUS=1
# terminal 2 (thư mục repo)
gdb-multiarch kernel/kernel
(gdb) target remote :25000      # port in ra ở terminal 1 (make print-gdbport)
(gdb) b virtio_disk_rw
(gdb) b virtio_disk_intr
(gdb) c
```

Debug panic: `panic()` in ra file:line; dùng `addr2line -e kernel/kernel <addr>`
hoặc `kernel/kernel.asm`/`kernel.sym` để đối chiếu. Với completion interrupt,
breakpoint trong `virtio_disk_intr` và `kernel/trap.c:devintr` là hữu ích nhất.

## Lưu ý WSL

- **Repo đặt trên `/mnt/e`** (9p) tiện chia sẻ với Windows nhưng chậm hơn ext4.
  Nếu build quá chậm, có thể clone thêm bản trong `~/src/ET4290` để build, và
  dùng `/mnt/e` làm nơi commit; nhưng khi benchmark phải dùng **cùng một đường dẫn**.
- Ưu tiên mở repo bằng **VS Code + Remote WSL** để edit trên Windows, build trong WSL.
- QEMU chạy **TCG** (WSL2 thường không có `/dev/kvm`): chậm hơn KVM vài lần.
  Điều này ảnh hưởng số liệu tuyệt đối — chỉ so sánh giữa các lần đo cùng máy.
- Nếu `apt-get update` lỗi do IPv6: chạy `sudo apt-get -o Acquire::ForceIPv4=true update`
  (setup-env.sh đã tự thử lại).
- `~/.wslconfig` có thể cần chỉnh RAM/CPU nếu máy yếu: `[wsl2] memory=8GB processors=6`.
- Ubuntu import mặc định không có systemd — không cần cho dự án; nếu cần,
  đặt `[boot] systemd=true` trong `/etc/wsl.conf`.

## Format code (tuỳ chọn)

`make fmt` dùng `.clang-format` của upstream xv6, trong đó `ReflowComments: Never`
là giá trị enum chỉ có ở **clang-format ≥ 19**. Ubuntu 24.04 có clang-format 18
nên `make fmt` báo `invalid boolean`. Không ảnh hưởng build/test (CI cũng không
chạy bước format). Nếu muốn format theo chuẩn upstream:

```bash
python3 -m pip install --user "clang-format==20.1.0"
make fmt && git diff --stat
```

## Sự cố thường gặp

| Triệu chứng | Nguyên nhân / cách xử lý |
| --- | --- |
| `Couldn't find a riscv64 version of GCC/binutils` | Chưa cài `gcc-riscv64-linux-gnu`, hoặc dùng `riscv64-unknown-elf-` không có trong PATH |
| `Need qemu version >= 7.2` | QEMU cũ; cài `qemu-system-misc` từ Ubuntu 24.04 |
| `make: bc: No such file` | `sudo apt install bc` |
| QEMU treo ở "xv6 kernel is booting" | Kiểm tra CPU/RAM WSL, hoặc `fs.img` hỏng → `make clean && make` |
| `Permission denied` khi ghi vào `/mnt/e` | Kiểm tra mount/owner; chạy `wsl -d Ubuntu-24.04` với user `ubuntu` |
| Build chậm bất thường | Repo trên `/mnt/e`; cân nhắc build trong ext4 như ghi chú trên |
| `panic: virtio_disk_intr status` | Dữ liệu thiết bị không khớp — thường do sửa driver sai; dùng test harness tái hiện |

## Tái lập trên máy thứ 2 / thứ 3

1. Làm đúng mục "Cài trên Windows" hoặc "Linux/VM".
2. `make env-check` phải exit 0.
3. Ghi version in ra vào báo cáo tuần (hoặc cập nhật bảng trên).
4. Chạy `make baseline` và so `meta.json` với baseline mẫu — commit xv6 và
   toolchain phải khớp; số liệu tuyệt đối có thể khác.

## Pin môi trường

Mọi version ở trên là một phần của "pin môi trường". Khi giảng viên chốt tag
xv6, cập nhật `.xv6-commit` bằng `scripts/update-xv6.sh <tag>` và ghi lại
version mới vào file này. Không nâng cấp toolchain giữa các mốc đo.
