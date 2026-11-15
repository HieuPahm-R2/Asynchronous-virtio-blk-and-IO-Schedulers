# W4-I02 — Thiết kế merge READ ở mức thiết bị và owner/cancel

**Card W4-I02 (P2 mở rộng, 2 h, sau core).** Tài liệu này là **thiết kế**, **chưa
code, chưa chạy test**. Nó chuẩn bị cho tuần 5 và **không** đưa thay đổi DMA/`kexit`
lớn vào cuối tuần 4 khi scheduler/switch chưa ổn định.

Owner: **Phạm Trung Hiếu (20233402)**. Reviewer: **Hoàng** (đường DMA/IRQ, lock) và
**Lợi** (queue/ordering, policy). Trạng thái: **DEFERRED** — nếu core tuần 4 trễ,
toàn bộ card ghi DEFERRED, không nhận đạt chỉ vì copy lại `lifecycle-review.md`
tuần 3.

Đọc kèm: [`../week03/lifecycle-review.md`](../week03/lifecycle-review.md) (rà soát
K1–K10 + owner/orphan/cancel đề xuất), [`interface.md`](interface.md) D21–D27,
[`../week02/interface.md`](../week02/interface.md) (D2/D5/D7: buffer ownership,
handle, completion).

---

## 1. Phạm vi

### 1.1 Trong phạm vi (chỉ thiết kế)

- Merge **nhiều READ liền kề** thành **một lệnh thiết bị**, tối đa **4 block =
  4096 byte**, cùng device/op/ordering-domain, chỉ với request đang **`QUEUED`**.
- Hỗ trợ **append/prepend** vào một lệnh đã có trong queue; tính **biên capacity**
  (pool, descriptor, buffer, block range) **trước khi chấp nhận**.
- Bounce buffer hữu hạn **hoặc** segment plan có giới hạn; mô tả **một lệnh thiết bị
  phủ nhiều block** và **fan-out completion** cho từng handle.
- Định nghĩa **master/child ownership**, lỗi partial/full, cancel **trước** submit,
  con trỏ dữ liệu và **release đúng một lần**.
- Rà lại owner/orphan/cancel trên đường `kexit`/`kkill` của xv6 pin (kế thừa K1–K10).
- Test checklist cho tuần 5 (chưa chạy).

### 1.2 Ngoài phạm vi

- **Không code** trong tuần 4 (kể cả merge hay owner check).
- Async WRITE, fence/flush, `NUM = 32/64`, syscall user đầy đủ, coherence với
  `bread()`, LOOK — là các thay đổi riêng, cần test/ngân sách riêng.
- Không hứa `IO_EINTR` tức thời khi kill: cần cơ chế wakeup an toàn (xem §6.3).

### 1.3 Tiêu chí "không được gọi là đã merge"

Chỉ **gom danh sách** request rồi vẫn phát **từng READ riêng** thì **không** phải
device merging; phải chứng minh **một lệnh thiết bị** (một head/chain DMA) phủ
nhiều block, bằng trace/counters của driver. Không đạt tiêu chí này thì ghi
"merge-lite (userspace-like batch), chưa phải device merge".

---

## 2. Hiện trạng kế thừa (code đã có tới `360b4df`)

| Thành phần | Hiện trạng | Hệ quả cho merge |
| :--- | :--- | :--- |
| Async API | `aio_read_submit/poll/wait/release/data`; 1 block = 1024 B; handle `(id, gen)` | Handle không đổi khi merge: mỗi child vẫn là 1 request slot có handle riêng |
| Pool | 16 slot trong BSS, mỗi slot có `data[1024]`; generation chống stale | Master/child dùng chung pool; không `kalloc` |
| Driver | `virtio_disk_try_submit_read()` tạo chain **3 descriptor** (header/data/status), publish atomic; owner map head→`ASYNC/STOCK`; IRQ reap đúng một lần | Một command = 1 head = 3 descriptor; `NUM = 8` ⇒ tối đa **2** command in-flight |
| Queue | `kernel/io_queue.c`: FCFS/SCAN/deadline, `IO_EAGAIN` không commit, trace 64 event | Merge phải định nghĩa queue nhìn thấy master hay child (xem §4.4) |
| Switch | `io_queue_set_policy_locked()`/`io_set_policy()`; không đụng request | Merge không được đổi semantics switch |
| Lifecycle | owner/orphan/cancel **chỉ thiết kế** (W3-I01), chưa có `owner_pid`/cleanup | Merge tuần 5 phải làm **cùng** owner/cancel, không tách rời |
| Snapshot | `io_snapshot`: S/C/E/R, Q/I/D/X/F, counter queue/policy/driver, latency | Phải mở rộng counter cho merge (§5) |

