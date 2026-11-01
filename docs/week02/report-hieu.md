# Báo cáo phần việc của Hiếu — tuần 2 (26/10 – 01/11/2026)

> **Người lập:** Phạm Trung Hiếu (20233402) — nhóm 3 người, đề tài **26128:
> Asynchronous virtio-blk và I/O schedulers trên xv6-riscv**.
> **Phạm vi báo cáo:** các card được giao cho Hiếu trong kế hoạch tuần 2
> (W2-G01, W2-I01, W2-I02) + phần việc tuần 1 còn liên quan + đóng góp phối hợp.
> **Ngày lập:** 2026-11-01. **Nhánh:** `week2/hieu-request`.
> **Base:** `e809500` (origin/main, 3 PR tuần 1 đã merge) · **Pin xv6 tạm:**
> `f780d785…` (GV chưa xác nhận tag chính thức).
>
> **Trạng thái chung:** 3/3 card của Hiếu đã có code + tài liệu + test PASS và
> commit trên nhánh; **cả 3 đang chờ reviewer xác nhận** (Hoàng review G01/I01/I02,
> Lợi review G01) nên **chưa đóng card**. Các test cần driver IRQ thật/queue
> (T01, T07–T10, T12–T13) vẫn **NOT RUN** — không ghi thành PASS.

---

## 1. Tóm tắt điều hành

- **W2-G01 (contract):** chốt mâu thuẫn lớn nhất của tuần 1 — chọn **pool sở hữu
  staging buffer** (bỏ mô hình caller-owned `kbuf`) và **một lock domain duy
  nhất** `io_lock` (bỏ phương án hai khóa `ioq.lock`/`vdisk_lock`); chốt API
  kernel-only, `struct io_handle{id, gen}`, vòng đời request/descriptor, quy tắc
  wait/wakeup, bảng context–khóa–lỗi cho từng hàm và 3 kịch bản review trên giấy.
- **W2-I01 (pool):** triển khai pool 16 slot trong BSS, try-alloc không ngủ/không
  panic, validate handle + generation trước mọi dereference, release chỉ khi
  terminal, counter `free_req/queued/inflight/eagain_pool/stale_handle`; kèm
  kernel selftest **T02/T03/T04/T11 PASS** và **negative control** chứng minh test
  bắt được bug.
- **W2-I02 (poll/wait/release):** triển khai `aio_poll`, `aio_wait` (đúng pattern
  `sleep_prepare→release→sleep→acquire`, single consumer), `aio_data`,
  `io_async_completed_locked` cho IRQ H02 gọi; harness test process-context
  **T05 complete-before-wait, T04 release-active, T06a lost-wakeup gap, T06b
  waiter ngủ thật được timer IRQ đánh thức** — tất cả PASS, có negative control
  bỏ `wakeup(req)` để chứng minh test bắt lost-wakeup.
- **Không ảnh hưởng production:** build production và `make test-fast` PASS;
  toàn bộ harness test nằm sau `#ifdef IO_SELFTEST`.
- **Việc còn lại trước khi đóng card:** reviewer ký cùng revision; push nhánh +
  mở PR; Lợi rà PTO trên Jira; trả lời câu hỏi GV (PTO-7); G02 tích hợp với
  H01/H02/L01 để chạy được các test IRQ/queue thật.

---

## 2. Vai trò và phạm vi tuần 2

Theo kế hoạch tuần 2, Hiếu phụ trách: **Pool/handle, buffer lifetime,
poll/wait/release** (8h) + 2h việc chung.

| Card | Đầu việc | Estimate | Hạn nội bộ | Trạng thái thực tế |
| --- | --- | ---: | --- | --- |
| **W2-G01** | Chốt interface request, buffer ownership và quy tắc khóa | 1,5h | 28/10 | ✅ có code/tài liệu/test; ⬜ chờ review |
| **W2-I01** | Triển khai request pool hữu hạn và handle có generation | 6h | 29/10 | ✅ có code/test/evidence; ⬜ chờ review |
| **W2-I02** | Bổ sung poll, wait và release tối thiểu an toàn | 2h | 30/10 | ✅ có code/test/evidence; ⬜ chờ review |
| G02/G03 (chung) | Tích hợp MVP + báo cáo tuần | 2h | 01/11 | ⏳ phần của Hiếu: contract/ownership review, evidence; chờ H01/H02/L01 |

