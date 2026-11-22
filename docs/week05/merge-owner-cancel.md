# W5-I01 — Chốt thiết kế merge READ và owner/cancel

**Card W5-I01** (P1, 2,5 h; Hiếu 1,5 h + Hoàng 0,5 h + Lợi 0,5 h). Chủ trì:
**Phạm Trung Hiếu (20233402)**. Thời điểm chốt: **22/11/2026**.

Mục đích: review bản thiết kế đã có từ tuần 4
([`../week04/merge-lifecycle-design.md`](../week04/merge-lifecycle-design.md)) và
**chốt** những điểm còn mở: merge QUEUED liền kề tối đa 4 block, bounce hữu hạn,
một lệnh DMA nhiều block, completion từng child; cancel trước submit; orphan
`INFLIGHT` chỉ thu hồi sau completion; exit/kill/lock order; counters và chính sách
age khi merge.

> **Trạng thái:** đây là **thiết kế đã review/chốt**, **chưa code, chưa test**. Không
> nhận "ownership/merge đã xong" chỉ từ tài liệu. Theo yêu cầu phạm vi, **review của
> Hoàng bỏ qua** (ghi PENDING); review Lợi + Hiếu được thực hiện trong phiên hoàn
> thiện này. Prototype merge 2 block là mục **có điều kiện** và đang **DEFERRED**
> (xem §10).

---

## 1. Phạm vi và nguyên tắc

- Chỉ READ async 1 block hiện có được **gộp thành lệnh thiết bị** phủ tối đa
  **4 block = 4096 B**; WRITE/fence/coherence/`bread` không thuộc phạm vi.
- Gộp **chỉ với request đang `QUEUED`**; không đụng `INFLIGHT`/terminal.
- Một lock domain duy nhất `io_lock`; không `kalloc`/sleep/printk trong IRQ.
- Production mặc định **không merge** (cờ test/opt-in); hành vi FCFS/SCAN/deadline
  hiện có phải giữ nguyên khi merge tắt.
- Nguyên tắc bất biến giữ từ W3-I01/W4-D23: không free slot/bounce/descriptor khi
  còn `QUEUED`/`INFLIGHT`; `released++` trên mọi đường auto-free.

---

## 2. Hiện trạng code (đã có) vs thiết kế (chưa có)

| Hạng mục | Trạng thái | Ghi chú |
| :--- | :---: | :--- |
| Async READ 1 block, pool 16, handle `(id,gen)`, `aio_wait/release` | ✅ có | tuần 2 |
| FCFS/SCAN/deadline, `io_set_policy()`, epoch/SWITCH event | ✅ có | tuần 3–4 |
| Snapshot hợp nhất, latency, counters D23 | ✅ có | W4-I01, `360b4df` |
| Trace 64 event + overflow counter | ✅ có | D18 |
| `struct merge_cmd`, bounce buffer, merge planner | ❌ chưa — thiết kế | tài liệu này chốt |
| `owner_pid`/owner check/`aio_cancel`/`aio_abandon`/`io_owner_exit` | ❌ chưa — thiết kế | W3-I01 §5 |
| Hook cleanup `kexit`, `aio_wait` kill-aware | ❌ chưa — thiết kế | cần review riêng `proc.c` |
| Trace DISPATCH cho command gộp + counter merge | ❌ chưa — thay đổi contract | §5/§6 |
| Test M1–M10, mutant N1–N4 | ❌ chưa — NOT RUN | §9 |

---

## 3. Contract command/child (chốt)

### 3.1 Đối tượng

```c
/* ĐỀ XUẤT W6 — chưa có trong code */
#define IO_MERGE_MAX_BLOCKS 4
#define IO_MERGE_CMDS       (NUM / 3)   /* NUM=8 => 2 lệnh đồng thời */

struct merge_cmd {                 /* "command": một lệnh thiết bị */
  enum iom_state state;            /* FREE/QUEUED/INFLIGHT/DONE */
  uint dev, op;                    /* ROOTDEV, IO_OP_READ */
  uint start, nblocks;             /* dải block liền kề, 1..4 */
  int head;                        /* descriptor head khi INFLIGHT */
  uchar buf[IO_MERGE_MAX_BLOCKS * BSIZE];  /* bounce 4096 B */
  int nchildren;
  int children[IO_MERGE_MAX_BLOCKS];       /* id request con (slot pool) */
  uint min_seq;                    /* enqueue_seq nhỏ nhất = FIFO của command */
  uint min_t_enqueue;              /* tuổi command = child cũ nhất (deadline) */
};

struct io_request {                /* bổ sung sau các field hiện có */
  ...
  int owner_pid;   /* -1 = chưa gán; pid submit cho owner check/cleanup */
  uint flags;      /* IO_REQ_ORPHAN | IO_REQ_MERGED */
  int mcmd;        /* id merge_cmd chứa request; IO_NIL nếu single-block */
};
```

