# Version log & môi trường tái lập — tuần 1 (T1-05)

> **Owner:** Hiếu (điều phối). Mỗi người **điền dòng của máy mình** ngay sau khi
> chạy `make env-check`; không copy số của máy khác. Giữ commit giống nhau để
> so sánh được.

## 1. Bảng version 3 máy

| Máy | Người | OS | xv6 pin | gcc RISC-V | QEMU | gdb | python | Ngày | `make env-check` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev-WSL2 (máy mẫu) | base | Ubuntu 24.04 (WSL2) | `f780d785` | 13.3.0 | 8.2.2 | 15.1 | 3.12.3 | 21/10/2026 | **PASS** |
| laptop-Hiếu | Hiếu | Ubuntu 26.04.1 | `f780d785` | 15.2.0 | 10.2.1 *(cài `qemu-system-riscv`)* | 17.1 | 3.14.4 | TODO | PASS sau khi cài QEMU |
| laptop-Hoàng | Hoàng | Ubuntu 24.04.3 LTS x86_64 | f780d785 (project a0cfa2e) | 13.2.0 (unknown-elf) | 8.2.2 | THIẾU gdb-multiarch | 3.12.3 | 23/10/2026 | **PASS** (log local) |
| laptop-Lợi | Lợi | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

## 2. Cách lấy thông tin

```bash
git rev-parse --short HEAD      # project commit
cat .xv6-commit                 # xv6 pin
make env-check                  # in toàn bộ version + build + boot smoke
```

Copy đúng các dòng `[ OK ]` từ output `make env-check` (gcc, QEMU, gdb,
python). Nếu máy thiếu gì, ghi `THIẾU` + lý do.

## 3. Quy tắc tái lập

1. Clone repo, checkout **đúng commit** trong bảng; `git status` phải sạch khi đo.
2. Cài toolchain: `sudo bash scripts/setup-env.sh` (Ubuntu 24.04/26.04).
3. `make env-check` phải PASS trước khi chạy baseline/test.
4. Ghi lại version + ngày + người chạy vào bảng trên; commit ngay.
5. Khi so sánh baseline giữa các máy: chỉ so **cùng commit**; nêu rõ khác Biệt
   OS/QEMU; không trộn số liệu giữa 24.04 và 26.04 khi kết luận.
6. Baseline của từng máy lưu riêng trong `results/baseline/<timestamp>/` —
   không ghi đè lần chạy của máy khác.


## 4. Bằng chứng máy Hoàng ngày 23/10/2026

- Repo làm việc: `/home/ubuntu/2026.1/HDH/Asynchronous-virtio-blk-and-IO-Schedulers`.
- Project hash: `a0cfa2e942fd7cf27040ec404b002e5a25c691d9`.
- Xv6 pin: `f780d7850765d74cbdcd1fff4b822d8829f7c9bd`, chưa xác nhận tag GV.
- `bash scripts/check-env.sh`: exit 0, build + boot CPUS=1 PASS.
- `python3 scripts/check-week01-hoang.py --results-dir results/local/hoang-week01-20261023`: build PASS; 4/4 smoke read/write và reboot CPUS=1/4 PASS.
- `make test-fast TEST_ARGS='--results-dir results/local/hoang-week01-20261023/stock-fast'`: 2/2 PASS, CPUS=1/3 theo case hiện có.
- Log/metadata: `results/local/hoang-week01-20261023/`. Đây là thư mục gitignored; phải sao lưu riêng khi chia sẻ bằng chứng.
- GCC thực tế là riscv64-unknown-elf-gcc 13.2.0, được ghi trong checks.json; không suy từ trường riscv_gcc trống của stock runner (runner hiện chỉ hỏi tên linux-gnu).
- Cảnh báo env-check: thiếu gdb-multiarch và clang-format. Không ngăn build/boot; chưa thực hiện GDB trace hoặc chạy make fmt.
- Full usertests/grind, stress 30 phút và đo max_inflight trên máy này: NOT RUN trong phiên. Baseline đã commit của máy dev không phải số đo mới.
- Kernel/user/mkfs/Makefile/mk không đổi; chưa commit theo yêu cầu.

Tham khảo [hướng dẫn của Hoàng](hoang.md) và [phân tích I/O](io-path.md).

Bản log để commit và review trên GitHub: [results/week01/hoang-2026-10-23](../../results/week01/hoang-2026-10-23/README.md). Đây là bản sao của kết quả ở trên, không phải số đo mới.