> **Giờ actual chưa được ghi riêng.** Báo cáo giữ estimate của kế hoạch, không
> sao chép estimate thành giờ actual (theo quy tắc G03).

---

## 3. Công việc tuần 2 theo card

### 3.1 W2-G01 — Contract interface, buffer ownership, quy tắc khóa

**Commit:** `fa0746e` (2026-10-30) · 16 file, +1157/−31.

**Vấn đề phải giải:** hai tài liệu tuần 1 mâu thuẫn nhau: `async-design.md` cho
pool sở hữu buffer + một lock chung; `decisions_report.md` cho caller sở hữu
`kbuf` và chưa chốt khóa. Nếu ba nhánh code theo hai mô hình thì không ghép được
hoặc deadlock.

**Quyết định đã chốt (D1–D10):**

| Mã | Chốt | Phương án bị loại / lý do |
| --- | --- | --- |
| D1 | MVP kernel-level, READ 1 block `BSIZE=1024`, một device `ROOTDEV`, FCFS; WRITE/log giữ đường stock | syscall user-space/async WRITE/merge thật: chờ GV + ngoài tuần 2 |
| D2 | **Pool sở hữu staging buffer** (`uchar data[BSIZE]` trong slot BSS) | caller-owned `kbuf`: nhiều đường lifetime/IRQ/exit-kill; không kịp 1,5h contract + 6h pool |
| D3 | Đơn vị địa chỉ công khai là **blockno**; đổi sector đúng **một chỗ** trong driver (`blockno*2`) | để hai module cùng nhân 2 |
| D4 | `struct io_handle {id, gen}`; gen tăng khi release, khỏi 0; stale trả `-ENOENT` | dùng index trần: handle cũ trỏ nhầm slot tái sử dụng |
| D5 | Hai vòng đời tách rời: request `FREE→ALLOCATED→QUEUED→INFLIGHT→DONE/ERROR→FREE`, descriptor `FREE→RESERVED→PUBLISHED→USED→RECLAIMED→FREE` | gộp request/descriptor/buffer làm một |
| D6 | **Một lock domain** `io_lock` = `disk.vdisk_lock` qua `virtio_disk_io_lock()`; không acquire lồng; không ngủ khi giữ khóa | hai khóa `ioq.lock`/`vdisk_lock`: enqueue đi `ioq→vdisk`, completion cần `vdisk→ioq` ⇒ deadlock |
| D7 | Mỗi head có owner `STOCK/ASYNC`; **async: IRQ reclaim**, **stock: caller reclaim**; dispatch kick ở 3 điểm (submit, IRQ, stock reclaim); không free hai lần | free chung không xét owner ⇒ double-free stock |
| D8 | Mã lỗi `-EINVAL/-ENODEV/-ERANGE/-ENOENT/-EAGAIN/-EIO/-EBUSY`; pool đầy trả `-EAGAIN` không ngủ/panic | panic hoặc chờ vô hạn |
| D9 | Kênh chờ = con trỏ request; `waiters ∈ {0,1}` (single consumer); IRQ set terminal **trước** `wakeup`; wait dùng `sleep_prepare` khi còn giữ khóa | release ngay khi terminal ⇒ mất kết quả; prepare sau release ⇒ lost wakeup |
| D10 | Counter + bất biến kế toán (`submitted = queued+inflight+done+error`, free_req, free_desc về đủ sau drain) | "PASS vì không panic" |

**Đầu ra:**

- [`docs/week02/interface.md`](interface.md) — contract đầy đủ: bảng context/khóa/
  lỗi từng hàm, state machine, 3 kịch bản review trên giấy (hết pool; IRQ trước
  wait; head reuse trước release), map T01–T13 → contract, câu hỏi GV/PTO, bảng
  chữ ký reviewer (PENDING, không ghi "đã duyệt").