Giới hạn giữ nguyên: một block = 1024 B; `ROOTDEV`; block `0..1999`; `NUM = 8`;
pool 16; không sleep/alloc/printk trong IRQ; không sửa request `INFLIGHT`.

---

## 3. Mô hình một lệnh thiết bị phủ nhiều block

### 3.1 Ràng buộc merge

Một **merge command** (`mcmd`) gom `k` READ liền kề (`1 <= k <= 4`):

1. Cùng `dev == ROOTDEV`, cùng `op == IO_OP_READ`.
2. Các block tạo thành **dải liên tục** `[start, start+k-1]`, không vượt
   `0..FSSIZE-1`; `k * BSIZE <= 4096`.
3. Tất cả request thành viên đang `QUEUED`; **không** gom request `INFLIGHT`,
   `DONE`, `ERROR`, `FREE`.
4. Tổng số child trong một `mcmd` `<= 4`; tổng `mcmd` đồng thời `<= 2`
   (`NUM/3 = 2` chain) — kiểm **trước** khi nhận, nếu không đủ thì giữ đường
   single-block.
5. Không merge qua biên thiết bị/`FSSIZE`; không merge hai request khác generation
   của cùng slot (generation chỉ là của slot, không phải block).
6. Chỉ READ; WRITE/fence/coherence có semantics riêng, **không** gộp vào đây.

### 3.2 Buffer: phương án A (chọn) — bounce buffer hữu hạn

- Mỗi `mcmd` sở hữu **một bounce buffer 4096 B** trong BSS:
  `struct merge_cmd` pool 2 phần tử ⇒ `2 × (4096 + metadata) ≈ 8,2 KiB` BSS,
  **không** `kalloc`.
- Device DMA ghi `k*1024` byte **liền mạch** vào bounce buffer; completion **copy
  từng slice 1024 B** vào `child->data[1024]` (staging buffer sẵn có của child),
  rồi mới đánh `DONE/ERROR` và `wakeup(child)`. Chi phí: `memcpy` tối đa 4 KiB trong
  IRQ, dưới `io_lock`, bounded — **phải đo** ở tuần 5; `memcpy` không sleep/alloc
  nhưng là chi phí thật, không được giấu.
- Điều kiện: bounce buffer và descriptor còn trống **trước khi** tạo `mcmd`.

**Phương án B (dự phòng, chưa chọn):** segment plan — chain nhiều data descriptor,
mỗi descriptor trỏ `child->data`. Ít copy hơn nhưng phức tạp chain/fence và giới hạn
`NUM`; chỉ dùng nếu đo thấy copy IRQ quá đắt và Hoàng review chain layout.

### 3.3 Descriptor/ngân sách

| Tài nguyên | Giá trị | Tính toán |
| :--- | :---: | :--- |
| Descriptor / command | 3 | header + data + status (layout pin hiện tại) |
| Descriptor pool | 8 (`NUM`) | ⇒ tối đa 2 command in-flight (khớp `max_inflight = 2`) |
| Block / command | ≤ 4 | `4 × 1024 = 4096 B` bounce |
| Child / command | ≤ 4 | child = request slot có handle riêng |
| Bounce buffer | 2 × 4096 B | BSS, mỗi command một buffer |
| Pool slot | 16 | child chiếm slot như hiện tại; master **không** chiếm slot request |
| In-flight block tối đa | 8 | 2 command × 4 block (software), dữ liệu DMA 8 KiB |

