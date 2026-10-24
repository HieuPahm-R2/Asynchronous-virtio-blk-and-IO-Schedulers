# Môi trường phát triển

Mục tiêu: **ba máy trong nhóm dựng được cùng một môi trường**, build và boot
xv6-riscv bằng cùng một commit, để kết quả baseline/benchmark so sánh được.

## Môi trường chuẩn của dự án

| Hạng mục | Lựa chọn | Ghi chú |
| --- | --- | --- |
| OS | Ubuntu 24.04 / **26.04 LTS** VM | Cùng một distro cho cả nhóm; 26.04 vẫn được, chỉ cần ghi version và không trộn số liệu |
| Compiler/binutils | `gcc-riscv64-linux-gnu` (GCC 13.x) | Makefile tự nhận `TOOLPREFIX` |
| QEMU | `qemu-system-riscv64` ≥ 7.2 (gói `qemu-system-misc`) | Makefile có `check-qemu-version` |
| Debug | `gdb-multiarch` | Bắt buộc nếu debug kernel |
| Đo/phân tích | Python 3.12 + matplotlib | Viết script điều khiển QEMU, vẽ đồ thị |
| Build tool | GNU make, bc, perl | `usys.pl` sinh syscall stub; `bc` cho check QEMU |
| Format | `clang-format` | `make fmt` cần clang-format ≥ 19 (xem ghi chú bên dưới) |


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