- [`kernel/io_request.h`](../../kernel/io_request.h) — header contract: enum/state,
  `struct io_request` (1080 B), `struct io_handle`, API, quy tắc lock/buffer.
- Cập nhật [`docs/week01/kickoff.md`](../week01/kickoff.md) (trạng thái thật đầu
  tuần 2 + câu hỏi GV), [`docs/architecture.md`](../architecture.md) §2.6–§2.7,
  banner "đã thay thế" ở [`docs/week01/async-design.md`](../week01/async-design.md)
  và [`docs/week01/decisions_report.md`](../week01/decisions_report.md).
- Bằng chứng: [`results/week02/g01-contract-2026-10-30/summary.md`](../../results/week02/g01-contract-2026-10-30/summary.md)
  — header compile `-Wall -Werror` + 3 `_Static_assert`, build clean PASS,
  `make check-text` PASS, `make test-fast` 2/2 PASS.

**Nghiệm thu card:** ✅ một contract duy nhất, hết mâu thuẫn buffer/lock; ✅ mỗi
hàm ghi context/khóa/hành vi hết tài nguyên; ✅ 3 kịch bản review trên giấy; ⬜
Hoàng + Lợi review cùng revision (hạn nội bộ 28/10 — hiện `PENDING`).

### 3.2 W2-I01 — Request pool hữu hạn + handle có generation

**Commit:** `5296c92` (2026-11-01) · 26 file, +1317/−9.

**Đã triển khai:**

- **Pool tĩnh** `io_pool[IO_NREQ=16]` trong BSS → địa chỉ header/status/buffer ổn
  định suốt boot, không `kalloc` trên đường async.
- `io_init()` gọi từ `main()` sau `virtio_disk_init()`; `io_alloc_slot_locked()`
  chỉ lấy slot FREE, pool đầy trả `NULL` + `eagain_pool++` (không ngủ/panic);
  `io_lookup_handle_locked()` kiểm id range + slot in-use + generation trước mọi
  dereference; `io_release_locked()` chỉ nhận DONE/ERROR, `waiters==0`, bump
  generation (khỏi 0), reset FREE; `aio_release()`; `io_get_stats()` (free_req/
  queued/inflight suy từ state để counter không drift).
- Slice sớm của H01: `virtio_disk_io_lock()` trả `&disk.vdisk_lock` để mọi module
  dùng đúng một lock domain (D6).
- Selftest riêng: **T02 pool-exhaustion, T03 stale-handle, T04 release-active,
  T11 accounting-drain (10 vòng) + buffer-address stability** — build bằng
  `-DIO_SELFTEST`, target một lệnh `make test-io`; production là stub rỗng.

**Bằng chứng:** [`results/week02/i01-pool-2026-10-30/summary.md`](../../results/week02/i01-pool-2026-10-30/summary.md)
— header check PASS, production build PASS, `test-fast` 2/2 PASS, `make test-io`
T02/T03/T04/T11 PASS; **negative control** tắt kiểm generation ⇒ T03 FAIL (4
assertion) và make exit ≠ 0, restore ⇒ PASS.

**Nghiệm thu card:** ✅ cấp đúng 16 slot, slot 17 bị từ chối, counter không đổi
(trừ `eagain_pool`); ✅ handle cũ bị từ chối sau reuse; ✅ không release slot còn
live/có waiter; ✅ không rò slot sau 10 vòng; ⬜ Hoàng review (PENDING).

### 3.3 W2-I02 — Poll, wait, release tối thiểu an toàn

**Commit:** `1677f11` (2026-11-01) · 27 file, +1290/−9.

**Đã triển khai:**

- `aio_poll()`: 1 = DONE, 0 = đang bay, `-EIO` = ERROR, `-ENOENT` = handle
  stale; không ngủ, không free slot.
- `aio_wait()`: chỉ process context; single consumer (`waiters`); vòng
  `sleep_prepare(req)` khi còn giữ `io_lock` → `release` → `sleep` → `acquire` →
  kiểm lại; fast-path trả ngay khi đã terminal; **không giữ spinlock khi ngủ**;
  `myproc()==0` trả `-EINVAL` (không wait trong IRQ/scheduler).
