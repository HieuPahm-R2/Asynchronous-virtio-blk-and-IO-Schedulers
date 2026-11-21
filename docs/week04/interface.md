# W4-G01 — Contract tuần 4: deadline, runtime switch, snapshot và evidence index

**Đề tài 26128 · ET4290 · Asynchronous virtio-blk và I/O schedulers trên xv6-riscv**
Kỳ tuần 4: **09–15/11/2026**. Tài liệu chốt ngày **15/11/2026** (Asia/Saigon).
Chủ trì: **Phạm Trung Hiếu (20233402)** — Hiếu điều phối; Hoàng + Lợi cùng xác nhận.
Reviewer chéo: Hoàng (driver/IRQ/lock), Lợi (queue/ordering/switch).

Đây là **contract tuần 4**: nó kế thừa contract tuần 2 (`docs/week02/interface.md`,
D1–D10) và tuần 3 (`docs/week03/interface.md`, D11–D20), bổ sung **D21–D27** cho
deadline, đổi policy khi có tải, snapshot/kế toán và đo lường. Khi contract và code
lệch nhau, sửa cả hai trong cùng một PR.

> Trạng thái quyết định: D21/D22/D23/D24 do G01 **chốt nội bộ nhóm** (đề xuất của
> Lợi trong L01/L02, Hiếu chuẩn hoá theo kế hoạch tuần 4 §13) và **chờ Hoàng + Lợi
> xác nhận trên cùng revision**. Không có phê duyệt nào của giảng viên trong tài
> liệu này; các câu hỏi PTO-7 vẫn **PENDING**.

---

## 1. Mục tiêu card và quan hệ với tuần 3

Card **W4-G01** (P0, 3 h tổng = 1 h/người): chốt contract tuần 4 trên main đã có cả
ba phần tuần 3, để **selector, harness và oracle dùng cùng một quy tắc** trước khi
viết code. Cụ thể:

1. Khoá base revision, ghi rõ phần đã merge ở tuần 3 và các khoảng trống còn lại.
2. Giữ **SCAN theo contract D11–D20** làm baseline; không đổi tên LOOK thành SCAN,
   không tự bỏ SCAN khi chưa có nguồn xác nhận của GV.
3. Chốt **D21+** cho deadline (nguồn thời gian, expire, tie-break, batch, trường dữ
   liệu) và **D22+** cho runtime switch (commit point, reset state, event/epoch).
4. Sửa chỗ lẫn **counter tích luỹ** với **gauge hiện tại**; chốt fixture stress theo
   source thật; ghi rõ evidence nào còn thiếu.
5. Ghi review trên cùng revision và danh sách câu hỏi cần GV xác nhận.

Đầu ra: tài liệu này + [`evidence-index.md`](evidence-index.md) +
[`measurement.md`](measurement.md) + header `kernel/io_request.h` (khai báo contract
mới). Code deadline/switch do **W4-L01/L02 (Lợi)**; test độc lập/snapshot do
**W4-I01 (Hiếu)**; READ thật/stress do **W4-H01/H02 (Hoàng)**.

---

## 2. Base revision và hiện trạng kế thừa