Merge **không** làm tăng `NUM`; capacity thực tế vẫn 2 chain. Lợi ích là **một**
lệnh cho nhiều block (giảm số command/IRQ), không phải tăng song song thiết bị.

---

## 4. Thiết kế dữ liệu và thuật toán

### 4.1 Cấu trúc đề xuất (chưa có trong code)

```c
/* ĐỀ XUẤT W4-I02/W5 — chưa hiện thực */
#define IO_MERGE_MAX_BLOCKS 4
#define IO_MERGE_CMDS       (NUM / 3)   /* 2 */

enum iom_state { IOM_FREE = 0, IOM_QUEUED, IOM_INFLIGHT, IOM_DONE };

struct merge_cmd {
  enum iom_state state;
  uint dev, op;
  uint start, nblocks;          /* dải block thiết bị */
  int head;                     /* descriptor head khi INFLIGHT */
  uchar buf[IO_MERGE_MAX_BLOCKS * BSIZE];  /* bounce buffer */
  int nchildren;
  int children[IO_MERGE_MAX_BLOCKS]; // id request con
  uint min_seq;                 /* enqueue_seq nhỏ nhất = FIFO của command */
  uint t_enqueue;               /* min t_enqueue của child (cho deadline) */
};

/* Bổ sung vào struct io_request (đề xuất) */
struct io_request {
  ...
  int owner_pid;   /* W3-I01: pid submit; -1 nếu không có */
  uint flags;      /* IO_REQ_ORPHAN, IO_REQ_MERGED */
  int mcmd;        /* id merge_cmd chứa request, IO_NIL nếu single */
  /* field cũ giữ nguyên thứ tự để không đổi layout driver đang dùng */
};
```

### 4.2 Vòng đời `mcmd`

```
FREE -> QUEUED -> INFLIGHT -> DONE -> (giải phóng bounce) -> FREE
```

- `QUEUED`: `mcmd` nằm trong queue đúng **một** entry; children **không** nằm trong
  queue (tránh double schedule). Children vẫn `QUEUED` ở tầng request layer.
- `INFLIGHT`: driver đã nhận head; chỉ IRQ được reap và fan-out.
- `DONE`: sau fan-out + copy; bounce trả về pool; children chuyển `DONE/ERROR` và
  chờ caller `aio_release` như hiện tại.
- Không có `mcmd` "DONE nhưng giữ bounce" — bounce không chia sẻ ra ngoài IRQ.

### 4.3 Khi nào merge (submit path, dưới `io_lock`)

```
aio_read_submit(dev, blockno):
  validate dev/blockno/handle như hiện tại
  nếu merge bật (build/opt-in) và có slot:
     thử gắn vào một mcmd QUEUED có dải liền kề (append hoặc prepend) và còn capacity
     nếu không, thử tạo mcmd mới gồm request này (+ các request QUEUED liền kề nếu có)
     nếu không đủ buffer/descriptor/range: fallback single-block như hiện tại
  enqueue + dispatch theo contract queue hiện có (không đổi)
```

Nguyên tắc: **không** chờ, **không** cấp phát động, **không** gộp request đã
`INFLIGHT`; nếu merge fail vì biên capacity thì request vẫn được nhận ở dạng
single-block (không trả `EAGAIN` chỉ vì merge fail).

### 4.4 Queue/policy nhìn thấy gì

- Queue giữ **một entry / mcmd`**, không giữ child rời. Vì vậy FCFS/SCAN/deadline
  chọn theo `mcmd`:
  - FCFS: `min_seq` của các child (request cũ nhất trong command).
  - DEADLINE: tuổi của **child cũ nhất** (`min t_enqueue`) — tránh starvation child
    cũ nằm trong command mới. Reason `EXPIRED/POSITION/FIFO` theo `mcmd`.
  - SCAN: vị trí theo chiều hiện tại là **block biên của dải**: UP dùng `start`,
    DOWN dùng `start+nblocks-1`. Sau dispatch, `logical_head = block biên vừa đọc`
    đúng chiều.
- `trace` ghi **một DISPATCH event cho `mcmd`** (kèm `nblocks`, `start`, `end`,
  reason, epoch) thay vì nhiều event giả cho child — nếu không oracle SCAN/deadline
  sẽ hiểu sai thứ tự. Đây là **thay đổi contract trace** phải chốt trước code.

### 4.5 Completion và fan-out

```
IRQ reap head -> mcmd:
  status = device_status
  nếu status == 0:
     với mỗi child i: memcpy(child->data, buf + i*BSIZE, BSIZE)
                      -> DONE, completed++, t_complete, wakeup(child)
  nếu status != 0:
     với mỗi child: ERROR, status = IO_EIO, errors++, wakeup(child)
  bounce -> FREE; descriptor chain -> free; state = FREE
  io_dispatch_locked()  (như IRQ hiện tại)