- `aio_data()`: trả staging buffer của pool; `io_async_completed_locked()`:
  chuyển DONE/ERROR + status + `t_complete` + counter + `wakeup(req)` — callback
  chuẩn để H02 gọi từ `virtio_disk_intr()`.
- Harness test **process-context** (chỉ `-DIO_SELFTEST`): `SYS_io_selftest` + init
  gọi test trước shell + timer hook trong `clockintr` + `scripts/io-selftest.sh`
  boot QEMU thẳng kernel (không qua make, tránh relink thiếu flag). Test:
  - **T05** complete-before-wait (DONE + ERROR + stale handle) → wait trả ngay;
  - **T04** release khi INFLIGHT → `-EBUSY`;
  - **T06a** completion rơi đúng khe `sleep_prepare→sleep` (deterministic, không
    dựa delay) → không mất wakeup;
  - **T06b** waiter ngủ thật, được **timer IRQ** hoàn tất và đánh thức
    (serial in `slept >= 3 tick(s)`);
  - **T03** handle sai (id âm, `id==NREQ`, gen 0, stale); **T11** drain.

**Bằng chứng:** [`results/week02/i02-poll-wait-2026-10-30/summary.md`](../../results/week02/i02-poll-wait-2026-10-30/summary.md)
— header compile 2 mode PASS, production build PASS, `test-fast` 2/2 PASS,
`make test-io` PASS (boot pool + process slice), **negative control** bỏ
`wakeup(req)` ⇒ T06a treo, không có PASS, make exit ≠ 0; restore ⇒ PASS.

**Nghiệm thu card:** ✅ wait sau DONE/ERROR trả ngay đúng status; wait trước
completion được đánh thức, không treo; ✅ release request đang bay `-EBUSY`;
✅ không giữ spinlock khi ngủ/không wait trong IRQ; ✅ lỗi handle hữu hạn, không
panic; ⬜ Hoàng review (PENDING).

### 3.4 Đóng góp phối hợp (G02/G03 — phần của Hiếu)

- **Nguồn sự thật cho L01/H01/H02:** header + contract chốt sẵn state machine,
  lock domain, owner/reclaim, callback completion (`io_async_completed_locked`),
  helper pool (`io_alloc_slot_locked`/`io_lookup_handle_locked`/
  `io_release_locked`), điểm dispatch-kick sau stock reclaim.
- **Hạ tầng test dùng lại được:** `make test-io` + `scripts/io-selftest.sh` +
  `io_selftest()`/`SYS_io_selftest` (guard `#ifdef IO_SELFTEST`); H02/G02 có thể
  mở rộng test IRQ thật trên cùng khung.
- **Cập nhật tài liệu chung:** kickoff trạng thái thật, architecture §2.6/§2.7,
  docs/README index, banner thay thế mô hình cũ.
- **Phần chưa đóng góp được cho G02:** tích hợp end-to-end và chạy T01–T13 cần
  H01/H02/L01 merge trước; Hiếu sẽ review ownership/API và chạy lại ma trận khi
  có nhánh tích hợp.

---

## 4. Phần việc tuần 1 của Hiếu (trạng thái thật)