| Hạng mục | Trạng thái thực tế trên nhánh W4 | Bằng chứng |
| :--- | :--- | :--- |
| `origin/main` | `5191ed8beda658120bf08667b87657fa45ed1861` — merge PR #8 (Hoàng toolchain/stress), #9 (Hiếu contract/lifecycle/proposal), #10 (Lợi SCAN) | `git log --oneline origin/main` |
| SCAN logic | **Đã có code** trên main: `kernel/io_queue.c` (D13–D16), oracle 10 ca + unlink, 3 mutant | W3-L01/L02; `tests/cases/ioq_scan.py` |
| FCFS | **Đã có** từ tuần 2; production mặc định FCFS | `results/week02/…` |
| Request pool/handle/wait | **Đã có** từ tuần 2 (pool 16, generation, `aio_poll/wait/release`) | T02–T06, T11 |
| READ thật virtio | **Đã có** harness; trên nhánh W4 có log FCFS real 10+10 boot và negative fixture | `results/week04/fcfs-regression/…` |
| Deadline + runtime switch | **Đã có code** nhánh `week4/loi-deadline-switch` (commit `7ae79f7`, `17a9d9b`): enum `IO_POLICY_DEADLINE`, `io_queue_set_policy_locked()`, `io_set_policy()`, SWITCH event/epoch | card W4-L01/L02 |
| Owner/orphan/cancel | **Chỉ thiết kế** tuần 3; **chưa** có owner_pid/owner check/`kio_owner_exit` trong `aio_wait`/`kexit` | W3-I01; W4-I02 tiếp tục thiết kế |
| Snapshot hợp nhất + latency | **Mới ở W4-I01**: `struct io_snapshot`, `io_get_snapshot()`, `*_locked` helpers, latency aggregates | commit `360b4df`; `docs/week04/measurement.md` |
| Runtime switch cho user | **Chưa** — chỉ kernel control (`io_set_policy()`); chưa có syscall | D22.6 |
| Merge READ / async WRITE / LOOK | **Chưa** — chỉ thiết kế (I02) hoặc ngoài phạm vi | D27 / §3.2 |

Base revision của nhánh Hiếu là **`0dc296e`** (nhánh Lợi `week4/loi-deadline-switch`
trên main `5191ed8`), code I01 ở commit **`360b4df`**, evidence ở commit **`4fa4de9`**.
Nhóm nghiệm thu trên **một candidate SHA cuối** sau G02, không cộng dồn log tuần 3 vào
chỉ tiêu tuần 4.

---

## 3. Phạm vi tuần 4 (chốt)

### 3.1 Trong phạm vi core

- READ async **1 block = 1024 B**, device `ROOTDEV`, block `0..FSSIZE-1`,
  `FSSIZE = 2000`, pool `IO_NREQ = 16`, `NUM = 8` descriptor, `max_inflight = 2`.
- Ba policy: **FCFS / SCAN / DEADLINE**; production mặc định **FCFS**.
- Runtime switch **kernel control** giữa 3 policy khi queue có request, có `epoch`/
  counter/event; **không** có syscall user trong tuần 4.
- Deadline là **ngưỡng tuổi để ưu tiên dispatch**, **không** phải EDF/thời gian thực,
  **không** bảo đảm hoàn tất trước hạn.
- Oracle Python độc lập cho SCAN (giữ nguyên tuần 3), deadline và switch; mutant
  negative control; snapshot hợp nhất dưới một `io_lock`.
- READ thật FCFS/SCAN/deadline tối thiểu, stress switch, máy thứ hai (H01/H02/G02).
- Báo cáo/demo phản ánh đúng phần đạt/chưa đạt (G03).

### 3.2 Ngoài phạm vi tuần 4 — không hứa, không tuyên bố đã làm

- Implement owner/owner-check/`aio_cancel`/`aio_abandon`/`io_owner_exit` — **chỉ
  thiết kế** (I02, P2 mở rộng); code để tuần 5+.
- Merge READ ở mức thiết bị (một lệnh DMA nhiều block) — **chỉ thiết kế** (I02);
  không code, không test.
- Async WRITE, fence/flush, coherence với `bread()`, `NUM = 32/64`.
- LOOK: giữ như phương án thay thế; chỉ triển khai nếu có nguồn xác nhận của GV.
- Benchmark ≥ 5 lần/điểm và stress ≥ 30 phút; benchmark cuối kỳ.
- Syscall/API user hoàn chỉnh, fork/exit và bảng handle kiểu fd.
- Không sửa request `INFLIGHT`, không cấp phát/ngủ/printk trong IRQ.

---

## 4. Quyết định tuần 4 (D21–D27)