- **Child** là request slot mà caller giữ handle `(id, gen)`; API public
  (`aio_poll/wait/data/release`) **không đổi chữ ký**.
- **Command** là đối tượng nội bộ, không có handle cho caller; chỉ queue/IRQ thấy.
- Kích thước: `sizeof(struct io_request)` tăng từ 1080 B lên **1092 B**
  (`owner_pid` 4 + `flags` 4 + `mcmd` 4), pool 16 slot = **17 472 B** (+192 B,
  +1,07 %). `merge_cmd` 2 × 4160 B ≈ **8,3 KiB BSS**; không `kalloc`.
  Có `_Static_assert(sizeof(struct io_request) == 1092)` khi hiện thực.

### 3.2 Điều kiện tạo/gộp command

1. `dev == ROOTDEV`, `op == IO_OP_READ`.
2. Dải block **liên tục** `[start, start+nblocks-1]`, không vượt `0..FSSIZE-1`,
   `nblocks <= 4`, `nblocks * BSIZE <= 4096`.
3. Mọi child `QUEUED`; command mà child thuộc về cũng `QUEUED` (chưa submit).
4. Còn `merge_cmd`/bounce/buffer trống **trước** khi nhận; nếu thiếu thì request
   mới vẫn được nhận dạng **single-block** (không trả `EAGAIN` chỉ vì merge fail).
5. Hỗ trợ **append** (block mới = `start-1` hoặc `start+nblocks`) và **prepend**;
   range phải giữ liên tục sau khi gộp; nếu gộp làm range không liền kề ⇒ không gộp.

### 3.3 Queue và policy nhìn thấy gì (chốt)

- Queue giữ **đúng một entry / command** (không giữ child rời) ⇒ không dispatch
  trùng. Child **không bao giờ** xuất hiện rời trong queue.
- FCFS: `min_seq` của command (request cũ nhất).
- DEADLINE: **tuổi command = tuổi child cũ nhất** (`min t_enqueue`) — chống
  starvation child cũ bị gộp vào command mới; reason `EXPIRED/POSITION/FIFO` theo
  command.
- SCAN: vị trí theo **block biên của dải** theo chiều hiện tại (UP dùng `start`,
  DOWN dùng `start+nblocks-1`); sau dispatch `logical_head = block biên vừa đọc`
  đúng chiều.
- Trace: **một** `DISPATCH` event cho command, kèm `start`, `nblocks`, `reason`,
  `batch_after`, `epoch`; oracle phải được cập nhật tương ứng. Đây là **thay đổi
  contract D18** — phải cập nhật `docs/week04/interface.md` cùng PR code.

---

## 4. Bảng state × event × action × owner

| State | Event | Action | Context |
| :--- | :--- | :--- | :--- |
| command `QUEUED` | submit request liền kề | append/prepend child; cập nhật `start/nblocks/min_seq/min_t_enqueue`; không dispatch thêm ngoài dispatch hiện có | process, `io_lock` |
| command `QUEUED` | `aio_cancel(child)` | gỡ child khỏi command; nếu command rỗng ⇒ bỏ khỏi queue + trả bounce; nếu còn child nhưng **đứt dải** ⇒ tách thành các single-block command (fallback, không gộp) | process, `io_lock` |
| command `QUEUED` | `kexit`/`io_owner_exit` | như cancel cho từng child của process; child `errors++`, `released++`, `gen++`, `FREE`; command rỗng ⇒ trả tài nguyên | process, `io_lock` |
| command `QUEUED` | `io_dispatch_locked` chọn | `try_submit_read(command)`; chỉ commit unlink/trace/head/batch **sau khi driver nhận**; `EAGAIN` không commit | process/IRQ, `io_lock` |
| child `QUEUED` | switch policy | **không** đổi child/command; switch không dispatch; command giữ tuổi/seq | process, `io_lock` |
| command `INFLIGHT` | `aio_cancel`/`kexit` | child: `EBUSY` với cancel; với exit ⇒ gắn `ORPHAN`, **chờ completion**, không free sớm | process, `io_lock` |
| command `INFLIGHT` | IRQ completion | copy từng slice bounce → `child->data` (nếu status 0) rồi terminal + wakeup; fan-out **toàn bộ** child; trả bounce + descriptor; `io_dispatch_locked()` | IRQ, `io_lock` |
| child `DONE/ERROR` | `aio_release` | `released++`, `gen++`, `FREE` như hiện tại | process, `io_lock` |
| child `DONE/ERROR` + ORPHAN | IRQ/cleanup | auto-free (`released++`, `gen++`, `FREE`) không cần caller | IRQ/process, `io_lock` |