| Mã | Việc | Bằng chứng hiện có | Trạng thái thật |
| --- | --- | --- | --- |
| T1-01 | Kickoff, biên bản, câu hỏi GV | [`docs/week01/kickoff.md`](../week01/kickoff.md) — đã cập nhật trạng thái thật đầu tuần 2, bảng câu hỏi Q1–Q7 có owner | ✅ file có; nhóm **không họp kickoff riêng**; câu hỏi GV còn `PENDING` |
| T1-04 | FigJam 3 trang + quyền GV | Chưa thấy URL FigJam trong repo | ⬜ **PENDING/NOT EVIDENCED** — cần bổ sung URL hoặc xác nhận nhóm dùng draw.io thay thế |
| T1-05 | Version log 3 máy + README tái lập | [`docs/week01/environment.md`](../week01/environment.md) có dòng `laptop-Hiếu` (Ubuntu 26.04.1, env-check PASS sau cài QEMU) | 🟡 điền một phần — cột **Ngày còn `TODO`**; **baseline riêng máy Hiếu chưa có** (kế hoạch tuần 2 đã ghi nhận, chuyển G02) |
| T1-08 | Buffer ownership, bread/bwrite/log, async API | [`docs/week01/decisions_report.md`](../week01/decisions_report.md) (owner Hiếu) + banner cập nhật thay thế mô hình | ✅ tài liệu có; mô hình caller-`kbuf` đã được G01 thay bằng pool-owned buffer (D2/D3) |
| T1-10 | Test plan ≥ 30 case + format kết quả | [`docs/week01/test-plan.md`](../week01/test-plan.md) (owner Hiếu) — phân tầng T0–T6, ma trận CPUS, benchmark, stress, mục NOT RUN | ✅ khung có; các case policy/async/merge còn `NOT RUN` vì chưa có code |
| T1-12 | Báo cáo tuần 1 + review chéo | File `docs/week01/progress-report.md` từng tồn tại nhưng đã bị xoá ở commit dọn dẹp `c5adc4f`; báo cáo tuần 1 đã nộp 25/10 theo kế hoạch tuần 2 | 🟡 **không còn bằng chứng trong repo hiện tại** — nếu G03 cần thì khôi phục từ lịch sử git hoặc bổ sung bản tóm tắt |

> Không đánh dấu `Done` cho mục thiếu bằng chứng; các mục trên là dữ liệu để
> G03 tổng hợp, không phải kết quả đã kiểm chứng lại.

---

## 5. Kiểm thử và bằng chứng tổng hợp

### 5.1 Test đã PASS (có log trong `results/week02/`)

| Nhóm | Test | Môi trường | Bằng chứng |
| --- | --- | --- | --- |
| Contract | header compile (`-Wall -Werror`, 3 `_Static_assert`), build clean, `test-fast` 2/2 | WSL2 + riscv gcc 13.3.0 + QEMU 8.2.2 | [G01 summary](../../results/week02/g01-contract-2026-10-30/summary.md) |
| Pool/handle | T02 pool-exhaustion, T03 stale-handle, T04 release-active, T11 accounting (10 vòng), buffer address | kernel selftest `make test-io` | [I01 summary](../../results/week02/i01-pool-2026-10-30/summary.md) |
| Poll/wait | T05 complete-before-wait (DONE+ERROR+stale), T04 release-active, T06a gap-completion, T06b sleep/wakeup bằng timer IRQ, T03 handle sai, T11 drain | process context qua `SYS_io_selftest` + `make test-io` | [I02 summary](../../results/week02/i02-poll-wait-2026-10-30/summary.md) |
| Negative control | I01: tắt kiểm generation ⇒ T03 FAIL; I02: bỏ `wakeup` ⇒ T06a treo/FAIL; restore ⇒ PASS | như trên | log `negative-control-*` trong 2 thư mục evidence |
| Regression | `make test-fast` 2/2 PASS trên production build ở cả I01 và I02 | QEMU CPUS=1/3 | `logs/test-fast.log` trong evidence |

### 5.2 NOT RUN (không đổi thành PASS)

| Hạng mục | Lý do | Kế hoạch |
| --- | --- | --- |
| **T01** single READ block thật | cần H01 try-submit + H02 completion/IRQ | G02 |
| **T07** backpressure descriptor, **T08** head reuse, **T09** completion mapping/đảo thứ tự, **T10** submit không chờ | cần driver/queue hoặc mock driver của H/L | G02 |
| **T12** stock regression `usertests -q`, `grind 60s` CPUS=1/4 | chưa chạy trong phiên card; thuộc G02 | G02 |
| **T13** oracle FCFS | cần queue L01 | L02 + G02 |
| T06 CPUS=4 / multi-waiter / kill-exit / cancel | K04 đầy đủ để kỳ sau; MVP chỉ single consumer | kỳ sau |
| `aio_read_submit` end-to-end | cần L01 + H01/G02 | G02 |
| Baseline riêng máy Hiếu | chưa có trong hồ sơ; máy Hiếu Ubuntu 26.04 | G02 |