### D21 — DEADLINE: ngưỡng tuổi + batch vị trí giới hạn

**Trạng thái:** chốt nội bộ nhóm (chờ Hoàng + Lợi xác nhận cùng revision).

- **Nguồn thời gian:** `ticks` của xv6 (timer 1e6 cycles ≈ **100 ms/tick** trên QEMU
  pin). Đọc trực tiếp một word dưới `io_lock`, **không** acquire `tickslock` để tránh
  mở thứ tự khoá mới. Trong build `-DIOQ_SELFTEST` thay bằng **đồng hồ giả** để
  fixture xác định.
- **Tuổi:** `age = now - t_enqueue`, so sánh **wrap-safe** theo int32
  (`(int)(now - t_enqueue)`), đúng trong miền age < 2^31 tick. `t_enqueue` do
  `io_queue_enqueue_locked()` gán, **không reset** khi đổi policy hoặc gặp `EAGAIN`.
- **Expire:** READ expire = **50 tick** (`IOQ_DL_READ_EXPIRE`), batch limit =
  **4** (`IOQ_DL_BATCH`). Đây là hằng số khởi đầu để có oracle xác định; muốn đổi
  phải review và ghi vào meta của mọi lượt chạy.
- **Luật chọn** (`deadline_pick_locked()`), O(16), thuần (không sửa trạng thái):
  1. Quét request `QUEUED`; nếu có **expired** (`age >= 50`) thì chọn **expiry sớm
     nhất** = `t_enqueue` nhỏ nhất; hoà theo `enqueue_seq`. Reason `EXPIRED`.
  2. Không có expired và `batch_count >= 4` thì chọn **FIFO** = request cũ nhất
     (đầu hàng, `enqueue_seq` nhỏ nhất). Reason `FIFO`.
  3. Ngược lại chọn **block thấp nhất**, hoà theo `seq`. Reason `POSITION`.
- **Batch:** dispatch `EXPIRED` hoặc `FIFO` đặt `batch_count = 0`; dispatch
  `POSITION` tăng `batch_count` thêm 1. Recheck expired **trước mỗi lần chọn**
  (đọc lại `now` mỗi vòng dispatch).
- **Commit:** chỉ commit khi `try_submit` trả **0**; `IO_EAGAIN` **không** đổi
  candidate/head/batch/trace. Request `INFLIGHT` không bị đụng.
- **Hệ quả giới hạn:** hết descriptor hoặc thiết bị không hoàn tất thì cả deadline
  lẫn batch đều không bảo đảm latency. Không dùng completion time làm input của
  quyết định deadline; không gọi đây là EDF.

### D22 — Runtime switch: một điểm commit dưới `io_lock`

- **API:** `io_queue_set_policy_locked(enum io_policy)` (yêu cầu đã giữ `io_lock`)
  và wrapper process-context `io_set_policy(policy)` (tự acquire `io_lock`). Tách
  khỏi setter test-only cũ `io_queue_set_policy()` (chỉ trước enqueue đầu tiên,
  D19). Tên API đã chốt trong G01; không mở syscall user trong tuần 4.
- **Kiểm trước khi sửa:** enum chỉ nhận `FCFS/SCAN/DEADLINE`; giá trị khác trả
  `IO_EINVAL = -22` và **không đổi gì**. Cùng policy là **no-op**: trả 0, **không**
  tăng `epoch`/`policy_switches`, **không** ghi event.
- **Commit:** dưới `io_lock`, tại điểm giữa hai lần dispatch. Thành công thì:
  `policy = new`, `epoch++`, `policy_switches++`, ghi **một** event `IOQ_EV_SWITCH`.