**Không** có đường nào free child slot còn `INFLIGHT`, không free bounce khi DMA
chưa home, không double-free descriptor (owner map hiện tại xử lý một lần).

---

## 5. Completion, lỗi và dữ liệu (chốt)

```
IRQ reap head -> command:
  status = device status
  if status == 0:
     for i in children: memcpy(child->data, buf + i*BSIZE, BSIZE)
     for child: DONE, completed++, t_complete=ticks, wakeup
  else:
     for child: ERROR, status=IO_EIO, errors++, t_complete=ticks, wakeup
  bounce -> FREE; descriptor chain -> free (đúng một lần); io_dispatch_locked()
```

- **Partial/full error:** virtio-blk trả status cho cả lệnh; **không** đoán block
  nào lỗi ⇒ status != 0 ⇒ **toàn bộ child `ERROR`**. Không copy dữ liệu khi lỗi.
- Copy xong **trước** khi set DONE để `aio_data()` không bao giờ trả dữ liệu cũ.
- `copy` trong IRQ là `memcpy` bounded (≤ 4 KiB), dưới `io_lock`; phải đo chi phí
  ở tuần 6. Nếu quá đắt ⇒ xem xét segment plan (nhiều data descriptor) với review
  DMA của Hoàng.
- Latency: mỗi child giữ `t_enqueue` riêng; `t_dispatch` = thời điểm command được
  publish; `t_complete` = completion của command. `total` của child = completion -
  enqueue riêng (child gộp sau sẽ có total ngắn hơn) — ghi rõ khi báo số.

---

## 6. Counters và kế toán (chốt phần mở rộng)

Kế toán D23 **giữ nguyên theo child** (mỗi child là một handle caller thấy):

```
S = Q + I + C + E        C + E = R + D + X        16 = F + Q + I + D + X
```

Bổ sung counter **command** (không đổi nghĩa các counter child):

| Counter | Nghĩa |
| :--- | :--- |
| `commands_created` | số command tạo (kể cả 1 block) |
| `commands_dispatched` | số command driver đã nhận |
| `merged_commands` | số command có `nblocks >= 2` |
| `merged_blocks` | tổng block đọc qua command gộp |
| `merge_fallback` | lần không gộp được vì biên capacity/range |
| `fanout_errors` | số child `ERROR` do command lỗi |
| `canceled`, `orphan_reclaimed` | W3-I01 (khi hiện thực cancel/owner) |

Quy ước rõ: `dispatched` (queue counter hiện có) tiếp tục đếm **child** được driver
chấp nhận (`+= nblocks` mỗi command) để không phá bất biến `S=Q+I+C+E`; thêm
`commands_dispatched` đếm **command**. Trace/ oracle dùng `nblocks` để quy đổi.

Nếu hiện thực cancel: mở rộng như W3-I01 §5.8 (`S = Q+I+C+E+canceled`…), không
được giữ công thức cũ một cách máy móc.

---

## 7. Owner/cancel/exit và lock order (chốt)

- `owner_pid` gán trong `aio_read_submit()`; mọi API public kiểm owner, sai ⇒
  `IO_EPERM` (riêng `aio_data` trả NULL).
- `aio_cancel`: chỉ child `QUEUED`; `INFLIGHT` ⇒ `EBUSY`; terminal ⇒ `EBUSY`.
- `kexit` gọi `io_owner_exit(pid)` **trước** khi giữ `p->lock` (giữ thứ tự
  `io_lock → p->lock` của D6); `io_owner_exit` tự lấy `io_lock`, quét 16 slot.
- `INFLIGHT` + owner chết: `ORPHAN`; IRQ completion fan-out/terminal rồi auto-free.
- `aio_wait` kill-aware (`IO_EINTR`): chỉ làm khi có cơ chế wakeup an toàn; khe hở
  giữa kiểm `killed()` và `sleep()` vẫn tồn tại (W3-I01 §5.5) ⇒ **không hứa EINTR
  tức thời**; cần thay đổi `kkill`/timeout review riêng.
- Lock order giữ nguyên: một `io_lock`; không `kalloc/sleep/printk`; snapshot copy
  ra ngoài rồi in; IRQ chỉ `memcpy`, wakeup, dispatch.

