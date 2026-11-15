# Báo cáo tuần 4 — Phạm Trung Hiếu (20233402)

**Đề tài 26128 · ET4290 · Asynchronous virtio-blk và I/O schedulers trên xv6-riscv**
Kỳ: **09–15/11/2026**. Nhánh: `week4/hieu-contract-oracle`. Chốt báo cáo: **15/11/2026**.

Báo cáo này gồm hai phần: **những việc Hiếu đã hoàn thiện** (W4-G01, W4-I01, W4-I02
và phần G03 của Hiếu) và **cách kiểm chứng chúng**. Mọi kết quả đều dẫn được tới
commit/log trong repo; phần chưa làm được ghi rõ **NOT RUN**, không suy diễn thành
đạt.

---

## 1. Tóm tắt nhanh

| Card | Việc Hiếu phụ trách | Đầu ra đã hoàn thiện | Trạng thái |
| :---: | :--- | :--- | :---: |
| **W4-G01** (P0) | Chốt contract deadline/switch + evidence index | [`interface.md`](interface.md) (D21–D27), [`measurement.md`](measurement.md), [`evidence-index.md`](evidence-index.md); khai báo contract trong `kernel/io_request.h` | ✅ **Xong**; review Hoàng/Lợi **PENDING** |
| **W4-I01** (P1) | Oracle độc lập cho deadline/switch + snapshot/counters + timing | Code snapshot một khoá + latency; 1 mô hình contract + 2 oracle Python độc lập; 12 fixture mới `IOQI01`; 3 mutant; harness một lệnh; **log PASS CPU1/4** | ✅ **Xong**, đã chạy PASS |
| **W4-I02** (P2) | Thiết kế merge READ + owner/cancel | [`merge-lifecycle-design.md`](merge-lifecycle-design.md): ≤4 block/lệnh, bounce buffer, master/child, fan-out, cancel/orphan/exit, test checklist | ✅ **Xong thiết kế**; code **chưa** (đúng phạm vi) |
| **W4-G03** (phần Hiếu) | Review số liệu, sửa công thức counter/gauge + link PDF cũ, báo cáo cá nhân | Báo cáo này; đính chính D20 tuần 3; sửa link `report-hieu.pdf` đã bị xoá | ✅ **Xong phần Hiếu** |

**Một câu kết quả:** trên revision code `360b4df`, oracle độc lập của Hiếu **PASS
CPU1 + CPU4**, **6/6 mutant bị bắt** (kể cả 2 mutant bắt buộc của kế hoạch), READ
thật FCFS cơ bản lấy được snapshot/latency, production restore sạch hook — xem
[evidence E6–E9](evidence-index.md).

---

## 2. Điểm xuất phát