- **State transition:**
  - Vào **SCAN**: `logical_head = last_block` (block của dispatch thành công gần nhất
    ở **mọi** policy; `0` nếu chưa có dispatch nào), `direction = UP`. Không dùng
    `q.logical_head` hiện tại vì nó chỉ cập nhật ở SCAN.
  - Vào **DEADLINE**: `batch_count = 0`.
  - "last successful dispatch block" (`last_block/has_last`) được cập nhật ở **mọi**
    dispatch thành công, mọi policy.
- **Bất biến:** không xoá/re-enqueue queue; không đổi `id/gen/seq/t_enqueue/expiry`;
  không thu hồi chain `INFLIGHT`; request `INFLIGHT` của policy cũ hoàn tất bình
  thường; switch **không tự dispatch** — lần pick kế tiếp dùng policy mới.
- **Quan sát:** SWITCH event mang `old/new/head/dir/batch/epoch`; snapshot có
  `policy/epoch/policy_switches/batch_count/last_block/has_last`.
- **Kiểm:** đủ 6 chiều chuyển giữa 3 policy; ít nhất một ca switch khi **Q>0 và
  I>0**; queue rỗng; no-op; enum sai; switch rồi `EAGAIN`. Không dùng reboot chọn
  policy thay cho runtime switch.

### D23 — Snapshot hợp nhất và bất biến kế toán

**Phân biệt bắt buộc — counter tích luỹ vs gauge hiện tại** (sửa lỗi trộn hai loại
trong tài liệu tuần 3, xem [`../week03/interface.md`](../week03/interface.md) D20 –
đã đính chính):

| Ký hiệu | Ý nghĩa | Loại |
| :---: | :--- | :--- |
| **S** | `submitted` — số request được cấp slot/handle thành công | tích luỹ |
| **C** | `completed` — số request kết thúc `DONE` | tích luỹ |
| **E** | `errors` — số request kết thúc `ERROR` | tích luỹ |
| **R** | `released` — số slot terminal đã được release/auto-free | tích luỹ |
| **Q/I/D/X** | queued / inflight / done / error slots hiện tại | gauge |
| **F** | `free_req = IO_NREQ - (Q+I+D+X)` | gauge |

**Bất biến (chưa có cancel/orphan trong revision này):**

```
S = Q + I + C + E
C + E = R + D + X
IO_NREQ (16) = F + Q + I + D + X
Sau drain:  S = C + E = R;  Q = I = D = X = 0;  F = 16;  free_desc = 8
```

Ghi chú quan trọng: `S` **không** bằng `Q+I+D+X` (đó là lỗi cũ); `C+E` lấy counter
tích luỹ, còn `D+X` là gauge. Unit test tự tạo state **không** áp dụng máy móc công
thức cumulative của luồng API thật; chỉ so drain cuối sau khi mọi worker kết thúc.

**Snapshot một khoá** — `struct io_snapshot` + `io_get_snapshot()` (process context,
tự lấy `io_lock`) / `io_snapshot_locked()` (yêu cầu đã giữ khoá):

- request layer: `S/C/E/R`, `Q/I/D/X/F`, `max_inflight`, `eagain_pool`,
  `stale_handle`;
- queue/dispatcher: `enqueued`, `dispatched`, `eagain`, `boundary_events`,
  `policy_switches`, `dl_expired`, `dl_fifo`, `trace_overflow`;
- policy state: `policy`, `epoch`, `batch_count`, `last_block`, `has_last`;
- driver: `free_desc`, `eagain_desc`, `completed_stock`, `completed_async`,
  `head_reuse`;
- timing: `samples`, `wait_sum/max`, `service_sum/max`, `total_sum/max`,
  `zero_total`, `ticks_now`.

Không được dựng lại snapshot bằng cách gọi rời `io_get_stats()` +
`virtio_disk_get_stats()` (hai thời điểm khoá khác nhau). Các getter public vẫn tự
lấy khoá; thêm helper `io_get_stats_locked()`, `virtio_disk_get_stats_locked()`
để tránh acquire lồng. `trace_overflow` tăng khi trace 64 event đầy; **không** ghi
đè vòng.

