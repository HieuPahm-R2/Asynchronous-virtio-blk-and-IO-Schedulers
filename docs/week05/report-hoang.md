# Báo cáo cá nhân tuần 5 | Nguyễn Văn Hoàng

**ET4290 · Đề tài 26128 · MSSV 20233413 · 16-22/11/2026.** Thực hiện nghiệm thu ngày 22/11, giờ Việt Nam.

## Phạm vi và kết luận

[PTO-45](https://phamvanthang786.atlassian.net/browse/PTO-45) là card Hoàng phụ trách ở Sprint 5. Nội dung theo plan Drive là W5-H02, nghiệm thu bản ghép cuối. Đầu ra cá nhân còn gồm review kỹ thuật driver/IRQ (W5-G02), nhận xét thiết kế DMA/lifetime (W5-I01), trích log demo (W5-G03) và bản bàn giao để Lợi tổng hợp (W5-G04).

**Kết quả W5-H02: PASS trên source sạch `f5a1c04ebd20c6e69ff124b2c1f13301f87b1d68`.** PR #14 đã vào `main` lúc 09:25 ngày 22/11. `f5130bb` là candidate trước merge. So sánh hai SHA cho thấy các file build, kernel, user, test và ba script kiểm thử chính trùng nhau. Tuần 5 bổ sung tài liệu, evidence và script điều phối máy hai.

## Ma trận kết quả

| Suite trên máy Hoàng | Kết quả và phạm vi | Evidence thư mục H02 |
| --- | --- | --- |
| Real policy/switch | CPU1/4 đạt 20 ca, 140 READ fixture. Stress 10/10 boot, 4.800 READ, 60 switch lúc Q>0 và I=2. Production restore smoke đạt. 2 ca dữ liệu tiêm lỗi bị bắt. | `real/` |
| Oracle độc lập | Mock CPU1/4 và READ thật CPU1 với snapshot đều PASS. 6 mutant EXPECTED_FAIL (expiry, epoch, batch, EAGAIN và giữ tuổi). | `oracle/` |
| Hồi quy FCFS | 20/20 boot real-virtio, 4/4 pool/queue mock, 1 corrupt fixture EXPECTED_FAIL. | `fcfs/` |
| Production | 6/6 PASS: boot-smoke CPU1, shell-fs CPU3, usertests -q CPU1/4 và grind 60 giây CPU1/4. | `production/` |
| Kiểm tra repo | check-text, check-mermaid, git diff --check PASS. Git status sạch sau kiểm thử. | `repo-checks.log` |

Tất cả 10 lượt stress đều có `submitted=completed=released=480`, `data_errors=errors=0`, `free_req=16`, `free_desc=8`, Q/I/D/X về 0. 60 lần switch phủ 6 chiều lặp qua 10 boot. Một mẫu CPU4 có `ovf=515`, `samples=480`, `zero_total=480`. Trace vòng chỉ phục vụ quan sát, kiểm stress dựa vào oracle, counters và checksum. Đơn vị tick được ghi trong log, 0 tick nghĩa là phép đo ở dưới độ phân giải. Kết quả trên QEMU virtio-blk không dùng để suy ra seek vật lý hay stress 30 phút.

## Đối chiếu hai máy

| Nguồn | SHA | Phạm vi đã xác nhận |
| --- | --- | --- |
| Lượt H02 của Hoàng, log và metadata đi kèm | `f5a1c04` | Real/switch, oracle, FCFS và production. Toolchain `riscv64-unknown-elf-gcc` 13.2.0 / QEMU 8.2.2. |
| Ảnh thư mục Drive `week 05/image`, máy Hiếu | `f5a1c04` | Ảnh summary cho thấy source sạch, host khác máy Hoàng, 13+3+24 PASS và 9 EXPECTED_FAIL. GCC 15.2.0 / QEMU 10.2.1. Phạm vi ảnh là real/switch, oracle và FCFS. Lượt production đủ 6 ca của máy Hiếu chưa có minh chứng trong bộ ảnh. |
| Raw log H01 của nhóm | `f5130bb` | 40 PASS, 9 EXPECTED_FAIL trên DESKTOP-RL9K1ML, SHA trước merge. Hồ sơ lịch sử của lượt H01 được lưu riêng ở `results/week05/second-machine/`. |

Ảnh Drive có ba tệp. Ảnh lệnh real cho thấy lần gõ đầu lỗi cú pháp rồi lệnh sửa chạy PASS CPU1/4. Ảnh 11:08:27 có SHA, sạch đầu/cuối, môi trường và bảng suite. Ảnh 11:09:12 có snippet JSON và log stress. PDF dùng các ảnh này làm minh chứng bổ sung. Log của lượt H02 là nguồn gốc cho kết luận máy Hoàng.

## Review và bàn giao

- G02: đã rà đường submit, EAGAIN, IRQ reap, lifecycle buffer, lock/wakeup và release. Chi tiết ở [hoang-dma-review.md](hoang-dma-review.md). Review kỹ thuật được ghi thành tài liệu. Phê duyệt GitHub chính thức thuộc reviewer nhóm.
- I01: đề nghị cố định mapping `(id, gen, offset)` tới completion, fan-out lỗi tới mọi child còn sống, tránh đếm đôi cancel trong D23, giữ lock order khi exit. PTO-41 thuộc Sprint 6. Prototype merge 2 block giữ DEFERRED do phần thử chung cần phối hợp queue, DMA và oracle.
- G03: dùng `real/real-policy-cpus1.log` để trình bày ba policy và ca expiry. Dùng `real/switch-stress-01-cpus4.log` để chỉ sáu chiều đổi, checksum và drain. Đây là đầu vào demo và hồ sơ tổng hợp, chưa xác nhận đã trình bày với GV.
- G04: báo cáo này là phần cá nhân của Hoàng để Lợi tổng hợp PTO-47. Jira PTO-45 hiển thị To Do khi đối chiếu. Báo cáo cung cấp kết quả kiểm thử để nhóm cập nhật card. Giờ công plan là ước lượng, không điền giờ thực tế từ plan.
- SonarCloud PR #14 báo Failure khi xem kết quả. Workflow CI hiện có trong repo ở dạng comment. Kiểm thử H02 là kết quả chạy local QEMU. Các kiểm tra đó được theo dõi như hai trạng thái riêng.

## Tái lập trên source sạch

Chạy tuần tự từ checkout `f5a1c04` với Python 3, GNU Make, QEMU RISC-V và toolchain được repo hỗ trợ. Đặt `OUT` là thư mục mới nằm ngoài checkout để trường `dirty` phản ánh đúng source được chạy.

```bash
OUT=/tmp/et4290-week5-h02
mkdir "$OUT"
git rev-parse HEAD
git status --porcelain
python3 scripts/check-week04-hoang.py --mode all --repeat 5 --cpus 1 4 --results-dir "$OUT/real"
python3 scripts/check-week04-oracle-hieu.py --results-dir "$OUT/oracle"
python3 scripts/check-week02-hoang.py --repeat 10 --results-dir "$OUT/fcfs"
python3 tests/runner.py --tag baseline --results-dir "$OUT/production"
make check-text check-mermaid
git diff --check
git status --porcelain
```

- [Log và metadata H02](../../results/week05/hoang-final-acceptance/)
- [Bản tích hợp PR #14](https://github.com/HieuPahm-R2/Asynchronous-virtio-blk-and-IO-Schedulers/pull/14)
- [Plan đang dùng trên Drive](https://drive.google.com/drive/u/0/folders/10pVdPhDCnVd2Xq7_ptWBReSXJ0YXOdm3)
- [Thư mục ảnh minh chứng](https://drive.google.com/drive/u/0/folders/1kk1UKV7DuWlIOoQmDxPvOrlxzYXfxhic)