- Nhóm đã merge tuần 3 vào `origin/main` tại **`5191ed8`** (PR #8 Hoàng, #9 Hiếu,
  #10 Lợi): có SCAN, toolchain/stress, contract/lifecycle/proposal. Không merge lại.
- Hiếu làm tiếp trên nhánh tích hợp tuần 4 của Lợi
  (**`week4/loi-deadline-switch`**, code deadline + runtime switch), để oracle của
  mình chạy được trên **code thật** thay vì chỉ mô phỏng.
- Nhánh Hiếu: `week4/hieu-contract-oracle`
  - `0dc296e` — kế thừa L01/L02 + evidence Lợi;
  - **`360b4df`** — code/test I01 của Hiếu (commit chính);
  - **`4fa4de9`** — evidence I01 (log/meta/summary).
- Phần Lợi đã có: deadline D21 (expire 50, batch 4), switch D22
  (`io_set_policy()`/`io_queue_set_policy_locked()`), event `SWITCH`, epoch,
  11 ca self-test `IOQDL`, 3 mutant. Phần Hiếu **không làm lại** các phần này; Hiếu
  làm **contract**, **oracle độc lập**, **snapshot/counters**, **thiết kế tiếp nối**.

---

## 3. W4-G01 — Contract tuần 4 và evidence index

### 3.1 Đã làm

1. **Khoá base revision** `5191ed8` + nhánh W4; ghi rõ phần nào đã có code, phần nào
   chỉ thiết kế (owner/cancel), phần nào còn thiếu (SCAN/deadline READ thật, stress
   10 boot, máy hai, final regression) — xem [`interface.md`](interface.md) §2.
2. **Chốt D21 (deadline)** đúng kế hoạch tuần 4 §13: nguồn thời gian `ticks`, tuổi
   wrap-safe int32, expire = **50 tick**, batch = **4**; có expired → expiry sớm
   nhất (hoà theo `seq`); không expired → block thấp nhất, nhưng cứ 4 lần liên tiếp
   thì lấy FIFO cũ nhất; `EAGAIN` không commit gì; không phải EDF.
3. **Chốt D22 (runtime switch)**: enum sai → `-22` không đổi gì; cùng policy →
   no-op không tăng epoch; khác → commit dưới `io_lock`, `epoch+1`, một event
   `SWITCH`; vào SCAN lấy `last_block` của **mọi** policy làm head, dir UP; vào
   DEADLINE reset batch; không đụng queue/tuổi/`INFLIGHT`; switch không tự dispatch.
4. **Chốt D23 (snapshot/kế toán)** và **sửa lỗi trộn counter với gauge**: công thức
   đúng là `S = Q+I+C+E`, `C+E = R+D+X`, `16 = F+Q+I+D+X` (S/C/E/R tích luỹ;
   Q/I/D/X/F hiện tại) — không còn kiểu `submitted = Q+I+D+X`.
5. **Chốt D24 (đo lường)**: 3 khoảng wait/service/total, đơn vị tick, độ phân giải
   ≈100 ms, bắt buộc báo `samples`/`zero_total`/`trace_overflow`; không dựng p99 giả.
6. **Chốt D25/D26/D27**: metadata bắt buộc cho mỗi lượt chạy; fixture stress thật
   (32 block 1968..1999, window 5, 4×120 READ, seed `0x26128003`; negative lật byte
   đầu block `FSSIZE-32`); owner/cancel + merge **chỉ thiết kế**.
7. **Evidence index** liệt kê 11 nhóm bằng chứng E1–E11 (revision, máy, lệnh, trạng
   thái, chứng minh/không chứng minh) + 8 hạng mục **NOT RUN** kèm người xử lý.
8. **Đính chính tài liệu cũ** (phần G03 của Hiếu): sửa công thức counter/gauge trong
   `docs/week03/interface.md` (D20), `lifecycle-review.md` §5.8, `proposal.md` §6;
   sửa link `report-hieu.pdf` đã bị xoá khỏi repo trong `docs/week03/README.md`.
   Tài liệu lịch sử giữ ngày và ghi rõ "đính chính 2026-11-15".

### 3.2 Vì sao cần

Nếu mỗi người dùng một quy tắc khác nhau (Lợi code theo expire 50, Hoàng chạy
harness theo fixture khác, oracle Hiếu tính theo cách hiểu khác) thì kết quả
"PASS" không so sánh được. Contract tuần 4 là **một nguồn sự thật**: cùng công
thức, cùng thông số, cùng định nghĩa evidence.

---

## 4. W4-I01 — Oracle độc lập, snapshot/counters và timing

### 4.1 Vấn đề cần giải

Tuần 3 đã có oracle SCAN. Tuần 4 thêm deadline + đổi policy khi có tải. Nếu chỉ
"thấy chương trình in PASS" thì không chứng minh được thứ tự dispatch **đúng**.
Cần một **oracle độc lập**: tự tính kết quả đúng từ contract rồi so với log, không
lấy log/ code C làm đáp án. Đồng thời cần **snapshot nhất quán** để đọc counters
(rất dễ đọc lệch nếu lấy từ nhiều lần khoá khác nhau).

### 4.2 Đã làm (code)

**(a) Snapshot hợp nhất + latency — `kernel/io_request.[ch]`, `kernel/virtio_disk.c`**

- `struct io_snapshot`: một lần đọc `io_lock` cho **tất cả** — request counters
  (S/C/E/R, Q/I/D/X/F, max_inflight, eagain/stale), queue counters (enqueued,
  dispatched, eagain, boundary, switch, dl_expired, dl_fifo, trace_overflow), policy
  state (policy/epoch/batch/last_block), driver descriptors (free_desc, owner split,
  head_reuse) và latency.
- `struct io_latency_stats`: `wait = t_dispatch - t_enqueue`,
  `service = t_complete - t_dispatch`, `total = t_complete - t_enqueue`, kèm
  `samples`, `*_sum`, `*_max`, `zero_total`; cộng dồn dưới `io_lock` khi request
  terminal; `uint` wrap-safe.
- Helper `io_get_stats_locked()` / `virtio_disk_get_stats_locked()` để
  `io_snapshot_locked()` **không acquire lồng** (đúng cảnh báo của H01/§I01.4).
- Không có `printk/kalloc/sleep` trong IRQ; snapshot copy ra ngoài rồi in.

**(b) Fixture self-test độc lập — `kernel/io_queue_test.c`** (12 ca `IOQI01`; bảng
dưới gộp 3 ca tuổi thành 1 dòng cho gọn)

| Ca | Kiểm điều gì |
| :--- | :--- |
| `i01-dl-age-before` / `-at` / `-after` | tuổi 49 (chưa expired) vs đúng 50 vs 51 (expired) |
| `i01-dl-expired-order` | nhiều expired khác tuổi → expiry sớm nhất thắng |
| `i01-dl-batch-boundary` | 4 lần POSITION rồi FIFO lấy request cũ block 1000 |
| `i01-dl-eagain` | EAGAIN trước/sau candidate không đổi batch/trace/job |
| `i01-dl-wrap` | đồng hồ wrap qua `0xFFFFFFFF` vẫn nhận đúng tuổi 50 |
| `i01-sw-keep-age` | switch không reset tuổi (request cũ vẫn expired) |
| `i01-sw-noop-invalid` | no-op/enum sai không tăng epoch; queue rỗng vẫn switch được |
| `i01-sw-batch-reset` | vào DEADLINE reset batch (nếu không sẽ FIFO sai thứ tự) |
| `i01-sw-scan-head` | vào SCAN lấy `last_block` (FCFS) làm head, dir UP |
| `i01-sw-all6` | đủ **6 chiều** chuyển giữa 3 policy, mỗi lần Q>0 và I>0 |

Kernel chỉ **in** trace/SW/SNAP và kiểm bất biến nội bộ; thứ tự đúng do oracle
Python bên ngoài chấm.

**(c) Oracle độc lập — `tests/cases/`**

- `ioq_w4_model.py`: mô hình contract (D21/D22/D23) viết từ spec, tự chạy lại
  kịch bản fixture, tự tính expected **event, SW record, counters và SNAP**.
- `ioq_deadline.py`: oracle deadline — so `CHK`, chuỗi event D/B/S, `END n`, SNAP.
- `ioq_policy_switch.py`: oracle switch — bản ghi SW (rc/q/i/epoch), đủ 6 chiều,
  ≥1 switch có Q>0 và I>0, SNAP kế toán.
- Cả hai **không import** oracle Lợi, không đọc code C, không lấy trace làm đáp án;
  có `coverage_errors()` tự kiểm fixture có phủ đủ ma trận.

**(d) Negative control — 3 mutant mới của I01**

| Mutant | Lỗi cố ý | Oracle bắt |
| :--- | :--- | :--- |
| `i01-m1-expired-latest` | chọn expired có expiry **muộn** nhất | deadline |
| `i01-m2-noop-epoch` | no-op cùng policy vẫn tăng epoch | switch |
| `i01-m3-keep-batch` | vào DEADLINE không reset batch | switch |

Ngoài ra harness chạy lại 3 mutant của L01/L02 (`dl-m1-no-expired`, `dl-m3-eagain-batch`,
`sw-m2-reset-age`) — đây là 2 mutant **bắt buộc theo card** (bỏ ưu tiên expired;
reset tuổi khi switch) và đều bị **oracle độc lập của Hiếu** bắt.

**(e) Harness một lệnh — `scripts/check-week04-oracle-hieu.py`**

Build `-DIOQ_SELFTEST` → boot **CPU1/4** → chạy oracle I01 + regression SCAN/FCFS/L02
→ 6 mutant `EXPECTED_FAIL` → build `IO_HW_SELFTEST` boot 1 lượt READ thật lấy
`IO-SNAP` → build production + kiểm hook vắng → `check_text.py` + `git diff --check`
→ ghi `results/week04/oracle-hieu/<host>-<stamp>/` (log, `meta.json`, `summary.md`,
`source.patch`, untracked source).

### 4.3 Kết quả chạy (evidence)

Nguồn: [`results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/`](../../results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/summary.md)
— revision `360b4df`, tree sạch, WSL2 Ubuntu 24.04, gcc 13.3.0, QEMU 8.2.2.

| Hạng mục | Kết quả |
| :--- | :---: |
| Oracle I01 mock CPUS=1 | **PASS** |
| Oracle I01 mock CPUS=4 | **PASS** |
| Regression SCAN tuần 3 + FCFS tuần 2 + policy L02 (cùng log) | **PASS** |
| 3 mutant I01 | **EXPECTED_FAIL** 3/3 |
| 3 mutant L01/L02 (gồm 2 mutant bắt buộc) | **EXPECTED_FAIL** 3/3 |
| READ thật FCFS cơ bản CPUS=1 + `IO-SNAP` | **PASS** |
| Production restore, hook test vắng | **PASS** |
| `check_text.py`, `git diff --check` | **PASS** |

**Snapshot của lượt READ thật:** `S=83, C=81, E=2, R=83, Q=I=D=X=0, F=16,
free_desc=8` (2 `ERROR` là **cố ý** của suite hardware để test error-path, không
phải lỗi dữ liệu), `lat_samples=83`, `zero_total=83`, `trace_overflow=19` (trace 64
event không đủ cho lượt dài — dùng counters thay trace, đúng giới hạn đã ghi).

---

## 5. Giải thích dễ hiểu (đọc nhanh)

**“Oracle độc lập” là gì?** Là một chương trình thứ hai, viết từ *luật* (contract),
tự tính ra thứ tự dispatch đúng, rồi so với thứ tự kernel in ra. Nếu cả hai cùng
sai theo một kiểu thì oracle mới không bắt được — vì vậy oracle **không** được lấy
output kernel làm đáp án. Muốn tin oracle, ta cố ý làm hỏng code (mutant): oracle
**phải** báo FAIL. Kết quả: 6/6 mutant bị bắt.

**“Snapshot một khoá” là gì?** Các bộ đếm nằm rải ở request layer, queue, driver.
Nếu đọc từng chỗ một, giữa hai lần đọc có thể có I/O chen vào → số liệu lệch nhau
(ví dụ `submitted` tăng nhưng `completed` chưa kịp). Hàm `io_get_snapshot()` giữ
`io_lock` **một lần** rồi copy tất cả ra, nên các con số thuộc **cùng một thời
điểm**. Đây là lý do phải thêm các helper `*_locked` thay vì gọi các hàm public
(tự lấy khoá) lồng nhau.

**`zero_total = 83` nghĩa là gì?** Đồng hồ chỉ nhảy mỗi **100 ms** (1 tick). Một
READ trên QEMU xong nhanh hơn 100 ms nên “total” đo được là **0 tick** — tức **dưới
1 tick**, không phải “0 ms”. Vì vậy báo cáo ghi rõ `samples=83, zero_total=83` và
**không** kết luận latency = 0. Muốn có phân bố latency cần workload lớn hơn hoặc
tăng độ phân giải (phải review) — ghi vào việc tuần sau.

**Ví dụ một ca deadline (dễ hiểu):** đồng hồ giả = 500, đưa 2 request block 40 và
block 10, tua đồng hồ 49 tick → cả hai chưa “quá hạn 50 tick”, nên policy DEADLINE
chọn **block thấp hơn** (10) trước. Nếu tua đúng 50 tick → cả hai vừa quá hạn, luật
“expired trước, hoà theo thứ tự đến” chọn request đến trước (40) trước. Oracle tự
tính hai kịch bản này và so từng dòng trace.

---

## 6. W4-I02 — Thiết kế merge READ và owner/cancel (chưa code)

Đầu ra: [`merge-lifecycle-design.md`](merge-lifecycle-design.md). Tóm tắt quyết
định thiết kế:

1. **Merge tối đa 4 block = 4096 B** trong **một lệnh thiết bị**; chỉ request đang
   `QUEUED`, cùng device/op, dải block liền kề; hỗ trợ append/prepend; kiểm biên
   capacity **trước** khi nhận; không merge `INFLIGHT`.
2. **Bounce buffer hữu hạn** 4096 B/command (2 command × 4 KiB ≈ 8 KiB BSS, không
   `kalloc`); IRQ copy từng slice 1024 B vào buffer của child rồi mới `DONE` +
   `wakeup`; lỗi thiết bị → **toàn bộ child** `ERROR` (virtio không cho biết partial).
3. **Master/child ownership**: master giữ descriptor + bounce; child giữ handle +
   `data[1024]`; release đúng một lần; cấm free slot/bounce/descriptor khi còn
   `INFLIGHT`.
4. **Cancel chỉ trước submit** (child QUEUED); sau submit trả `EBUSY` (không abort
   được). **Owner/orphan** kế thừa W3-I01 (phương án A: `owner_pid`, cleanup `kexit`,
   orphan auto-free sau completion).
5. **Ảnh hưởng queue/policy**: queue giữ **một entry/command**; tuổi deadline =
   child cũ nhất; vị trí SCAN = block biên theo chiều; trace DISPATCH ghi một event
   cho command (kèm `nblocks`) — là **thay đổi contract** phải chốt trước code.
6. **Test checklist tuần 5**: M1–M10 (merge liền kề/ngược/vượt biên, cancel,
   orphan, done-on-exit, stale, kill waiter, bão hoà slot, lỗi thiết bị) + mutant
   N1–N4 (bỏ fan-out, double free, merge INFLIGHT, sai offset) + checksum từng child.
7. **Trạng thái:** DEFERRED — không code/test trong tuần 4; cần Hoàng review DMA/IRQ
   và Lợi review ordering trước khi bắt đầu.

---

## 7. Bảng tổng hợp PASS / EXPECTED_FAIL / NOT RUN

| Hạng mục | Trạng thái | Bằng chứng |
| :--- | :---: | :--- |
| Contract D21–D27 + evidence index | ✅ **XONG** | [`interface.md`](interface.md), [`evidence-index.md`](evidence-index.md) |
| Snapshot một khoá + latency aggregates | ✅ **CODE + PASS** | `kernel/io_request.c`, E8 |
| Oracle deadline độc lập CPU1/4 | ✅ **PASS** | E6, `policy-cpus1/4.log` |
| Oracle switch độc lập (6 chiều) CPU1/4 | ✅ **PASS** | E6 |
| Snapshot/kế toán (kernel + oracle) | ✅ **PASS** | E6, `IO-SNAP` |
| Mutant bắt buộc (bỏ expired / reset tuổi) | ✅ **EXPECTED_FAIL** | E7 |
| Mutant I01 thêm 3 cái | ✅ **EXPECTED_FAIL** | E7 |
| READ thật FCFS cơ bản + timing mẫu | ✅ **PASS (1 boot CPU1)** | E8 |
| Production restore + hooks vắng | ✅ **PASS** | E9 |
| Merge/owner/cancel | 🟡 **THIẾT KẾ (DEFERRED)** | [`merge-lifecycle-design.md`](merge-lifecycle-design.md) |
| SCAN READ thật CPU1/4 | ⛔ **NOT RUN** | H01 (Hoàng) |
| Deadline READ thật CPU1/4 | ⛔ **NOT RUN** | H01/H02 |
| Stress switch 10 boot (4×120 READ) | ⛔ **NOT RUN** | H02 |
| Máy thứ hai cùng final revision | ⛔ **NOT RUN** | H02 |
| Final regression 6 case production / FCFS 20 boot trên candidate cuối | ⛔ **NOT RUN** | G02 |
| Benchmark ≥5 lần/điểm, stress ≥30 phút | ⛔ **NOT RUN** | tuần 5+ |

---

## 8. Giới hạn — những gì báo cáo này **không** tuyên bố

- **Không** tuyên bố SCAN/deadline đã chạy qua READ thật 10 boot: phần đó là H01/H02,
  chưa có trên nhánh Hiếu. Evidence READ thật ở đây chỉ **1 boot CPU1** để lấy mẫu
  snapshot/timing, **không** thay acceptance G02.
- **Không** tuyên bố runtime switch đã có syscall/user API: mới là **kernel control**
  (`io_set_policy()`), đúng phạm vi tuần 4.
- **Không** tuyên bố merge/owner/cancel đã code: chỉ thiết kế, chưa test.
- **Không** tuyên bố latency/benchmark: tick 100 ms quá thô, mẫu `0` là dưới 1 tick.
- **Không** tuyên bố LOOK hay rubric đã được GV xác nhận; PTO-7/Q1–Q8 vẫn **PENDING**.
- Log tuần 3 chỉ là tham chiếu lịch sử, **không** cộng vào chỉ tiêu tuần 4.
- Review chéo của Hoàng/Lợi trên cùng revision: **PENDING** — báo cáo không ghi Done.

---

## 9. Cách tái lập (một lệnh chính)

Yêu cầu: WSL2 Ubuntu hoặc Ubuntu có `make`, `riscv64-linux-gnu-*` (hoặc
`riscv64-unknown-elf-*`), QEMU ≥ 7.2, `python3`.

```bash
git switch week4/hieu-contract-oracle
git log --oneline -3          # 4fa4de9 / 360b4df / 0dc296e

# Toàn bộ oracle I01 + mutant + READ thật + production restore (~4 phút):
TOOLPREFIX=riscv64-linux-gnu- python3 scripts/check-week04-oracle-hieu.py

# Kết quả: results/week04/oracle-hieu/<host>-<stamp>/{summary.md,meta.json,*.log}
# Chỉ chạy oracle trên một log có sẵn:
python3 tests/cases/ioq_deadline.py      results/week04/oracle-hieu/<...>/policy-cpus1.log
python3 tests/cases/ioq_policy_switch.py results/week04/oracle-hieu/<...>/policy-cpus1.log

# Harness L01/L02 (deadline/switch mock + 6 mutant):
TOOLPREFIX=riscv64-linux-gnu- python3 scripts/check-week04-policy.py

# Kiểm tra tài liệu/repo:
python3 scripts/check_text.py && git diff --check
```

---

## 10. Danh mục file Hiếu tạo/sửa trong tuần 4

| File | Vai trò |
| :--- | :--- |
| [`docs/week04/interface.md`](interface.md) | **G01** contract D21–D27 + ma trận test + câu hỏi GV |
| [`docs/week04/measurement.md`](measurement.md) | **I01** schema snapshot, công thức latency, kết quả mẫu |
| [`docs/week04/evidence-index.md`](evidence-index.md) | **G01** evidence E1–E11 + NOT RUN |
| [`docs/week04/merge-lifecycle-design.md`](merge-lifecycle-design.md) | **I02** thiết kế merge READ + owner/cancel |
| [`docs/week04/report-hieu.md`](report-hieu.md) | Báo cáo này (G03 phần Hiếu) |
| [`kernel/io_request.h`](../../kernel/io_request.h) | Snapshot/latency structs + contract counters + helper `_locked` |
| [`kernel/io_request.c`](../../kernel/io_request.c) | `io_snapshot_locked/get_snapshot`, latency record, refactor stats |
| [`kernel/virtio_disk.c`](../../kernel/virtio_disk.c) | `virtio_disk_get_stats_locked()` |
| [`kernel/io_queue_test.c`](../../kernel/io_queue_test.c) | 12 fixture `IOQI01`, snapshot checks, generic scenario runner |
| [`kernel/io_hw_test.c`](../../kernel/io_hw_test.c) | In `IO-SNAP` sau READ thật (mẫu timing) |
| [`tests/cases/ioq_w4_model.py`](../../tests/cases/ioq_w4_model.py) | Mô hình contract độc lập (D21/D22/D23) |
| [`tests/cases/ioq_deadline.py`](../../tests/cases/ioq_deadline.py) | Oracle deadline độc lập |
| [`tests/cases/ioq_policy_switch.py`](../../tests/cases/ioq_policy_switch.py) | Oracle switch/snapshot độc lập |
| [`tests/mutants/i01-m1-expired-latest.patch`](../../tests/mutants/i01-m1-expired-latest.patch) · [`i01-m2-noop-epoch`](../../tests/mutants/i01-m2-noop-epoch.patch) · [`i01-m3-keep-batch`](../../tests/mutants/i01-m3-keep-batch.patch) | Negative control I01 |
| [`scripts/check-week04-oracle-hieu.py`](../../scripts/check-week04-oracle-hieu.py) | Harness một lệnh cho I01 |
| [`results/week04/oracle-hieu/…`](../../results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/summary.md) | Evidence: log/meta/summary/source.patch |
| `docs/week03/{interface,lifecycle-review,proposal}.md`, `docs/week03/README.md` | Đính chính công thức counter/gauge + link PDF cũ (G03 phần Hiếu) |

---

## 11. Bàn giao và việc tiếp theo

**Bàn giao cho nhóm:**

- Contract + evidence index để Hoàng mở real harness (H01) và Lợi đồng bộ phần
  SCAN/deadline; oracle I01 + một lệnh chạy để H02/G02 dùng lại.
- Snapshot/schema để H02 ghi số liệu stress đúng đơn vị; `measurement.md` nêu rõ
  giới hạn tick.

**Việc cần làm (tuần 5 / trước chốt):**

1. Hoàng/Lợi review contract + snapshot trên cùng revision (đang **PENDING**).
2. H01: SCAN/deadline READ thật CPU1/4 có oracle order; H02: stress switch 10 boot
   + máy thứ hai; G02: final regression trên candidate SHA.
3. Nếu core ổn: bắt đầu owner/cancel + merge READ theo thiết kế I02 (code riêng,
   test M1–M10/N1–N4), sau khi chốt cơ chế cleanup/coherence.
4. Benchmark độ phân giải cao hơn cho latency (tuần 5+), không dùng tick 100 ms để
   kết luận p50/p99.

---

## 12. Đối chiếu kế hoạch tuần 4 (card của Hiếu)

| Card | Tiêu chí nghiệm thu (kế hoạch) | Kết quả Hiếu |
| :---: | :--- | :--- |
| W4-G01 | Ba người xác nhận cùng contract; giả định có trạng thái/owner; thống nhất scope | ✅ contract + owner/trạng thái; **2 review PENDING** |
| W4-G01 | Danh sách thiếu evidence có người xử lý; công thức/thông số khớp code; không claim GV duyệt thiếu nguồn | ✅ evidence index §4 (NOT RUN + owner); D23/D26 khớp code; Q1–Q8 PENDING |
| W4-I01 | Ma trận §14 PASS CPU1/4; ≥2 mutant EXPECTED_FAIL; phát hiện thiếu event/marker | ✅ PASS CPU1/4; 6 mutant bị bắt; oracle FAIL khi thiếu marker/END |
| W4-I01 | Bất biến counter/gauge đúng, cân bằng sau drain; tick thô thì chỉ báo phân bố/giới hạn | ✅ SNAP invariants PASS; `measurement.md` báo samples/zero_total, không p99 giả |
| W4-I02 | Review mô hình DMA/ordering; nêu API có/mới; nếu core trễ ghi DEFERRED | ✅ design + câu hỏi review; **DEFERRED**, chưa code |
| W4-G03 (phần Hiếu) | Cung cấp contract/oracle/counters/lifecycle limits; sửa phương trình + link PDF cũ | ✅ báo cáo này + đính chính tài liệu tuần 3 |

---

## 13. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-15 | `360b4df` | Code I01 (snapshot/latency/oracle/mutant/harness) + thiết kế I02; chạy PASS lần đầu. |
| 2026-11-15 | `4fa4de9` | Evidence I01 (mock CPU1/4, 6 mutant EXPECTED_FAIL, READ thật + IO-SNAP, production restore). |
| 2026-11-15 | — | Contract G01, `measurement.md`, `evidence-index.md`, báo cáo này; đính chính công thức/link tài liệu tuần 3. |