### D24 — Đo lường: đơn vị, độ phân giải, mẫu

- Queue wait = `t_dispatch - t_enqueue`; service = `t_complete - t_dispatch`;
  total = `t_complete - t_enqueue`. Đơn vị: **tick**; 1 tick ≈ **100 ms** trên QEMU
  pin (timer 1e6 cycles). Độ phân giải = 1 tick ⇒ một mẫu `total == 0` nghĩa là
  **dưới 1 tick**, **không phải 0 ms**; báo `zero_total`/`samples` thay vì p99 giả.
- Bắt buộc báo kèm: đơn vị, độ phân giải, `samples`, `zero_total`, `trace_overflow`,
  policy/expiry/batch của lượt chạy. Không trộn trung bình giữa các workload khác
  nhau để so policy; không suy `max_inflight = 2` thành thiết bị chạy song song.
- Tick quá thô để kết luận latency thật; READ thật/drain/invariant vẫn phải đo.
- Chi tiết schema, công thức và kết quả mẫu: [`measurement.md`](measurement.md).

### D25 — Revision, evidence và metadata bắt buộc

Mỗi lượt chạy phải ghi: commit + dirty/source hash; xv6 pin; máy/OS; compiler/QEMU/
make; `TOOLPREFIX`; lệnh/cờ/CPU; seed/fixture/checksum; expiry/batch; số boot/READ/
switch; expected/actual; timeout; raw log; production restore; reviewer. Chỉ đổi
commit sau khi chạy phải ghi lại phạm vi đã tái kiểm. Negative control báo
**EXPECTED_FAIL** riêng, không cộng vào PASS; thiếu marker/timeout là **FAIL**.
Danh mục bằng chứng: [`evidence-index.md`](evidence-index.md).

### D26 — Fixture, oracle độc lập và negative control

- **Fixture stress** (theo source thật, không theo báo cáo cũ): 32 block cuối ảnh
  test **1968..1999**, window 5, **4 worker × 120 READ/boot**, seed `0x26128003`,
  có backup/restore và checksum toàn block. Negative fixture lật **byte đầu block
  `FSSIZE-32`** trên **ảnh sao tạm**; restore rồi chạy lại positive.
- **Oracle độc lập:** tính expected từ contract, **không** đọc code C làm đáp án,
  **không** lấy trace/output của kernel làm expected. Giữ nguyên oracle SCAN tuần 3.
  Phải phát hiện thiếu event/marker, không chỉ tìm chuỗi `PASS`.
- **Mutant bắt buộc:** (a) bỏ ưu tiên expired; (b) reset arrival/expiry khi switch.
  Tối thiểu 2 mutant; repo hiện có `dl-m1-no-expired`, `sw-m2-reset-age` (L01/L02)
  và 3 mutant I01 (`i01-m1-expired-latest`, `i01-m2-noop-epoch`,
  `i01-m3-keep-batch`). Patch/restore trong `finally`; mutant **không** được lọt vào
  revision bàn giao.

### D27 — Merge READ / owner / cancel: chỉ thiết kế, chưa code

Theo phân công, owner/cancel và merge READ ở mức thiết bị là **P2 mở rộng**: chỉ
thiết kế ở [`merge-lifecycle-design.md`](merge-lifecycle-design.md), **không code**,
**không test** trong tuần 4. Nguyên tắc giữ nguyên từ W3-I01: không free slot /
descriptor / buffer DMA khi còn `QUEUED`/`INFLIGHT`; `released++` trên mọi đường
auto-free; design DEFERRED toàn bộ nếu core trễ. Implementation chỉ bắt đầu sau khi
review cơ chế cleanup/coherence (tuần 5+).

---

## 5. Thuật toán tham chiếu

### 5.1 Deadline pick (thuần, dưới `io_lock`)