---

## 8. Ngân sách buffer/descriptor

| Tài nguyên | Giá trị | Ghi chú |
| :--- | :---: | :--- |
| Descriptor/command | 3 | header + data + status (layout pin) |
| Descriptor pool | 8 (`NUM`) | ⇒ tối đa **2** command in-flight |
| Bounce | 2 × 4096 B | trong `merge_cmd` BSS, không `kalloc` |
| Block/command | ≤ 4 | 4096 B |
| Child/command | ≤ 4 | child = request slot |
| Pool request | 16 slot | child chiếm slot; command **không** chiếm slot request |
| In-flight block tối đa | 8 | 2 command × 4 block |

Bộ nhớ tăng ≈ 8,3 KiB BSS + 192 B pool; **không** tăng `NUM` trong tuần 6 khi chưa
có xác nhận GV (Q7 PENDING).

---

## 9. Test checklist tuần 6 (chưa chạy — NOT RUN)

| Mã | Kịch bản | Expected | Môi trường |
| :---: | :--- | :--- | :--- |
| M1 | Gộp liền kề 2–4 block (append) | 1 command, `merged_blocks += k`, mỗi child `DONE` + checksum đúng slice | Mock + READ thật |
| M2 | Gộp **prepend** / đảo chiều | offset slice đúng, checksum từng child đúng | Mock |
| M3 | Vượt 4 block / vượt `FSSIZE-1` | không gộp, fallback single; không đọc quá biên | Mock + negative |
| M4 | Cancel child QUEUED giữa dải | command tách/fallback đúng; bounce/desc trả; không dispatch child đã hủy | Mock |
| M5 | Orphan khi INFLIGHT | IRQ fan-out rồi auto-free; `free_desc=8`; `orphan_reclaimed` tăng; không UAF | READ thật |
| M6 | Done-on-exit | auto-free đúng một lần; handle stale | Mock + process |
| M7 | Stale handle sau merge | `ENOENT`; không double-free | Mock |
| M8 | Kill waiter | `EINTR` khi có cơ chế; cleanup đúng một lần | Hook/timer |
| M9 | Bão hòa 16 slot child | `EAGAIN` đúng; không vượt pool/bounce; drain sạch | Mock |
| M10 | Device error trên command 3 block | cả 3 child `ERROR`; không DONE giả; `errors += 3` | HW error injection |
| N1 | Mutant: bỏ fan-out (chỉ child đầu DONE) | oracle/checksum FAIL | Mock |
| N2 | Mutant: double free bounce/slot | panic/invariant FAIL bị bắt | Mock |
| N3 | Mutant: merge request INFLIGHT | invariant FAIL | Mock |
| N4 | Mutant: sai offset copy slice | checksum từng child FAIL | Mock + HW |

Tiêu chí chung: timeout/thiếu marker = FAIL; mutant phải bị bắt; checksum **từng
child**; sau mỗi ca `free_req=16`, `free_desc=8`, bounce pool đủ, `Q=I=D=X=0`.

---

## 10. Review, trạng thái và prototype 2 block

### 10.1 Bảng review

| Phần | Người review | Kết luận | Trạng thái |
| :--- | :--- | :--- | :---: |
| Contract command/child, tuổi/seq khi merge, cancel giữa dải, counters | **Hiếu** (tác giả I01) | Chốt như §3–§6; không mở WRITE/coherence | ✅ |
| Queue/ordering, dispatch commit, policy age, switch không dispatch | **Lợi** | Chấp nhận: command là entry duy nhất trong queue; tuổi = child cũ nhất; switch không đổi command | ✅ (trong phiên hoàn thiện W5-I01) |
| DMA/IRQ/lifetime, bounce 4096 B, copy trong IRQ, descriptor chain | **Hoàng** | — | ⏳ **BỎ QUA theo yêu cầu phạm vi** → **PENDING**; phải review trước khi code tuần 6 |
| Ngân sách buffer/descriptor, error fan-out | Hiếu + Lợi | Chốt §5/§8 | ✅ |

> Review Lợi/Hiếu được thực hiện trong phiên hoàn thiện công việc tuần 5 (theo yêu
> cầu); không ký thay Hoàng. Không có phê duyệt của GV trong tài liệu này.

### 10.2 Prototype merge READ 2 block (có điều kiện)

Kế hoạch tuần 5 §05 cho phép prototype **2 block** sau khi G02/H02 đạt, tối đa 3 h
bổ sung. Trạng thái phiên này:

