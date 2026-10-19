# Baseline stock xv6

Baseline = số liệu của **xv6-riscv gốc chưa sửa kernel**, dùng để so sánh với
bản async/scheduler sau này. Chỉ có giá trị khi build từ đúng pin và không
dirty source.

## Giao thức

1. Pin xv6: xem `.xv6-commit` (hiện là `f780d785…`, tạm chờ tag giảng viên).
2. Build sạch: `make clean && make -j$(nproc) kernel/kernel fs.img`.
3. Chạy trên QEMU TCG (WSL2 không KVM), đúng command line của Makefile:
   `-machine virt -bios none -kernel kernel/kernel -m 128M -smp CPUS -nographic`
   `-global virtio-mmio.force-legacy=false -drive file=fs.img,... -device virtio-blk-device,...`.
4. Mỗi cấu hình CPUS=1 và CPUS=4:
   - boot + `echo BOOT_OK` (log serial),
   - `usertests -q` (mong đợi `ALL TESTS PASSED`, không có `FAILED`),
   - `grind` trong **60 giây** (kill chủ động, ghi rõ thời lượng; FAIL nếu panic).
5. Lưu `meta.json` + `summary.md` + serial log từng case; commit thư mục
   `results/baseline/<timestamp>/`.
6. Mỗi điểm đo muốn so sánh phải lặp **≥ 5 lần** — với baseline tuần 1 mới chạy
   1 lượt/cấu hình (bằng chứng "chạy được", chưa phải số liệu benchmark).

Chạy lại:

```bash
make baseline
# hoặc chọn tag khác:
BASELINE_TAG=baseline bash scripts/baseline.sh
```

## Kết quả baseline — tuần 1

Lần chạy: **`results/baseline/2026-10-19_222935/`**

- Commit dự án: `9f5b784` (tree sạch — `dirty: false` trong `meta.json`)
- xv6 pin: `f780d785` (2026-10-15)
- Môi trường: WSL2 Ubuntu 24.04, host 6 CPU / 8 GB, QEMU 8.2.2 (TCG, không KVM)
- Lệnh: `make baseline` (build sạch + tag `baseline`) — tổng **~19,4 phút**
- Kết quả: **6 PASS / 0 FAIL**

| Case | CPUS | Kết quả | Thời gian (s) |
| --- | ---: | --- | ---: |
| `boot-smoke` | 1 | PASS | 3,50 |
| `shell-fs-cpus3` | 3 | PASS | 4,27 |
| `usertests-quick-cpus1` | 1 | PASS | 536,77 |
| `usertests-quick-cpus4` | 4 | PASS | 492,98 |
| `grind-smoke-cpus1` | 1 | PASS | 63,00 |
| `grind-smoke-cpus4` | 4 | PASS | 63,27 |

Bằng chứng: [`results/baseline/2026-10-19_222935/`](../results/baseline/2026-10-19_222935/)
(`meta.json`, `summary.md`, `build.log`, `logs/*.log`).

> Bảng trên do `make baseline` sinh ra tại `results/baseline/<timestamp>/summary.md`;
> mục này được cập nhật tay sau khi chạy. Ghi kèm commit + ngày chạy.
> Nếu pin/commit thay đổi (tag giảng viên), **chạy lại baseline** và thêm lần chạy mới
> thay vì sửa số cũ.

## Diễn giải & giới hạn

- QEMU **TCG** trên WSL2: chậm hơn KVM, số liệu tuyệt đối không dùng để so với
  máy khác. Chỉ so sánh giữa các lần đo **cùng máy, cùng command line**.
- `usertests -q` mất **~8–9 phút/cấu hình CPU** trên máy dev này (TCG), nên
  `make test` (gồm usertests CPUS=1/4) mất **~18 phút**. Dùng `make test-fast`
  (~8 giây) trong lúc code hằng ngày, `make test` trước khi commit lớn/PR.
- `usertests -q` kiểm tra tính đúng và free pages (in `FAILED -- lost some free
  pages` nếu rò); đây là regression bắt buộc trước/sau mọi thay đổi.
- `grind` chạy vô hạn; 60 giây chỉ là smoke stress, **không** phải bằng chứng
  R09 (R09 cần ≥ 30 phút, có seed/cấu hình/checksum và kết luận).
- Baseline **chưa đo được** `max_inflight` thực tế của stock: cần spike thêm
  counter (xem `docs/architecture.md` mục 1.4). Đây là việc tuần 1–2.
- Số request INFLIGHT tối đa suy ra từ code: `floor(NUM/3) = 2` chain
  (`NUM = 8` descriptor, 3 descriptor/chain); caller thứ 3 ngủ chờ descriptor.
  Con số **đo được** phải lấy từ counter, không suy đoán.

## Bằng chứng lưu ở đâu

```
results/baseline/<timestamp>/
├── build.log          # log build sạch
├── meta.json          # commit, xv6 pin, toolchain, host, từng case
├── summary.md         # bảng PASS/FAIL + thời gian
├── NOTES.md           # ghi chú lần chạy (do make baseline thêm)
└── logs/<case>.log    # serial console đầy đủ từng case
```