```
pick_deadline(now):
  best = none
  for r in queue_by_seq:                 # thứ tự liên kết = thứ tự enqueue_seq
    if age(r.t_enqueue, now) >= 50 and
       (best == none or r.t_enqueue before best.t_enqueue):
      best = r
  if best != none: return (best, EXPIRED)
  if batch_count >= 4: return (queue_head, FIFO)
  return (min_by_block_then_seq(queue), POSITION)
```

Commit sau khi driver nhận (`try_submit == 0`):

```
if reason == EXPIRED: batch_count = 0; dl_expired++
elif reason == FIFO:  batch_count = 0; dl_fifo++
else:                 batch_count++
last_block = r.blockno; has_last = 1
```

### 5.2 Switch (dưới `io_lock`, không dispatch)

```
set_policy_locked(new):
  if new not in {FCFS, SCAN, DEADLINE}: return EINVAL      # không đổi gì
  if new == policy: return 0                               # no-op
  if new == SCAN: logical_head = has_last ? last_block : 0; direction = UP
  if new == DEADLINE: batch_count = 0
  policy = new; epoch++; policy_switches++
  trace_add(SWITCH(old, new, head, dir, batch, epoch))
```

### 5.3 Ví dụ chuẩn (dùng chung oracle)

Fixture `i01-dl-age-before` (đồng hồ giả 500): `A(40), A(10), T(49), CAP=1` →
tuổi 49 < 50 nên chưa expired ⇒ chọn block thấp `10` (`POSITION`, batch 1), sau khi
một slot hoàn tất chọn `40` (`POSITION`, batch 2). Fixture `i01-dl-age-at` với
`T(50)` → tuổi đúng 50 ⇒ cả hai `EXPIRED`, hoà expiry nên theo `seq`: `40` trước,
`10` sau. Fixture `i01-sw-keep-age` (FCFS 1000, `A(40)`, `T(45)`, `SW(DEADLINE)`,
`T(10)`, `A(5)`) → request `40` vẫn expired dưới deadline (tuổi 55) và được dispatch
trước `5`; nếu switch reset tuổi thì oracle FAIL.

---

## 6. Trace và event schema tuần 4

Trace hữu hạn `IOQ_TRACE_N = 64`, chỉ ghi **sự kiện đã commit**, dưới `io_lock`;
copy snapshot ra rồi in ở process context, **ngoài** khoá. Trường thêm ở tuần 4
(append, không đổi layout cũ):

| Event | Trường | Ý nghĩa |
| :--- | :--- | :--- |
| `DISPATCH` | `policy, seq, blockno, head_before/after, dir_before/after, reason, batch_after, epoch` | một request đã được driver nhận |
| `BOUNDARY` | `boundary(0/1999), head, dir_before/after, epoch` | SCAN chạm biên logic, đảo chiều |
| `SWITCH` | `old_policy, policy(new), head_before/after, dir_after, batch_after, epoch` | một lần đổi policy đã commit |

`reason ∈ {NONE, EXPIRED, POSITION, FIFO}` chỉ có nghĩa với DEADLINE. Output test
dùng marker riêng: `IOQSCAN` (SCAN tuần 3), `IOQDL` (deadline/switch L01/L02),
`IOQI01` (fixture độc lập + SNAP của I01), `IO-HWTEST`/`IO-SNAP` (READ thật).

---

## 7. Ma trận kiểm thử tuần 4 và trạng thái

Đối chiếu kế hoạch tuần 4 §14. Cột "Tuần 4" chỉ ghi những gì **đã chạy được trên
revision/đường dẫn được dẫn**; còn lại **NOT RUN** và không được cộng log tuần 3.