```

- **Partial/full error:** virtio-blk trả status cho cả request, không có thông tin
  từng block; nếu status != 0 thì **toàn bộ child** `ERROR` (không đoán partial).
- Không free child slot trong IRQ; child chờ `aio_release` như cũ.
- Copy xong **trước** khi set `DONE` để `aio_data()` không bao giờ trả dữ liệu cũ.

### 4.6 Chủ sở hữu, dữ liệu và release đúng một lần

| Đối tượng | Ai sở hữu | Khi nào giải phóng |
| :--- | :--- | :--- |
| Bounce buffer | `mcmd` | IRQ sau fan-out (state DONE→FREE) |
| Descriptor chain | driver/IRQ | IRQ reap, đúng một lần (owner map hiện tại) |
| Child `data[1024]` | request slot (BSS) | Slot về FREE khi caller `aio_release`; dữ liệu valid tới lúc đó |
| Child handle | caller | Caller `aio_release`; stale sau đó |
| `mcmd` entry | queue/IRQ | Queue khi dispatch xong; IRQ khi reap |

**Cấm:** free child/bounce/descriptor khi command còn `INFLIGHT`; free hai lần;
`aio_data()` trả con trỏ tới bounce buffer (bounce được tái sử dụng sau completion).

### 4.7 Cancel trước submit và owner/orphan

- **Cancel chỉ với child `QUEUED` và `mcmd` `QUEUED`**: `io_queue_remove_locked()`
  child khỏi `mcmd`; nếu `mcmd` hết child thì bỏ `mcmd` khỏi queue và trả bounce
  (chưa có DMA). Nếu còn child khác thì cập nhật `start/nblocks/min_seq`
  (có thể tách dải không liền kề ⇒ khi đó **không** merge nữa, fallback single).
- **Cancel sau khi `INFLIGHT`: `EBUSY`** — virtio-blk không có abort; không free slot.
- **Owner/orphan (kế thừa W3-I01 phương án A):** thêm `owner_pid` + kiểm owner ở
  mọi API; `kexit` gọi `io_owner_exit(pid)`:
  - child `QUEUED`: remove khỏi `mcmd`/queue, `errors++`, `released++`, `gen++`,
    `FREE`;
  - child `INFLIGHT`: set `ORPHAN`; IRQ completion vẫn fan-out/mark terminal, sau đó
    **auto-free** (`released++`, `gen++`, `FREE`) thay vì chờ caller;
  - child terminal: `released++`, `gen++`, `FREE`.
- Nếu `mcmd` mất hết child do cancel/orphan khi chưa INFLIGHT: trả bounce + slot
  `mcmd`, không dispatch rỗng.

### 4.8 Lock order và context

- Một lock domain duy nhất: `io_lock` (= `virtio_disk_io_lock()`). Merge planning,
  queue update, driver publish, IRQ fan-out đều dưới `io_lock`.
- Không acquire `p->lock` dưới `io_lock` theo chiều ngược: `kexit` gọi
  `io_owner_exit()` **trước** khi giữ `p->lock` (giữ thứ tự D6: `io_lock → p->lock`).
- IRQ: `memcpy` bounded, `wakeup`, không `printk/kalloc/sleep/copyinout`.
- Không giữ `io_lock` khi format/in log; snapshot copy ra ngoài rồi in.

---

## 5. Ảnh hưởng kế toán và counters

Kế toán D23 vẫn tính **theo child request** (`S/C/E/R`, `Q/I/D/X`) vì mỗi child là
một handle mà caller thấy. Bổ sung counter cho **command** (không thay nghĩa cột cũ):

| Counter mới (đề xuất) | Nghĩa |
| :--- | :--- |
| `commands_submitted` | số `mcmd` tạo thành công (kể cả 1 block) |
| `commands_dispatched` | số `mcmd` driver đã nhận |
| `merged_commands` | số `mcmd` có `nblocks >= 2` |
| `merged_blocks` | tổng block đã đọc qua command gộp |
| `merge_fallback` | submit không merge được vì biên capacity/range |
| `fanout_errors` | số child bị `ERROR` do lệnh gộp lỗi |
| `canceled` / `orphan_reclaimed` (từ W3-I01) | cancel/orphan như thiết kế tuần 3 |

Bất biến mở rộng (chưa cancel): `S = Q + I + C + E` vẫn đúng theo child;
`merged_blocks == Σ nblocks` của các command đã dispatch; `child_count ==
Σ nblocks`; sau drain `free_req = 16`, `free_desc = 8`, `Q=I=D=X=0`, bounce pool
về đủ 2. Nếu có cancel: mở rộng phương trình như W3-I01 §5.8 (thêm `canceled`).

---

## 6. Rà lại owner/orphan/cancel trên xv6 pin (kế thừa + bổ sung)

### 6.1 Điểm tựa hiện tại (đã rà ở W3-I01)

- `kkill` set `killed`, wake process đang `SLEEPING` ([`kernel/proc.c`](../../kernel/proc.c)).
- `usertrap()` kiểm `killed` trước/sau syscall, gọi `kexit` ([`kernel/trap.c`](../../kernel/trap.c)).
- `kexit()` chưa có hook dọn async request ([`kernel/proc.c`](../../kernel/proc.c)).
- `sleep_prepare/release/sleep/acquire` đóng cửa sổ lost-wakeup cho `aio_wait`,
  nhưng **kill không cắt được** `aio_wait` hiện tại (K1).

### 6.2 Bổ sung cho merge

| Sự kiện | Child `QUEUED` | Child `INFLIGHT` (trong `mcmd`) |
| :--- | :--- | :--- |
| `aio_cancel` | remove khỏi `mcmd`; nếu `mcmd` rỗng bỏ queue; `ERROR/-ECANCELED`; chờ release | `EBUSY` (không abort được) |
| `kexit`/`io_owner_exit` | remove + `errors++/released++/gen++/FREE` | `ORPHAN`; IRQ fan-out rồi auto-free |
| device error | — | toàn bộ child `ERROR`; `released++` theo đường orphan nếu có |
| waiter bị kill | `aio_wait` trả `IO_EINTR` (khi có cơ chế), `waiters=0` trước cleanup | giữ `ORPHAN` tới completion; không free sớm |

### 6.3 Khe hở còn lại (phải nói rõ)

Kill đến đúng khe giữa lần kiểm `killed()` và `sleep()` vẫn không được quan sát cho
tới khi I/O xong, vì `kkill` chỉ wake process đang `SLEEPING`. Muốn đóng hoàn toàn
cần (a) cho `kkill` wake cả kênh `p->chan` (rủi ro spurious wakeup toàn kernel),
hoặc (b) `aio_wait` có timeout hữu hạn — **cả hai phải review riêng**, không nằm
trong tuần 4/5 mặc định. Vì vậy **không hứa `IO_EINTR` tức thời**.

---

## 7. Test checklist tuần 5 (chưa viết — NOT RUN)

| Mã | Kịch bản | Expected (thiết kế) | Môi trường |
| :---: | :--- | :--- | :--- |
| M1 | Merge **liền kề** 2–4 block (cùng chiều) | 1 `mcmd`, `merged_blocks += k`, mỗi child `DONE` + checksum đúng slice | Mock + READ thật CPU1/4 |
| M2 | Merge **ngược chiều** (prepend/append) | Thứ tự dải đúng, checksum từng child đúng, không nhầm offset | Mock |
| M3 | **Vượt biên** `FSSIZE-1` / vượt 4 block | Không merge; fallback single-block; không đọc quá `FSSIZE` | Mock + negative |
| M4 | **Cancel khi `mcmd` QUEUED** | Child removed; `mcmd` rỗng bị bỏ; bounce/desc trả đúng; không dispatch | Mock |
| M5 | **Orphan khi INFLIGHT** | IRQ fan-out rồi auto-free; `free_desc=8`; `orphan_reclaimed` tăng; không UAF | READ thật |
| M6 | **Done-on-exit** | Child terminal auto-free; `released++`; handle stale | Mock + process context |
| M7 | **Stale handle** sau merge/release | `ENOENT`; không double-free; gen đúng | Mock |
| M8 | **Kill waiter** trong `aio_wait` | Trả `EINTR` khi có cơ chế, `waiters=0`; cleanup đúng một lần | Hook + timer |
| M9 | **Bão hoà 16 slot** (mỗi child chiếm slot) | `EAGAIN` đúng; merge không vượt pool/bounce; drain sạch | Mock |
| M10 | **Device error** trên `mcmd` 3 block | Cả 3 child `ERROR`, không child nào `DONE` giả; `errors += 3` | HW error injection |
| N1 | Mutant **bỏ fan-out** (chỉ child đầu DONE) | Oracle/checksum FAIL | Mock |
| N2 | Mutant **double free** bounce/slot | Panic hoặc invariant FAIL bị bắt | Mock |
| N3 | Mutant **merge request INFLIGHT** | Invariant FAIL (`INFLIGHT` không được đổi) | Mock |
| N4 | Mutant **sai offset** copy slice | Checksum từng child FAIL | Mock + HW |

Nguyên tắc: timeout/thiếu marker = FAIL; mutant phải bị bắt; checksum **từng child**,
không chỉ checksum tổng; sau mỗi ca kiểm `free_req=16`, `free_desc=8`, bounce pool
đủ, `Q=I=D=X=0`.

---

## 8. Ngân sách bộ nhớ và descriptor (đề xuất)

| Hạng mục | Hiện tại | Sau merge (đề xuất) | Tăng |
| :--- | :---: | :---: | :---: |
| Pool request | 16 × 1080 B = 17 280 B | 16 × (1080 + 8) = 17 408 B (owner_pid+flags) | +128 B (+0,74 %) |
| Merge command | 0 | 2 × (~4 160 B) ≈ 8 320 B | +8,1 KiB BSS |
| Bounce buffer | 0 | nằm trong `merge_cmd` (2 × 4096 B) | tính ở trên |
| Descriptor | 8 | 8 (không đổi) | 0 |
| Child field `mcmd` | 0 | +4 B/request = +64 B | +0,37 % |

Tổng BSS tăng khoảng **8,5 KiB** trên kernel hiện tại; không `kalloc`, không đổi
layout DMA cũ (field mới **append** sau `data`, driver không dùng). Cần
`_Static_assert(sizeof(struct io_request) == 1092)` khi hiện thực (nếu chọn owner_pid
+ flags + mcmd).

---

## 9. Rủi ro và câu hỏi review

| Rủi ro | Giảm thiểu / trạng thái |
| :--- | :--- |
| DMA ghi quá bounce buffer / sai length | Kiểm `k*BSIZE <= 4096` trước submit; assert trong try-submit; negative test M3/N4 |
| Copy 4 KiB trong IRQ đắt | Bounded, dưới `io_lock`; đo; nếu đắt chuyển segment plan B (review Hoàng) |
| Fan-out sai thứ tự/không đủ child | Fan-out trước khi set DONE; assert `nchildren == nblocks`; mutant N1 |
| Queue thấy child rời ⇒ dispatch trùng | Queue chỉ chứa `mcmd`; child không bao giờ ở queue; test M1/M9 |
| Policy SCAN/deadline sai vị trí/tuổi do gộp | Định nghĩa mcmd tuổi = child cũ nhất, vị trí = block biên (§4.4); oracle phải chạy lại |
| Cancel/orphan free sớm khi INFLIGHT | Cấm free `INFLIGHT`; orphan chỉ auto-free sau completion (W3-I01 §5.4) |
| Owner pid tái sử dụng | Ghi rủi ro; nếu cần chính xác chuyển owner pointer/refcount (W3-I01 phương án B) |
| Coherence với `bread()` khi block vừa đọc vừa ghi | Ngoài phạm vi; chỉ fixture read-only; cần quyết định tuần 5+ |

**Câu hỏi cho Hoàng (DMA/IRQ/lock):**

1. Một descriptor data length 4096 B có hợp lệ với layout chain hiện tại (không đổi
   header/status) trên QEMU virtio-blk legacy pin không?
2. Fan-out copy trong IRQ dưới `io_lock` có chấp nhận được về thời gian giữ khoá
   không, hay nên dùng segment plan (nhiều data descriptor)?
3. Có cần fence đặc biệt giữa DMA 4 KiB và copy slice không?
4. `_Static_assert` layout và owner map head→mcmd: thêm bảng hay tận dụng owner map?

**Câu hỏi cho Lợi (queue/ordering/switch):**

1. Queue giữ `mcmd` thay vì request có phá oracle SCAN/deadline tuần 4 hiện có
   không? Trace DISPATCH cho `mcmd` (kèm `nblocks`) có được chấp nhận là thay đổi
   contract D18 không?
2. Tuổi deadline của `mcmd` = child cũ nhất có đủ chống starvation không?
3. Cancel một child ở giữa dải: tách dải (fallback single) hay cấm cancel khi
   `mcmd` có >1 child?
4. Switch policy khi `mcmd` QUEUED/INFLIGHT: chỉ đổi policy, `mcmd` giữ nguyên —
   xác nhận không cần rollback head/batch.

---

## 10. Code nào đã có / thiết kế nào chưa (bàn giao)

| Hạng mục | Trạng thái | Ghi chú |
| :--- | :---: | :--- |
| Async READ 1 block, pool 16, handle, wait/release | ✅ **Đã có** | tuần 2 |
| FCFS/SCAN/deadline + runtime switch (kernel control) | ✅ **Đã có** | tuần 3–4 |
| Snapshot một khoá + latency aggregates | ✅ **Đã có** | W4-I01, commit `360b4df` |
| `owner_pid`/owner check/`aio_cancel`/`aio_abandon`/`io_owner_exit` | ❌ **Chưa — thiết kế** | W3-I01 §5; tuần 5 |
| Hook cleanup `kexit` | ❌ **Chưa — thiết kế** | cần review `proc.c` |
| `aio_wait` kill-aware (`IO_EINTR`) | ❌ **Chưa — thiết kế** | §6.3; cần cơ chế wakeup/timeout |
| `struct merge_cmd`, bounce buffer, merge policy | ❌ **Chưa — thiết kế** | tuần 5 |
| Trace DISPATCH cho `mcmd` + counter merge | ❌ **Chưa — thiết kế** | §4.4/§5, đổi contract D18/D23 |
| Test M1–M10 + mutant N1–N4 | ❌ **Chưa — NOT RUN** | §7 |
| Async WRITE/fence/syscall/coherence | ❌ **Backlog** | ngoài phạm vi |

---

## 11. Đối chiếu tiêu chí nghiệm thu card W4-I02

| # | Tiêu chí | Kết quả |
| :---: | :--- | :--- |
| 1 | Hoàng/Lợi review mô hình DMA và unlink/ordering; nêu rõ API nào đang có, API nào mới đề xuất | ✅ §2/§10 phân loại rõ; §9 câu hỏi review cho Hoàng/Lợi — **review PENDING** |
| 2 | Nếu core trễ, ghi DEFERRED toàn bộ I02; không nhận đạt chỉ vì copy lại lifecycle-review tuần 3 | ✅ trạng thái **DEFERRED** (thiết kế mới cho merge + tích hợp owner/cancel; không copy nguyên văn) |

---

## 12. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-15 | `360b4df` | Tạo thiết kế merge READ mức thiết bị (≤4 block/4096 B), bounce buffer hữu hạn, master/child ownership, fan-out completion, cancel/orphan/exit, lock order, ngân sách bộ nhớ, test M1–M10 + mutant N1–N4. Trạng thái DEFERRED, chưa code/test. |