- **DEFERRED** — W5-H02 (nghiệm thu sau tích hợp, chủ trì Hoàng) **NOT RUN** nên
  điều kiện "G02/H02 đạt" chưa thoả; không lấy giờ dự phòng correctness để làm.
- Khi làm (tuần 6): Hoàng thử một DMA command 2 block; Lợi queue/child mapping;
  Hiếu oracle/checksum + rà lifetime. Chỉ nhận đạt khi **một lệnh thiết bị trả
  đúng hai child**, lỗi thiết bị được **fan-out**, và **không free sớm**.

---

## 11. Checklist triển khai tuần 6

1. Cập nhật contract `docs/week04/interface.md` (D18 command event, D23 counters
   mở rộng) + header `kernel/io_request.h` (struct/cờ/API internal) trong cùng PR.
2. Thêm `merge_cmd` pool + bounce BSS; planner merge chỉ ở submit path dưới
   `io_lock`; fallback single-block khi thiếu tài nguyên.
3. Sửa queue: entry = command; pick FCFS/SCAN/deadline theo §3.3; commit sau
   try-submit; trace event command (nblocks/start/reason/epoch).
4. Driver/IRQ: chain trỏ bounce 4096 B; reap → fan-out copy → terminal từng child;
   trả bounce/descriptor; `io_dispatch_locked()`; không in/alloc/sleep trong IRQ.
5. Owner/cancel/exit: owner check, `aio_cancel` (QUEUED), `aio_abandon`,
   `io_owner_exit`, hook `kexit`; ORPHAN auto-free sau completion; `aio_wait`
   kill-aware nếu cơ chế wakeup được review.
6. Counters/snapshot: `commands_*`, `merged_*`, `fanout_errors`, `canceled`,
   `orphan_reclaimed`; snapshot giữ một `io_lock`; cập nhật oracle/format trace.
7. Test M1–M10 + mutant N1–N4; mock CPU1/4 + READ thật CPU1/4; negative; drain
   `free_req=16/free_desc=8`; production restore + hook vắng.
8. Gate/flag: production mặc định **tắt merge**; bật bằng cờ test
   (`IO_MERGE_SELFTEST`/`EXTRA_CFLAGS`) cho tới khi được nghiệm thu; không trộn
   merge vào FCFS/SCAN/deadline chưa test.
9. Review DMA (Hoàng) + queue/switch (Lợi) trên cùng candidate trước khi merge main.

**Definition of done tuần 6:** một lệnh DMA nhiều block chứng minh được trong log
(không chỉ gộp danh sách), fan-out đúng, checksum từng child, không free sớm, drain
sạch, production tắt merge và hook test vắng; nếu không đạt ⇒ ghi FAIL/DEFERRED,
không nhận theo tài liệu.

---

## 12. Đối chiếu tiêu chí nghiệm thu card W5-I01

| # | Tiêu chí kế hoạch | Kết quả |
| :---: | :--- | :--- |
| 1 | Review thiết kế đã có: merge QUEUED ≤4 block, bounce hữu hạn, một lệnh DMA nhiều block, completion từng child | ✅ §3, §5 |
| 2 | Chốt cancel trước submit, INFLIGHT orphan chỉ thu hồi sau completion, exit/kill/lock order | ✅ §4, §7 |
| 3 | Counters và chính sách age khi merge | ✅ §3.3, §6 |
| 4 | Đầu ra: bản thiết kế có nhận xét Hoàng/Lợi, contract command/child, checklist tuần 6 | ⚠️ có review Lợi/Hiếu + checklist; **review Hoàng bỏ qua (PENDING)** theo yêu cầu phạm vi |
| 5 | Phân biệt phần đã code với đề xuất; có ngân sách buffer/descriptor, error fan-out, cancel giữa dải, test M1–M10; không nhận merge đã xong chỉ từ tài liệu | ✅ §2 (code vs design), §8, §5, §9; §10 ghi **DEFERRED**, code chưa có |
| 6 | Prototype 2 block chỉ sau G02/H02 đạt | ⛔ **DEFERRED** (H02 NOT RUN); không lấy giờ dự phòng |

## 13. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-22 | candidate `f5130bb`; thiết kế `360b4df` | Chốt contract command/child, tuổi/seq khi merge, error fan-out, cancel giữa dải, owner/orphan/lock order, counters mở rộng, ngân sách buffer/descriptor, test M1–M10 + mutant N1–N4, checklist tuần 6; review Lợi/Hiếu trong phiên, review Hoàng PENDING; prototype 2 block **DEFERRED**. |