| Nhóm test | Tối thiểu | Chủ trì | Trạng thái trên nhánh Hiếu |
| :--- | :--- | :---: | :--- |
| W3 carry-over | SCAN 10 ca + unlink; 3 mutant; FCFS/SCAN real CPU1/4; pool16/2chain | H01 + Lợi | Mock SCAN PASS + mutant (log tuần 3/Lợi); **SCAN real chưa chạy ở nhánh này → NOT RUN** |
| Deadline xác định | Expired-first; không expired; tie expiry/seq; batch boundary; request cũ giữa luồng mới | L01 + I01 | **PASS** mock CPU1/4 (`results/week04/oracle-hieu/...`) |
| Thời gian/EAGAIN | Fake clock trước/đúng/sau expiry; wrap; EAGAIN không đổi age/head/batch/trace | I01 | **PASS** mock CPU1/4 |
| Runtime switch | 6 chiều 3 policy; Q>0 và I>0; empty; invalid; no-op; switch rồi EAGAIN | L02 + I01 | **PASS** mock CPU1/4 (oracle I01 độc lập) |
| Negative controls | ≥2 mutant deadline/switch bị bắt; fixture sai byte; thiếu PASS/timeout phải FAIL | I01 + H02 | **PASS**: 6 mutant EXPECTED_FAIL; fixture sai byte có log FCFS (Lợi); timeout/thiếu marker phát hiện qua oracle |
| Stress ngắn | 4×120 READ, 5 boot CPU1 + 5 CPU4, checksum + drain | H02 | **NOT RUN** ở nhánh này (Lợi mới smoke 1+1 boot) |
| Máy thứ hai | Cùng final revision; 3 policy × CPU1/4; oracle + switch có tải | H02; Lợi/Hiếu chạy | **NOT RUN** (chưa có revision cuối) |
| Final regression | FCFS 20 boot; SCAN/deadline mỗi CPU1/4; 6 case production; hooks vắng | G02 | **NOT RUN**; FCFS real 10+10 boot đã có từ nhánh Lợi (tham chiếu, chưa phải final) |

---

## 8. Câu hỏi cần GV xác nhận (PENDING)

Không câu nào dưới đây được coi là "GV đã duyệt". Giữ nguyên Pending của PTO-7.

| # | Câu hỏi | Ảnh hưởng | Trạng thái |
| :---: | :--- | :--- | :---: |
| Q1 | Tag/commit xv6 chính thức | pin/môi trường | **PENDING** |
| Q2 | Async WRITE có bắt buộc? | phạm vi tuần 5+ | **PENDING** |
| Q3 | API kernel hay syscall user? | API/demo | **PENDING** |
| Q4 | SCAN hay LOOK là yêu cầu chính thức? | policy baseline | **PENDING** |
| Q5 | RUBRIC 40/35/25 có áp dụng? | phạm vi học phần | **PENDING** |
| Q6 | Merge READ mức thiết bị / max 4 block? | I02, tuần 5 | **PENDING** |
| Q7 | Có được tăng `NUM` descriptor? | capacity/merge | **PENDING** |
| Q8 | Coherence với buffer cache/`bread`? | merge/READ thật | **PENDING** |

---

## 9. File, owner và thứ tự tích hợp

| Hạng mục | File | Owner | Reviewer | Trạng thái |
| :--- | :--- | :---: | :--- | :--- |
| Contract tuần 4 | `docs/week04/interface.md`, `measurement.md`, `evidence-index.md` | Hiếu (G01) | Hoàng, Lợi | ✅ soạn; review **PENDING** |
| Deadline + switch | `kernel/io_queue.c`, `kernel/io_queue_test.c/h`, `kernel/io_request.h/c` | Lợi (L01/L02) | Hoàng (IRQ), Hiếu (API/counters) | ✅ có code + evidence Lợi; review **PENDING** |
| Snapshot/latency + oracle | `kernel/io_request.h/c`, `kernel/virtio_disk.c` (helper), `tests/cases/ioq_w4_model.py`, `ioq_deadline.py`, `ioq_policy_switch.py`, `scripts/check-week04-oracle-hieu.py` | Hiếu (I01) | Lợi (rules), Hoàng (lock/timing) | ✅ code + evidence; review **PENDING** |
| Merge/lifecycle design | `docs/week04/merge-lifecycle-design.md` | Hiếu (I02) | Hoàng (DMA), Lợi (ordering) | ✅ thiết kế; review **PENDING** |
| READ thật/stress | `kernel/io_hw_test.c`, harness H01/H02 | Hoàng | Hiếu (snapshot/oracle) | ⏳ code harness có; acceptance **NOT RUN** |
| Báo cáo/demo | `docs/week04/report-hieu.md`, báo cáo nhóm + demo | Lợi (G03) + cả nhóm | cả nhóm | ⏳ Hiếu xong phần cá nhân |

