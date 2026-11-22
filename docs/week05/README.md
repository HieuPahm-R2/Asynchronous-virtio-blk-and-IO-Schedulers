# Tuần 5 — Hồ sơ phần việc Hiếu + Lợi (W5-G01, H01, G02, I01, G03)

Thư mục này chứa đầu ra tuần 5 (16–22/11/2026) cho các card do **Hiếu** và **Lợi**
chủ trì, hoàn thiện trên `main` sau khi pull candidate tuần 4. Theo yêu cầu phạm vi:

- **Bỏ qua** các bước review thuộc Hoàng; không ký thay. Các chỗ cần chữ ký ghi
  **PENDING** rõ ràng.
- **Không làm W5-G04** (báo cáo/đồng bộ hồ sơ nhóm).
- W5-H02 (nghiệm thu sau tích hợp, chủ trì Hoàng) **NOT RUN** — ngoài phạm vi yêu cầu.
- Prototype merge READ 2 block: **DEFERRED** (điều kiện G02/H02 đạt chưa thoả).

## 1. Tài liệu

| File | Card | Nội dung | Trạng thái |
| :--- | :---: | :--- | :---: |
| [`status.md`](status.md) | **W5-G01** | Rà trạng thái sau snapshot 19/11; bảng task/owner/SHA/evidence/blocker; **chốt candidate `f5130bb`** cho máy hai | ✅ |
| [`second-machine.md`](second-machine.md) | **W5-H01** | Kết quả chạy candidate trên host thứ hai (`DESKTOP-RL9K1ML`, khác host Hoàng): policy/switch CPU1/4, oracle + mutant, FCFS regression, repo checks | ✅ PASS (xem evidence) |
| [`integration.md`](integration.md) | **W5-G02** | Tích hợp tuần 4 vào `main`: merge PR #11 (Hoàng) lên nhánh Hiếu/PR #13 rồi vào main; SHA mới; phạm vi tái kiểm; smoke sau merge | ✅ |
| [`merge-owner-cancel.md`](merge-owner-cancel.md) | **W5-I01** | Chốt thiết kế merge READ + owner/cancel: contract command/child, tuổi/seq khi merge, error fan-out, cancel giữa dải, counters, ngân sách, test M1–M10 + mutant N1–N4, checklist tuần 6 | ✅ thiết kế; code **chưa**; review Hoàng **PENDING** |
| [`demo.md`](demo.md) | **W5-G03** | Runbook + transcript demo 10 phút (ba policy, switch có tải, checksum, drain snapshot); trạng thái câu hỏi GV | ✅ runbook/transcript; phản hồi GV **PENDING/không có nguồn** |
| [`../week04/merge-lifecycle-design.md`](../week04/merge-lifecycle-design.md) | W4-I02 | Thiết kế gốc tuần 4 được W5-I01 review/chốt | ✅ |

## 2. Script và evidence mới

| Hạng mục | Vị trí |
| :--- | :--- |
| Harness máy hai (mới) | [`scripts/verify-second-machine.py`](../../scripts/verify-second-machine.py) |
| Evidence máy hai | `results/week05/second-machine/<host>-<stamp>/` — `second-machine.json`, `summary.md`, `logs/`, `real-and-switch/`, `independent-oracle/`, `fcfs-regression/` |
| Evidence smoke sau merge | `results/week05/post-merge/` |
| Evidence tuần 4 kế thừa | `results/week04/hoang-20261116/acceptance-d39ea8c/`; `results/week04/policy-mock/…`; `results/week04/oracle-hieu/…` |

## 3. Revision

- Candidate chốt cho máy hai: **`f5130bb9898c4154c3e761e2c85f3038f3a02a86`**
  (`week4/hieu-contract-oracle`, PR #13 = Hiếu + Lợi + Hoàng).
- Code đã kiểm trên máy Hoàng: `d39ea8c` (docs head `e29e824`).
- `main` trước tích hợp: `544673d` (PR #12 = Lợi + Hiếu).
- `main` sau tích hợp: **`efe2849`** (merge candidate `f5130bb`; xem
  [`integration.md`](integration.md)).

## 4. Kết quả ngắn

| Hạng mục | Kết quả |
| :--- | :---: |
| H01 máy hai: policy/switch READ thật CPU1/4 + negative + production restore | **PASS** (negative EXPECTED_FAIL) |
| H01 máy hai: oracle độc lập + 6 mutant | **PASS** (mutant EXPECTED_FAIL) |
| H01 máy hai: regression FCFS 20 boot + mock + negative | **PASS** |
| H01: `check_text.py` / `git diff --check` | **PASS** |
| G02 tích hợp tuần 4 vào main | **PASS** — main `efe2849`; diff code rỗng so candidate; post-merge real-policy CPU1/4 + production restore PASS |
| H02 sau tích hợp | **NOT RUN** (ngoài phạm vi; cần chạy trước nghiệm thu cuối) |
| W5-G04 | **KHÔNG LÀM** theo yêu cầu |

## 5. Giới hạn (đọc trước khi nghiệm thu)

- Máy hai ở đây là host **DESKTOP-RL9K1ML (WSL2 Ubuntu 24.04, `riscv64-linux-gnu-`,
  QEMU 8.2.2)** — khác host Hoàng (`nguyen-van-hoang-20233413`,
  `riscv64-unknown-elf-`); CPU1/4 trên cùng host không được tính là hai máy.
- QEMU virtio-blk không chứng minh seek/latency vật lý; tick ≈ 100 ms nên
  `0 tick` là dưới 1 tick, không phải 0 ms; 4.800 READ không phải 4.800 test độc lập.
- Merge/owner/cancel **chưa code** — chỉ thiết kế; prototype 2 block DEFERRED.
- Không có phản hồi GV/Jira trong phiên này (PENDING/NOT VERIFIED); không sửa Jira.
- Review chéo của Hoàng cho phần Hiếu/Lợi **bỏ qua theo yêu cầu**; không tự ký thay.