### 5.3 Môi trường và giới hạn bằng chứng

- Bằng chứng chạy trên **Windows 11 + WSL2 Ubuntu-24.04**, 6 CPU, riscv gcc
  13.3.0, QEMU 8.2.2, GNU Make 4.3, Python 3.12.3. **Không phải** máy Ubuntu
  26.04 của Hiếu → không dùng làm baseline hiệu năng.
- Mọi evidence chạy trên cây làm việc dirty của nhánh; hash commit cuối là
  `fa0746e`/`5296c92`/`1677f11` (báo cáo trích đúng hash, không trích base như
  hash của card).
- `make test-io` để lại kernel build `-DIO_SELFTEST`; phải `make clean && make`
  trước khi dùng cho việc khác (đã làm ở bước restore trong evidence).
- Log tiếng Việt phải chạy với `LANG=C.UTF-8 LC_ALL=C.UTF-8
  PYTHONIOENCODING=utf-8`, nếu không make/echo WSL sinh mojibake và
  `make check-text` FAIL.

---

## 6. Trạng thái, blocker và việc còn lại

| Việc | Owner | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Review W2-G01 (contract/buffer/lock) | Hoàng + Lợi | ⬜ PENDING | review cùng revision = commit của PR; cần trước khi merge module |
| Review W2-I01 (pool/generation/lock slice) | Hoàng | ⬜ PENDING | đặc biệt slice `virtio_disk_io_lock()` thuộc H01 |
| Review W2-I02 (wait/wakeup, harness test-only) | Hoàng | ⬜ PENDING | kiểm tác động production (đã có build + test-fast) |
| Push nhánh + mở PR | Hiếu | ⬜ PENDING | nhánh local đang ahead 2 so với `origin/week2/hieu-request` |
| Rà PTO-4/7/9/10/11 trên Jira | Lợi | ⬜ PENDING | môi trường làm việc không có quyền Jira; bằng chứng repo đã ghi trong interface §9.2 |
| 7 câu hỏi GV (PTO-7): tag, API/syscall, READ-only, SCAN/LOOK, merge, rubric, max_inflight | theo owner | ⬜ PENDING | interface §9.1, không tự suy đáp án |
| Tích hợp MVP + test IRQ/queue thật (G02) | Hoàng chủ trì | ⏳ chờ H01/H02/L01 | Hiếu review ownership/API + chạy lại ma trận |
| Baseline riêng máy Hiếu | Hiếu | ⬜ PENDING | G02, cùng base commit |

**Blocker kỹ thuật đã biết:** chưa có `aio_read_submit` end-to-end, chưa có
try-submit/IRQ (H01/H02), chưa có queue (L01) ⇒ các test cần thiết bị thật chưa
chạy được. Hiếu đã cung cấp callback `io_async_completed_locked` + contract để
H02/L01 ghép; không tự đổi ownership để vượt blocker.

---

## 7. Kế hoạch tiếp theo của Hiếu

1. **Cùng Hoàng/Lợi review** 3 commit `fa0746e`, `5296c92`, `1677f11`; xử lý
   comment và đóng card khi cả hai ký cùng revision.
2. **Push nhánh + PR** `week2/hieu-request → main`, gắn reviewer, kèm link
   evidence và bảng T-case; không tự merge.
3. **G02:** review tích hợp H02 (IRQ completion) + L01 (FCFS) theo contract; bổ
   sung test hook cho completion thật; chạy ma trận T01/T07–T13 trong phạm vi MVP.
4. **Bổ sung baseline máy Hiếu** (Ubuntu 26.04) trên đúng base, tách khỏi số liệu
   máy dev; ghi version/hash/CPU/log đầy đủ.
5. **Kỳ sau (K04):** kill/exit/cancel, multi-waiter, timeout không free DMA,
   quyết định mô hình buffer/API theo trả lời của GV (Q2/Q3).

---

## 8. Phụ lục

### A. Commit của Hiếu trong tuần 2

