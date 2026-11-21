# Tuần 4 - hồ sơ nhóm, cập nhật phần Hoàng ngày 16/11/2026

- [Báo cáo Hoàng](report-hoang.md) / [PDF](report-hoang.pdf)
- [Nghiệm thu local và evidence](acceptance-hoang.md)
- [Lệnh tái lập](hoang-runbook.md) / [Review driver/API](review-hoang.md)

Code candidate `d39ea8c` đã kiểm real policy/switch, stress 10 boot,
FCFS20boot và production6case. **Máy thứ hai và review chéo còn thiếu**;
không coi toàn bộ PTO-36/37 đã Done. Phần bên dưới là snapshot hồ sơ Hiếu ngày 15/11.

---

# Tuần 4 — Hồ sơ phần việc của Hiếu (W4-G01, W4-I01, W4-I02)

Thư mục này chứa đầu ra tuần 4 do **Phạm Trung Hiếu (20233402)** thực hiện theo kế
hoạch nhóm tuần 4 (09–15/11/2026), nhánh `week4/hieu-contract-oracle`, base
`origin/main` **`5191ed8`** + nhánh tích hợp deadline/switch của Lợi
(`week4/loi-deadline-switch`).

> **Đọc nhanh:** [`report-hieu.md`](report-hieu.md) — báo cáo hoàn thiện, dễ hiểu.
> **Quy tắc/contract:** [`interface.md`](interface.md).
> **Số liệu/snapshot:** [`measurement.md`](measurement.md).
> **Bằng chứng:** [`evidence-index.md`](evidence-index.md).
> **Thiết kế tuần 5:** [`merge-lifecycle-design.md`](merge-lifecycle-design.md).

## 1. Tài liệu

| File | Card | Nội dung | Trạng thái |
| :--- | :---: | :--- | :---: |
| [`interface.md`](interface.md) | **W4-G01** | Contract tuần 4 D21–D27: deadline, runtime switch, snapshot/kế toán, đo lường, evidence, merge scope; ma trận test; câu hỏi GV | ✅ soạn; review Hoàng/Lợi **PENDING** |
| [`measurement.md`](measurement.md) | **W4-I01** | Schema snapshot một khoá, phân biệt counter/gauge, công thức latency, kết quả mẫu + giới hạn tick | ✅ |
| [`evidence-index.md`](evidence-index.md) | **W4-G01** | Kiểm kê evidence E1–E11 (revision/máy/lệnh/trạng thái) + 8 hạng mục **NOT RUN** | ✅ |
| [`merge-lifecycle-design.md`](merge-lifecycle-design.md) | **W4-I02** | Thiết kế merge READ ≤4 block/lệnh, bounce buffer, master/child, fan-out, owner/cancel/exit, test M1–M10 + mutant N1–N4 | ✅ thiết kế; **DEFERRED**, chưa code |
| [`report-hieu.md`](report-hieu.md) | **G01/I01/I02 + G03** | Báo cáo hoàn thiện, dễ hiểu: việc đã làm, kết quả PASS/EXPECTED_FAIL/NOT RUN, giới hạn, cách tái lập, bàn giao | ✅ |

## 2. Code và test Hiếu thêm trong tuần 4

| File | Nội dung |
| :--- | :--- |
| `kernel/io_request.h`, `kernel/io_request.c` | `struct io_snapshot`/`io_latency_stats`; `io_get_snapshot()`, `io_snapshot_locked()`, `io_get_stats_locked()`, latency aggregates |
| `kernel/virtio_disk.c` | `virtio_disk_get_stats_locked()` để snapshot không acquire lồng |
| `kernel/io_queue_test.c` | 12 fixture độc lập `IOQI01` + in trace/SW/SNAP + kiểm bất biến D23 |
| `kernel/io_hw_test.c` | In `IO-SNAP` trên READ thật |
| `tests/cases/ioq_w4_model.py` | Mô hình contract độc lập (D21/D22/D23) |
| `tests/cases/ioq_deadline.py`, `tests/cases/ioq_policy_switch.py` | Hai oracle độc lập |
| `tests/mutants/i01-m1-expired-latest.patch`, `i01-m2-noop-epoch.patch`, `i01-m3-keep-batch.patch` | Negative control I01 |
| `scripts/check-week04-oracle-hieu.py` | Harness một lệnh: mock CPU1/4 + mutant + READ thật + production restore + repo checks |

## 3. Revision và môi trường

- Base: `origin/main` `5191ed8beda658120bf08667b87657fa45ed1861`; nhánh tích hợp
  deadline/switch `0dc296e`.
- Code I01: **`360b4df`**; evidence I01: **`4fa4de9`**.
- Pin xv6: `f780d7850765d74cbdcd1fff4b822d8829f7c9bd`.
- Kiểm chứng trên WSL2 Ubuntu 24.04 (`DESKTOP-RL9K1ML`), `riscv64-linux-gnu-gcc`
  13.3.0, QEMU 8.2.2, GNU Make 4.3, Python 3.12.3.

## 4. Kết quả đã chạy

| Hạng mục | Kết quả | Đường dẫn |
| :--- | :---: | :--- |
| Oracle I01 độc lập (deadline + switch + snapshot), mock CPU1/4 | **PASS** | [`results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/`](../../results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/summary.md) |
| 6 mutant deadline/switch (gồm 2 mutant bắt buộc) | **EXPECTED_FAIL** 6/6 | cùng thư mục |
| READ thật FCFS cơ bản + `IO-SNAP` timing mẫu | **PASS** (1 boot CPU1) | `hw-cpus1-snap.log` |
| Production restore, hook test vắng, `check_text`/`git diff --check` | **PASS** | `meta.json` |
| Deadline/switch/SCAN mock của L01/L02 (kế thừa, chạy lại) | **PASS** | [`results/week04/policy-mock/…`](../../results/week04/policy-mock/haree-20261115-035243/summary.md) |
| SCAN/deadline READ thật, stress 10 boot, máy hai, final regression | **NOT RUN** | xem [`evidence-index.md`](evidence-index.md) §4 |

## 5. Giới hạn (đọc trước khi nghiệm thu)

- Đây là nhánh cá nhân của Hiếu: **chưa** phải candidate cuối của nhóm; SCAN/deadline
  READ thật 10 boot, stress switch, máy thứ hai và final regression thuộc H01/H02/G02.
- Runtime switch mới ở mức **kernel control**, chưa có syscall user (đúng phạm vi).
- Merge READ và owner/cancel **chỉ thiết kế**, chưa code/test.
- Tick 100 ms quá thô để kết luận latency; mẫu `0` là **dưới 1 tick**, không phải
  0 ms.
- Review chéo Hoàng/Lợi trên cùng revision: **PENDING**; không có phê duyệt nào của
  GV trong tài liệu này (PTO-7/Q1–Q8 **PENDING**).

## 6. Lệnh tái lập

```bash
git switch week4/hieu-contract-oracle
TOOLPREFIX=riscv64-linux-gnu- python3 scripts/check-week04-oracle-hieu.py
TOOLPREFIX=riscv64-linux-gnu- python3 scripts/check-week04-policy.py
python3 scripts/check_text.py && git diff --check
```
