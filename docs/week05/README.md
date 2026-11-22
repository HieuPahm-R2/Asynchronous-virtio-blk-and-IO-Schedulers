# Tuần 5 — Hồ sơ tích hợp và nghiệm thu

Thư mục này tổng hợp công việc tuần 5 (16–22/11/2026) của Hiếu, Lợi và Hoàng. Phần của Hoàng bổ sung kết quả W5-H02 (PTO-45) trên `f5a1c04`, nhận xét thiết kế DMA và báo cáo cá nhân để nhóm tổng hợp W5-G04.

## 1. Tài liệu

| File | Card | Nội dung | Trạng thái |
| :--- | :---: | :--- | :---: |
| [`status.md`](status.md) | **W5-G01** | Rà trạng thái sau snapshot 19/11; bảng task/owner/SHA/evidence/blocker; **chốt candidate `f5130bb`** cho máy hai | ✅ |
| [`second-machine.md`](second-machine.md) | **W5-H01** | Kết quả chạy candidate trên host thứ hai (`DESKTOP-RL9K1ML`, khác host Hoàng): policy/switch CPU1/4, oracle + mutant, FCFS regression, repo checks | ✅ PASS (xem evidence) |
| [`integration.md`](integration.md) | **W5-G02** | Tích hợp tuần 4 vào `main`: merge PR #11 (Hoàng) lên nhánh Hiếu/PR #13 rồi vào main; SHA mới; phạm vi tái kiểm; smoke sau merge | ✅ |
| [`merge-owner-cancel.md`](merge-owner-cancel.md) | **W5-I01** | Chốt thiết kế merge READ + owner/cancel: contract command/child, tuổi/seq khi merge, error fan-out, cancel giữa dải, counters, ngân sách, test M1–M10 + mutant N1–N4, checklist tuần 6 | ✅ thiết kế; code **chưa**; có ghi chú review DMA của Hoàng bên dưới |
| [`demo.md`](demo.md) | **W5-G03** | Runbook + transcript demo 10 phút (ba policy, switch có tải, checksum, drain snapshot); trạng thái câu hỏi GV | ✅ runbook/transcript; phản hồi GV **PENDING/không có nguồn** |
| [`../week04/merge-lifecycle-design.md`](../week04/merge-lifecycle-design.md) | W4-I02 | Thiết kế gốc tuần 4 được W5-I01 review/chốt | ✅ |
| [`report-hoang.md`](report-hoang.md) | **W5-H02 / PTO-45** | Báo cáo cá nhân, ma trận hai máy và kết quả hồi quy sau tích hợp trên `f5a1c04` | **PASS** |
| [`hoang-dma-review.md`](hoang-dma-review.md) | **W5-G02 / W5-I01** | Rà driver/IRQ và góp ý về DMA, vòng đời buffer và completion cho tuần 6 | Đã ghi nhận xét kỹ thuật |

## 2. Script và evidence mới

| Hạng mục | Vị trí |
| :--- | :--- |
| Harness máy hai (mới) | [`scripts/verify-second-machine.py`](../../scripts/verify-second-machine.py) |
| Evidence máy hai | `results/week05/second-machine/<host>-<stamp>/` — `second-machine.json`, `summary.md`, `logs/`, `real-and-switch/`, `independent-oracle/`, `fcfs-regression/` |
| Evidence smoke sau merge | `results/week05/post-merge/` |
| Evidence H02 trên `f5a1c04` | [Log và metadata của Hoàng](../../results/week05/hoang-final-acceptance/) |
| Evidence tuần 4 kế thừa | `results/week04/hoang-20261116/acceptance-d39ea8c/`; `results/week04/policy-mock/…`; `results/week04/oracle-hieu/…` |

## 3. Revision

- Candidate chốt cho máy hai: **`f5130bb9898c4154c3e761e2c85f3038f3a02a86`**
  (`week4/hieu-contract-oracle`, PR #13 = Hiếu + Lợi + Hoàng).
- Code đã kiểm trên máy Hoàng: `d39ea8c` (docs head `e29e824`).
- `main` trước tích hợp: `544673d` (PR #12 = Lợi + Hiếu).
- `main` sau merge local: **`efe2849`** (merge candidate `f5130bb`; xem
  [`integration.md`](integration.md)). Các commit tuần 5 (docs/evidence/harness)
  nằm **sau** merge commit và không đổi code; main remote bị branch protection
  (phải qua PR), nên phần tuần 5 được đẩy bằng nhánh
  **`week5/loi-hieu-integration`** + **PR #14** (xem
  [`integration.md`](integration.md) §2.2).

## 4. Kết quả ngắn

| Hạng mục | Kết quả |
| :--- | :---: |
| H01 máy hai: policy/switch READ thật CPU1/4 + negative + production restore | **PASS** (negative EXPECTED_FAIL) |
| H01 máy hai: oracle độc lập + 6 mutant | **PASS** (mutant EXPECTED_FAIL) |
| H01 máy hai: regression FCFS 20 boot + mock + negative | **PASS** |
| H01: `check_text.py` / `git diff --check` | **PASS** |
| G02 tích hợp tuần 4 vào main | **PASS** — main `efe2849`; diff code rỗng so candidate; post-merge real-policy CPU1/4 + production restore PASS |
| H02 sau tích hợp | **PASS** trên `f5a1c04`: 10 lượt stress, 20 lượt FCFS và 6/6 ca production |
| W5-G04 | Có báo cáo cá nhân của Hoàng để Lợi tổng hợp báo cáo nhóm |

## 5. Giới hạn (đọc trước khi nghiệm thu)

- Máy hai ở đây là host **DESKTOP-RL9K1ML (WSL2 Ubuntu 24.04, `riscv64-linux-gnu-`,
  QEMU 8.2.2)** — khác host Hoàng (`nguyen-van-hoang-20233413`,
  `riscv64-unknown-elf-`); CPU1/4 trên cùng host không được tính là hai máy.
- QEMU virtio-blk không chứng minh seek/latency vật lý; tick ≈ 100 ms nên
  `0 tick` là dưới 1 tick, không phải 0 ms; 4.800 READ không phải 4.800 test độc lập.
- Merge/owner/cancel **chưa code** — chỉ thiết kế; prototype 2 block DEFERRED.
- Không có phản hồi GV/Jira trong phiên này (PENDING/NOT VERIFIED); không sửa Jira.
- [Ghi chú review kỹ thuật của Hoàng](hoang-dma-review.md) đã có. Phê duyệt PR chính thức do reviewer của nhóm xác nhận.