| Commit | Nội dung | File thay đổi | Bằng chứng |
| --- | --- | --- | --- |
| `fa0746e` | W2-G01 contract + header | 16 file (+1157/−31) | `results/week02/g01-contract-2026-10-30/` |
| `5296c92` | W2-I01 pool/handle + selftest | 26 file (+1317/−9) | `results/week02/i01-pool-2026-10-30/` |
| `1677f11` | W2-I02 poll/wait/release + harness | 27 file (+1290/−9) | `results/week02/i02-poll-wait-2026-10-30/` |

Lịch sử nhánh: `e809500` (origin/main tuần 1) → `fa0746e` (G01) → `c5adc4f`
(dọn tài liệu, không thuộc card của Hiếu) → `5296c92` (I01) → `1677f11` (I02).

### B. File chính Hiếu đã tạo/sửa

| Nhóm | File |
| --- | --- |
| Contract | `docs/week02/interface.md`, `kernel/io_request.h` |
| Pool/API | `kernel/io_request.c`, `kernel/io_request_test.c`, `kernel/defs.h`, `kernel/main.c` |
| Test harness | `scripts/io-selftest.sh`, `mk/project.mk` (`make test-io`), `kernel/syscall.{h,c}`, `kernel/trap.c`, `user/usys.pl`, `user/init.c` (phần guard `#ifdef IO_SELFTEST`) |
| Tài liệu | `docs/week02/progress-i01.md`, `docs/week02/progress-i02.md`, `docs/week01/kickoff.md`, `docs/architecture.md` §2.6–§2.7, `docs/week01/{async-design,decisions_report}.md` (banner), `docs/README.md` |

### C. Lệnh tái lập

```bash
# production
make clean && make -j"$(nproc)"
make test-fast

# kernel selftest (W2-I01 + W2-I02), chỉ build -DIO_SELFTEST
make test-io
# sau đó trả về production:
make clean && make

# kiểm tra tài liệu
make check-text
```

### D. Ghi chú kỹ thuật / rủi ro đã xử lý

- **Không cho make relink thiếu flag:** `make qemu` không track CFLAGS nên có
  thể link lại object production sau khi build `-DIO_SELFTEST` (đã gặp lỗi
  `undefined reference io_test_timer_tick`). Giải pháp: `scripts/io-selftest.sh`
  boot QEMU trực tiếp, không gọi make.
- **Production an toàn:** toàn bộ hook test nằm trong `#ifdef IO_SELFTEST`;
  `SYS_io_selftest` trả `-1`, `init`/`clockintr` không gọi test; đã chứng minh
  bằng production build + `test-fast`.
- **Khi cập nhật pin xv6:** các mảnh test-only trong file upstream
  (`kernel/syscall.{h,c}`, `kernel/trap.c`, `user/usys.pl`, `user/init.c`) phải
  re-apply sau `scripts/update-xv6.sh` — ghi vào checklist kỳ sau.
- **Một workspace dùng chung:** trong phiên có thay đổi tài liệu từ tiến trình
  khác (`docs/architecture.md`, `docs/baseline.md`, `docs/upstream.md`); các
  thay đổi này **không** nằm trong commit của Hiếu.

### E. Nguồn tham chiếu

- Kế hoạch triển khai tuần 2 — đề tài 26128 (PDF, lập 27/10/2026): các card
  W2-G01/W2-I01/W2-I02, ma trận T01–T13, quy tắc đóng card.
- Contract tuần 2: [`docs/week02/interface.md`](interface.md).
- Tiến độ chi tiết: [`docs/week02/progress-i01.md`](progress-i01.md),
  [`docs/week02/progress-i02.md`](progress-i02.md).
- Bằng chứng: 3 thư mục `results/week02/*` (README format:
  [`results/README.md`](../../results/README.md)).

---

> **Người lập:** Phạm Trung Hiếu — soạn ngày 2026-11-01, có sự hỗ trợ của AI
> agent trong việc chạy lệnh/test và soạn thảo; mọi số liệu lấy từ log/commit
> thật trong repo, không suy diễn. Báo cáo này **không thay thế** review của
> Hoàng/Lợi và không tự đánh dấu card `Done`.