Thứ tự: G01 → (L01 deadline, I01 oracle/snapshot song song) → L02 switch → H01 READ
thật → H02 stress/máy hai → G02 → G03. Mọi thay đổi API sau đó phải cập nhật
contract + test trong cùng PR.

---

## 10. Review và nghiệm thu

### 10.1 Bảng xác nhận trên cùng revision

| Người | Phần xác nhận | Trạng thái |
| :--- | :--- | :---: |
| Hiếu | Contract D21–D27, snapshot/kế toán, oracle độc lập, I02 design | ✅ đã soạn trên `360b4df`/`4fa4de9` |
| Hoàng | Driver/IRQ/lock, thứ tự khoá `test_lock → io_lock`, timing | ⏳ **PENDING** |
| Lợi | Queue/ordering, deadline rules, switch state transition, oracle rules | ⏳ **PENDING** |

### 10.2 Đối chiếu tiêu chí nghiệm thu card W4-G01

| # | Tiêu chí | Kết quả |
| :---: | :--- | :--- |
| 1 | Ba người xác nhận cùng header/contract; mỗi giả định có trạng thái + owner; thống nhất scope READ 1 block, pool 16, NUM=8, FCFS/SCAN/deadline | ✅ tài liệu này + §9 (owner/trạng thái); **chờ 2 review** |
| 2 | Danh sách thiếu evidence có người xử lý; công thức kế toán và thông số stress khớp code; không claim "GV đã duyệt" thiếu nguồn | ✅ [`evidence-index.md`](evidence-index.md) §4 (NOT RUN + owner); D23/D26 khớp code; Q1–Q8 **PENDING** |

---

## 11. Bằng chứng và cách tái lập

```bash
# Trên máy WSL2/Ubuntu có riscv64-linux-gnu- và QEMU >= 7.2:
git switch week4/hieu-contract-oracle
git log --oneline -3        # 4fa4de9 (evidence) / 360b4df (code I01) / 0dc296e (L01/L02)
TOOLPREFIX=riscv64-linux-gnu- python3 scripts/check-week04-oracle-hieu.py
TOOLPREFIX=riscv64-linux-gnu- python3 scripts/check-week04-policy.py   # harness L01/L02
make clean && make TOOLPREFIX=riscv64-linux-gnu-        # production restore
python3 scripts/check_text.py && git diff --check
```

Evidence I01: `results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/`
(`meta.json`, `summary.md`, log CPU1/4, mutant, `hw-cpus1-snap.log`, `source.patch`).
Evidence L01/L02: `results/week04/policy-mock/haree-20261115-035243/`,
`scan-regression/`, `fcfs-regression/`, `stress-smoke/`. Tổng hợp:
[`evidence-index.md`](evidence-index.md).

---

## 12. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-15 | base `0dc296e`, I01 `360b4df` | Tạo contract tuần 4: D21–D27; sửa counter/gauge theo phần 13 kế hoạch; chốt fixture/oracle/mutant; ma trận test + evidence index. |
| 2026-11-15 | `4fa4de9` | Gắn evidence I01 (oracle độc lập CPU1/4, 6 mutant EXPECTED_FAIL, READ thật + IO-SNAP, production restore). |
