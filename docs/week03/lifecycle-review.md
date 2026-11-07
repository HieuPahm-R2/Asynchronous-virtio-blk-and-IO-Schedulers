# W3-I01 — Rà soát vòng đời request và thiết kế xử lý kill/cancel

> **Mã công việc:** W3-I01 (mã kế hoạch; không phải issue Jira mới) — *Rà vòng đời request và thiết kế xử lý kill cancel*.
> **Người thực hiện:** Phạm Trung Hiếu (MSSV: 20233402).
> **Reviewer:** Nguyễn Văn Hoàng — **PENDING** (review lifetime DMA; không thêm early-free vào `INFLIGHT`).
> **Base revision:** `49557bf671edb5ee4ccf6a2c3c452d32fd1f411e` (main, 2026-11-04). **Pin xv6:** `f780d785…`.
> **Tính chất card:** **thiết kế + rà soát**, **không triển khai** kill/cancel trong tuần 3.
> **Snapshot:** 2026-11-07.
> **Liên quan:** [`docs/week03/interface.md`](interface.md) (D13–D20), [`docs/week02/interface.md`](../week02/interface.md) (D1–D10),
> tiền đề cho API user sau này (PTO-7/Q3).

---

## 1. Phạm vi và phương pháp

Card này trả lời câu hỏi còn mở từ tuần 2: **điều gì xảy ra với request async khi
tiến trình gọi bị kill hoặc exit**, và **cần thiết kế gì trước khi mở API user**.
Phạm vi:

- **Trong phạm vi:** rà code hiện có trên `main` (`io_request.c`, `io_queue.c`,
  `virtio_disk.c`, `proc.c`, `trap.c`); lập bảng `state × event × action × owner`;
  đề xuất cơ chế owner/orphan và API cancel/abandon; đánh giá ngân sách bộ nhớ;
  liệt kê test cần viết; chỉ ra code nào đã có, thiết kế nào chưa triển khai.
- **Ngoài phạm vi:** **không** sửa code, **không** thêm syscall, **không** thêm
  early-free vào `INFLIGHT`, **không** mở async WRITE, **không** hứa hỗ trợ
  kill/cancel trong tuần 3. Mọi thay đổi code (nếu có) phải là một PR riêng sau
  review, và chỉ là "sửa sai khác contract nhỏ đã được review" theo card.

Phương pháp: đọc trực tiếp mã nguồn tại base revision; đối chiếu semantics kill/exit
của xv6 pin; mô phỏng từng event trên state machine; kiểm tra lại bằng 4 kịch bản
lifecycle bắt buộc của card (kill trước dispatch, khi `INFLIGHT`, sau `DONE`, cleanup
đúng một lần). Không có kết quả thực nghiệm nào được ghi PASS trong tài liệu này vì
**không có code mới để chạy**.

---

## 2. Hiện trạng: ai thao tác handle, ai sở hữu dữ liệu

### 2.1 Handle hiện tại chỉ có `(id, gen)` — không có owner

```c
struct io_handle { int id; uint gen; };   // kernel/io_request.h
```

Mọi hàm API chỉ kiểm tra **tính hợp lệ của cặp `(id, gen)`** (`io_lookup_handle_locked`,
[`kernel/io_request.c`](../../kernel/io_request.c) dòng 172–185), **không** kiểm tra
tiến trình gọi có phải chủ sở hữu request hay không. Hệ quả: bất kỳ ai có handle
(cùng nhân, hoặc lộ handle sang tiến trình khác) đều có thể `poll/wait/data/release`
request đó. Với kernel C API của tuần 2–3, handle do caller giữ kín nên rủi ro thấp;
với syscall user ở tương lai, đây là **lỗ hổng phân quyền** phải chặn.

### 2.2 Bảng thao tác handle và quyền hiện tại

| Hàm | Ai gọi được (hiện tại) | Kiểm tra owner? | Chặn khi sai | Ghi chú |
| :--- | :--- | :---: | :--- | :--- |
| `aio_read_submit` | Process context (`myproc() != 0`) | — (tạo handle) | `EINVAL/ENODEV/ERANGE/EAGAIN` | Cấp slot + enqueue + dispatch; không chờ |
| `aio_poll(h)` | Bất kỳ process context | **Không** | `ENOENT` nếu stale | Không sleep, không free slot |
| `aio_wait(h)` | Bất kỳ process context | **Không** | `ENOENT`, `EBUSY` nếu đã có waiter | Sleep trên `req`; `waiters ∈ {0,1}` |
| `aio_data(h)` | Bất kỳ process context | **Không** | `NULL` nếu không `DONE` | Trả con trỏ **kernel** tới staging buffer |
| `aio_release(h)` | Bất kỳ process context | **Không** | `EBUSY` nếu chưa terminal/còn waiter; `ENOENT` | Tăng `gen`, đưa slot về `FREE` |
| `io_get_stats` | Process context | — | — | Snapshot dưới `io_lock` |

### 2.3 Ai sở hữu dữ liệu và trong khoảng nào

| Đối tượng | Chủ sở hữu | Hiệu lực | Bất biến |
| :--- | :--- | :--- | :--- |
| `req->data[BSIZE]` (staging buffer) | **Pool** (BSS tĩnh), không phải caller | Địa chỉ bất biến toàn boot; nội dung chỉ định nghĩa khi `DONE` | CPU **cấm** đọc/ghi khi `QUEUED`/`INFLIGHT`; `aio_release` làm handle stale nhưng **không** free bộ nhớ |
| Descriptor chain (`info[head]`) | Driver: `IO_HEAD_ASYNC` → **IRQ** giải phóng; `IO_HEAD_STOCK` → caller stock | Từ publish tới lúc used-ring reap | Mỗi chain đúng **một** chủ thu hồi; không early-free |
| Slot request | Pool; caller giữ "quyền dùng" đến `aio_release` | `FREE→…→DONE/ERROR` giữ slot | Slot chỉ về `FREE` khi terminal + `waiters == 0` |
| Handle | Caller (không được kernel kiểm chứng) | Tới khi slot được release (khi đó `gen` đổi) | Handle stale phải bị từ chối, không được dereference |

### 2.4 Ai giải phóng cái gì (đã có, không đổi ở tuần 3)

- **Descriptor ASYNC:** `reap_head_locked()` trong `virtio_disk_intr` — kiểm tra
  mapping `info[head].req/gen/state/head`, chép status, `free_chain(head)`, rồi gọi
  `io_async_completed_locked`
  ([`kernel/virtio_disk.c`](../../kernel/virtio_disk.c) dòng 394–432).
- **Descriptor STOCK:** `virtio_disk_rw` sau khi `b->disk == 0` tự `free_chain`
  (dòng 325–331).
- **Slot:** chỉ `io_release_locked` (dòng 190–215), và chỉ khi `DONE/ERROR` +
  `waiters == 0`.
- **Staging buffer:** **không ai free** — nằm trong BSS của pool; đây là lý do kill
  không thể gây use-after-free cho DMA (xem §5).

---

## 3. Bảng trạng thái × sự kiện × hành động (hiện trạng)

Cột "Owner" là chủ sở hữu **hành động** theo thiết kế hiện tại.

| State | Sự kiện | Hành động hiện có | Owner | Ghi chú |
| :--- | :--- | :--- | :---: | :--- |
| `FREE` | `aio_read_submit` | `io_alloc_slot_locked`, init toàn bộ field, `data` zero | Process gọi | Không quan sát được từ CPU khác |
| `ALLOCATED` | enqueue | `io_queue_enqueue_locked`: `state=QUEUED`, `enqueue_seq`, link cuối queue | Queue (L01) | Chỉ tồn tại bên trong submit dưới `io_lock` |
| `QUEUED` | dispatcher + `try_submit` = 0 | `io_started_locked`: `state=INFLIGHT`, gán `head`, đo `max_inflight`; publish avail + notify | Dispatcher (process/IRQ) | Driver có thể đã DONE trước khi `try_submit` trả về |
| `QUEUED` | `try_submit` = `EAGAIN` | Giữ nguyên request, `seq`, vị trí; `eagain_desc++`; dừng dispatch | Dispatcher | Không pop, không spin |
| `INFLIGHT` | IRQ reap chain | `io_async_completed_locked`: `DONE` nếu status 0, `ERROR` nếu khác; `wakeup(req)` | IRQ | Status ghi **trước** wakeup (chống lost-wakeup) |
| `DONE` | `aio_wait` | Fast-path hoặc ngủ-tới-khi-thức; trả 0; `waiters` 0 | Process | Không tự release |
| `ERROR` | `aio_wait` | Trả `IO_EIO`; `aio_data` trả `NULL` | Process | Vẫn chiếm slot |
| `DONE`/`ERROR` | `aio_release` | `io_release_locked`: `gen++` (≠0), `state=FREE`, xoá field | Process | Handle cũ thành stale |
| `DONE`/`ERROR` | `aio_release` khi `waiters != 0` | `EBUSY` | Process | Bảo vệ waiter |
| `QUEUED`/`INFLIGHT` | `aio_release` | `EBUSY` | Process | Không early-free |

Bất biến hiện có, đã đối chiếu code:

1. `aio_release` **không** free slot đang `QUEUED/INFLIGHT` (dòng 195–198).
2. Descriptor async chỉ được free trong IRQ; request slot và descriptor là hai vòng
   đời độc lập (D5/D7 tuần 2).
3. `wakeup(req)` chỉ sau khi state đã terminal (dòng 374–391).
4. Staging buffer **không bao giờ** bị `kfree`/giải phóng — kể cả khi process chết.
5. Handle stale bị chặn trước dereference; `gen` chỉ tăng khi release, không bao giờ 0.

---

## 4. Hành vi khi caller bị kill/exit (rà soát trên code hiện tại)

### 4.1 Semantics kill/exit của xv6 pin (điểm tựa)

- `kkill(pid)` đặt `p->killed = 1`; nếu process đang `SLEEPING` thì đổi `RUNNABLE`
  để `sleep()` trả về ([`kernel/proc.c`](../../kernel/proc.c) dòng 600–622).
- `usertrap()` kiểm tra `killed(p)` **trước** syscall và **sau** syscall; nếu killed
  thì `kexit(-1)` ([`kernel/trap.c`](../../kernel/trap.c) dòng 54–82).
- `kexit()` đóng file/cwd rồi chuyển `ZOMBIE`; **không** có hook dọn request async
  ([`kernel/proc.c`](../../kernel/proc.c) dòng 325–360).
- `sleep_prepare()` chỉ ghi `p->chan`; `sleep()` ngủ nếu `p->chan != 0`, trả ngay nếu
  đã bị wakeup ([`kernel/proc.c`](../../kernel/proc.c) dòng 546–572).

### 4.2 Bảng sự kiện kill/exit × trạng thái request

| # | Sự kiện | State request | Hành vi hiện tại (đã kiểm tra code) | Rủi ro | Mức |
| :---: | :--- | :--- | :--- | :--- | :---: |
| K1 | Kill **trong `aio_wait`** | `QUEUED` hoặc `INFLIGHT` | `kkill` set `killed`, wake khỏi `sleep`; `aio_wait` reacquire lock, **không kiểm tra `killed`**, lặp `sleep_prepare`+`sleep` ⇒ **ngủ tiếp** chờ I/O. Nếu I/O xong: trả kết quả, trap thấy killed → `kexit`; slot `DONE/ERROR` **rò rỉ**. Nếu I/O không bao giờ xong: process **không thể thoát** dù đã bị kill | Leak slot; kill không hiệu lực tới khi I/O xong; thiết bị treo ⇒ process treo | **Cao** |
| K2 | Kill/exit khi request đang `QUEUED` (không wait) | `QUEUED` | Không ai cancel. Dispatcher sau đó vẫn dispatch → `INFLIGHT` → `DONE/ERROR`; slot **rò rỉ** vĩnh viễn | 16 slot rò rỉ ⇒ mọi submit sau trả `EAGAIN`; async I/O chết, stock vẫn chạy | **Cao** |
| K3 | Kill/exit khi request đang `INFLIGHT` | `INFLIGHT` | IRQ vẫn reap bình thường trên vùng BSS tĩnh; không UAF, không double-free; slot → `DONE/ERROR` **rò rỉ** | Leak slot; descriptor vẫn được thu hồi đúng một lần | **Cao** (leak) |
| K4 | Kill/exit **sau** `DONE` trước `release` | `DONE/ERROR` | Slot giữ nguyên vĩnh viễn; không hook `kexit` | Leak slot; dữ liệu đọc xong nhưng không ai giải phóng | **Cao** |
| K5 | Kill/exit khi **chưa wait** (sau submit) | `QUEUED`/`INFLIGHT`/`DONE` | Như K2/K3/K4 | Leak | **Cao** |
| K6 | Kill **giữa** `aio_read_submit` | `ALLOCATED` (nội bộ) | `ALLOCATED` chỉ tồn tại trong vùng `io_lock`; kill không chen vào được cho tới khi submit trả về; không có state nửa vời | Không rò rỉ trong critical section; handle chưa trả về | Thấp |
| K7 | Double release | `FREE` (đã release) | Lần 2: `gen` đã đổi/state `FREE` ⇒ `io_lookup_handle_locked` trả NULL ⇒ `ENOENT` | An toàn, không double-free | — |
| K8 | Release khi request còn `QUEUED/INFLIGHT` | — | `EBUSY` (dòng 195–198) | An toàn | — |
| K9 | Hai process cùng thao tác một handle | mọi state | **Không kiểm owner**: process thứ hai có thể `wait/data/release` hộ | Sai quyền sở hữu; release hộ làm mất dữ liệu; nguy cơ khi mở syscall | **Trung bình→Cao** |
| K10 | Process chết khi đang là waiter, request chưa xong | `QUEUED/INFLIGHT`, `waiters=1` | Như K1: chưa thoát được; nếu thoát được thì `waiters` đã về 0 trong `aio_wait`; chưa có cleanup | Nếu có cleanup mà không xử lý `waiters` sẽ kẹt `EBUSY` | Trung bình |

### 4.3 Kết luận rà soát

1. **Không có use-after-free/DMA để lại trên đường ASYNC khi kill** vì staging
   buffer và request slot nằm trong BSS tĩnh, IRQ không free slot; kill không free
   bất cứ thứ gì. Đây là điểm mạnh của D2/D5 tuần 2.
2. **Rò rỉ slot là hệ quả chính** của kill/exit: request đi hết vòng đời nhưng không
   ai gọi `aio_release`; sau 16 lần, pool cạn vĩnh viễn cho tới reboot.
3. **Kill không "cắt" được `aio_wait`** trong code hiện tại (K1): không có kiểm tra
   `killed`, nên kill chỉ có hiệu lực sau khi I/O hoàn tất.
4. **Không có owner**: handle không gắn tiến trình, nên việc "thu hồi hộ" khi process
   chết là **không thể làm chính xác** nếu không thêm thông tin owner.
5. Vì vậy cần: (a) trường owner; (b) hook cleanup ở `kexit`; (c) API cancel/abandon
   có semantics theo state; (d) kiểm tra `killed` trong `aio_wait`; (e) bổ sung test.

---

## 5. Thiết kế đề xuất

### 5.1 Lựa chọn cơ chế sở hữu

| Phương án | Nội dung | Ưu | Nhược | Quyết định |
| :--- | :--- | :--- | :--- | :--- |
| **A (khuyến nghị)** | Thêm `owner_pid` vào `io_request`; cleanup theo `pid` khi `kexit`; cờ `ORPHAN` cho `INFLIGHT`; scan 16 slot | Nhỏ (+8 B/slot), không bảng động, không refcount, đủ cho MVP | Cleanup O(IO_NREQ) mỗi lần exit; pid lý thuyết có thể tái sử dụng | **Chọn cho tuần 4** |
| B | Bảng handle/refcount trong `struct proc` (fd-like) | Chính xác khi fork/syscall; cleanup O(số handle) | Tăng bộ nhớ `struct proc`, phức tạp fork/exit/copyout; vượt phạm vi tuần 3 | Backlog khi mở syscall (theo Q3) |
| C | Không owner, chỉ timeout/reboot | Đơn giản nhất | Không giải quyết leak; không đáp ứng kill/exit | Loại |

### 5.2 Bổ sung dữ liệu (đề xuất, chưa hiện thực)

```c
/* ĐỀ XUẤT W3-I01 — chưa có trong code tuần 3 */
struct io_request {
  ...
  int  owner_pid;   /* pid của process đã submit; -1 nếu không có */
  uint flags;       /* IO_REQ_ORPHAN = 1<<0: chủ đã chết, chờ completion thu hồi */
  /* các field cũ giữ nguyên thứ tự */
};
```

- **Bộ nhớ:** `sizeof(struct io_request)` hiện là **1080 B** (theo contract tuần 2:
  14 field 4 B + `data[1024]`). Thêm `int + uint` = **+8 B** ⇒ 1088 B/slot ⇒
  **17 408 B** cho 16 slot, tăng **+128 B (+0,74%)** trên pool; không `kalloc`,
  không thay đổi layout DMA hiện có (các field mới đặt sau `data` hoặc trước `data`
  nhưng **không** đổi offset các field cũ mà driver đang dùng). Nếu cần
  `_Static_assert(sizeof(struct io_request) == 1088)` khi hiện thực.
- **Phương án thay thế:** dùng `struct proc *owner` (+8 B, +256 B/tổng) để tránh
  hoàn toàn pid-reuse; đắt hơn A 128 B. Chọn A cho MVP, ghi rõ rủi ro pid-reuse.

### 5.3 Mã lỗi và API bổ sung (đề xuất)

| Mã / API | Giá trị / chữ ký | Ý nghĩa |
| :--- | :--- | :--- |
| `IO_EPERM` | `-1` | Handle không thuộc process gọi (owner mismatch) |
| `IO_EINTR` | `-4` | `aio_wait` bị kill/ngắt giữa chừng; **chưa** release, caller phải cleanup |
| `IO_ECANCELED` | `-125` | `status` của request bị cancel khi còn `QUEUED` |
| `aio_cancel(h)` | `int aio_cancel(struct io_handle h)` | Hủy request `QUEUED` (unlink, `ERROR/-ECANCELED`, wake); `INFLIGHT`/terminal trả `EBUSY`; owner sai trả `EPERM` |
| `aio_abandon(h)` | `int aio_abandon(struct io_handle h)` | Owner từ bỏ handle: `QUEUED` ⇒ cancel+free; `INFLIGHT` ⇒ set `ORPHAN`, auto-free khi completion; terminal ⇒ free; trả 0, handle stale ngay hoặc sau completion |
| `io_owner_exit(pid)` | `void io_owner_exit(int pid)` | Gọi từ `kexit`; quét 16 slot của `pid`, đưa về trạng thái an toàn (bảng §5.4) |

Các hàm cũ thêm kiểm tra owner ở đầu (sau `io_lookup_handle_locked`):
`aio_poll/aio_wait/aio_data/aio_release/aio_cancel/aio_abandon` trả `IO_EPERM` nếu
`req->owner_pid != myproc()->pid`. Riêng `aio_data` trả `NULL` + không log.

### 5.4 Bảng state × event × action × owner (thiết kế)

| State | Event | Action | Owner | Context |
| :--- | :--- | :--- | :---: | :--- |
| `QUEUED` | `aio_cancel` (owner) | `io_queue_remove_locked(req)`; `status=-ECANCELED`; `state=ERROR`; `errors++`; `wakeup(req)`; slot **giữ** tới `aio_release` | Caller | Process |
| `QUEUED` | `kexit`/`io_owner_exit` | remove khỏi queue; `errors++`, `released++`; `gen++`; `state=FREE` | Kernel | Process (exit) |
| `INFLIGHT` | `aio_cancel` | `EBUSY` — virtio-blk **không có abort**; không được free slot/buffer/descriptor | Caller | Process |
| `INFLIGHT` | `aio_abandon`/`kexit` | `flags |= ORPHAN`; **không** đổi `state`; chờ completion. IRQ reap: `io_async_completed_locked` (DONE/ERROR) → nếu ORPHAN: `released++`; `gen++`; `state=FREE` (bỏ qua `DONE` lâu dài); `orphan_reclaimed++` | IRQ | IRQ, dưới `io_lock` |
| `DONE`/`ERROR` | `aio_cancel` | `EBUSY` (đã terminal; dùng `aio_release`) | Caller | Process |
| `DONE`/`ERROR` | `aio_abandon`/`kexit` | `released++`; `gen++`; `state=FREE` | Caller/Kernel | Process |
| `DONE`/`ERROR` | `aio_release` | như hiện tại (`released++`, `gen++`, `FREE`) | Owner | Process |
| mọi state | `kexit` khi `waiters == 1` (chính process đó) | `aio_wait` phải trả `EINTR` trước, đặt `waiters=0`; cleanup mới chạy. Nếu cleanup chạy khi `waiters != 0` ⇒ giữ slot tới khi waiter thoát (không được free) | Kernel | Process (exit) |

### 5.5 `aio_wait` trở nên "kill-aware"

Đề xuất sửa vòng lặp (khi hiện thực ở tuần 4):

```c
while (req->state == IO_QUEUED || req->state == IO_INFLIGHT) {
  if (killed(myproc())) {            /* p->lock lấy dưới io_lock: đúng thứ tự D6 */
    rc = IO_EINTR;
    break;
  }
  sleep_prepare(req);
  release(io_lock);
  sleep();
  acquire(io_lock);
  if (req->gen != h.gen) { /* stale sau wake */ ... }
}
req->waiters = 0;
```

**Giới hạn còn lại (phải ghi rõ, không giấu):** kill đến đúng khe giữa lần kiểm tra
`killed()` và lúc `sleep()` thực sự ngủ vẫn không được quan sát cho tới khi I/O
hoàn tất, vì `kkill` chỉ wake process đang `SLEEPING`. Trong môi trường test, thiết bị
luôn hoàn tất nên process chỉ bị trễ, không treo vĩnh viễn. Muốn đóng hoàn toàn khe
này cần một trong hai thay đổi **phải review riêng**: (a) cho `kkill` wake cả kênh
`p->chan` (ảnh hưởng mọi sleep toàn kernel — rủi ro spurious wakeup), hoặc
(b) `aio_wait` có timeout hữu hạn (thêm semantics timeout, không được coi timeout là
thiết bị đã dừng). Cả hai **không** nằm trong tuần 3.

### 5.6 Cleanup ở `kexit` — thứ tự an toàn

```
kexit(status):
  close fds, cwd (hiện có)
  io_owner_exit(p->pid)        # MỚI: process context, không giữ p->lock/io_lock
  ...
  acquire(&p->lock); state = ZOMBIE ...
```

- `io_owner_exit` **không** được gọi khi đang giữ `p->lock` (tránh lock order
  `p->lock → io_lock` trái với D6 `io_lock → p->lock`).
- Mỗi slot: quyết định theo bảng §5.4; **không** free slot `INFLIGHT`; chỉ set
  `ORPHAN`.
- Trong IRQ, nếu `ORPHAN`: sau khi tính DONE/ERROR và `wakeup` (không có waiter),
  mới `released++`, `gen++`, `FREE`. `wakeup` trước/sau free không quan trọng vì
  không còn waiter, nhưng giữ thứ tự "terminal trước, free sau" để dễ review.
- Nếu cleanup gặp `waiters != 0` (trường hợp xấu, waiter không phải chính process
  đang exit): **không free**, đặt `ORPHAN` và để waiter/completion xử lý.

### 5.7 Ảnh hưởng tới queue/policy (đối chiếu W3-G01)

- Cancel/orphan chỉ gỡ request **`QUEUED`** bằng `io_queue_remove_locked` (D17);
  không đụng `INFLIGHT`.
- `logical_head`/`direction` của SCAN **không cần rollback** khi gỡ một request
  `QUEUED`: lựa chọn được tính lại từ trạng thái đã commit ở mỗi lần dispatch; nếu
  request bị gỡ là ứng viên kế tiếp thì lần chọn sau tự bỏ qua.
- Cancel không được ghi trace `DISPATCH`; nếu muốn audit, thêm counter `canceled`
  (không thêm event vào trace để oracle L02 không phải xử lý thêm loại event).

### 5.8 Bất biến kế toán sau khi thêm orphan/cancel

Giữ nguyên D10 tuần 2, bổ sung:

- `submitted = queued + inflight + done + error` (cancel từ `QUEUED` chuyển sang
  `ERROR` nên vẫn nằm trong `error` cho tới khi release/cleanup);
- `completed + errors = released + done + error`: **mọi** đường auto-free
  (orphan trong IRQ, cleanup `kexit`, `aio_abandon`) **phải** `released++` trước khi
  `gen++/FREE`, nếu không bất biến sai;
- `free_req = 16 - (queued + inflight + done + error)`;
- sau drain/owner exit: `free_req = 16`, `free_desc = 8`, `Q=I=D=X=0`;
- counter mới: `canceled`, `orphan_reclaimed`, `eintr`, `owner_denied` (tích lũy).

---

## 6. Test cần viết (chưa chạy — NOT RUN)

| Mã | Kịch bản | Expected (thiết kế) | Môi trường |
| :---: | :--- | :--- | :--- |
| K1 | Kill **trước** dispatch: submit rồi kill process khi request còn `QUEUED` (mock driver giữ `EAGAIN`) | Queue không còn request; slot `FREE`; `gen` tăng; `submitted = released`; không dispatch request đã cancel | Mock + hook, CPU1/4 |
| K2 | Kill **khi `INFLIGHT`**: submit READ thật rồi kill ngay trong `aio_wait` | Không UAF; descriptor thu hồi đúng 1 lần; sau completion slot `FREE`; `free_desc=8`; `orphan_reclaimed=1`; không data trả cho ai | QEMU READ thật CPU1/4 |
| K3 | Kill **sau `DONE`** trước `release` | Cleanup `kexit` free slot; handle cũ `ENOENT`; không double-free | Selftest process context |
| K4 | **Cleanup đúng một lần**: owner exit đồng thời một thread/handle khác thử release | Chỉ một đường free; đường còn lại `ENOENT`/`EPERM`; drain đủ 16/8; bất biến D20 đúng | CPU4 stress |
| K5 | Kill **waiter**: process bị kill trong `aio_wait`; completion đến sau | `aio_wait` trả `EINTR` (sau khi thức), `waiters=0`; process exit được; slot được cleanup | Hook + timer IRQ |
| K6 | **Rò rỉ 16 slot** rồi owner exit | Sau cleanup: `free_req=16`; submit mới thành công; không panic | Mock |

Negative control bắt buộc: bỏ bước `ORPHAN → released++/FREE` ⇒ phải FAIL ở K2/K6;
bỏ owner check ⇒ K4 phải FAIL. Test timeout/thiếu marker là **FAIL**, không phải PASS.

---

## 7. Đối chiếu tiêu chí nghiệm thu card

| # | Tiêu chí | Kết quả |
| :---: | :--- | :--- |
| 1 | Có bảng state/event/action và owner cho mọi trường hợp | ✅ §3, §5.4 (gồm kill/exit theo 4 kịch bản + ca biên) |
| 2 | Nêu rõ code nào đã có, thiết kế nào chưa triển khai/test | ✅ §2.4, §8 |
| 3 | Hoàng review lifetime DMA; không thêm early-free vào `INFLIGHT` | ⏳ **PENDING**; thiết kế giữ nguyên nguyên tắc "không free khi `INFLIGHT`" |
| 4 | Review bằng 4 kịch bản lifecycle; chạy lại stale-handle/release-active nếu có sửa code | ✅ 4 kịch bản K1–K4 đã định nghĩa; **không sửa code** nên không chạy lại (vẫn ghi NOT RUN) |

---

## 8. Code nào đã có / thiết kế nào chưa (bảng bàn giao)

| Hạng mục | Trạng thái | Ghi chú |
| :--- | :---: | :--- |
| Pool 16 slot, handle id/gen, release-terminal, stale chặn | ✅ **Đã có** (main) | `io_request.c`; test T02/T03/T04/T11 từ tuần 2 |
| `aio_wait` chống lost-wakeup, single waiter | ✅ **Đã có** | `sleep_prepare/release/sleep/acquire`; T05/T06 |
| Descriptor owner ASYNC/STOCK, IRQ reclaim | ✅ **Đã có** | `virtio_disk.c`; test T07–T09 |
| Owner `pid` + owner check cho mọi API | ❌ **Chưa — thiết kế** | §5.2–§5.3 |
| `aio_cancel`, `aio_abandon`, `io_owner_exit` | ❌ **Chưa — thiết kế** | §5.3–§5.4 |
| `aio_wait` kill-aware (`IO_EINTR`) | ❌ **Chưa — thiết kế** | §5.5 |
| Hook cleanup trong `kexit` | ❌ **Chưa — thiết kế** | §5.6; cần review vì đụng `proc.c` |
| Test K1–K6 | ❌ **Chưa — thiết kế** | §6; **NOT RUN** |
| Bão hoà `waiters != 0` khi cleanup | ❌ **Chưa — thiết kế** | §5.4 dòng cuối |
| Syscall/fd table, copyout dữ liệu, timeout | ❌ **Backlog** | Phụ thuộc PTO-7/Q3; tuần 5–6 |

---

## 9. Rủi ro và backlog

| Rủi ro | Giảm thiểu / trạng thái |
| :--- | :--- |
| Free slot sớm khi DMA còn dùng ⇒ UAF | **Cấm** free khi `INFLIGHT`/`QUEUED`; staging buffer BSS tĩnh; Hoàng review lifetime |
| Kill trong khe `sleep_prepare`→`sleep` | Ghi rõ còn khe hở; cần thay đổi `kkill`/timeout phải review riêng (không làm tuần 3) |
| Pid tái sử dụng | Chọn phương án A; ghi rủi ro; nếu cần chính xác tuyệt đối chuyển sang owner pointer/refcount (B) |
| Handle lộ sang process khác | Owner check ở mọi API; future syscall dùng bảng handle/fd (B) |
| `released` không tăng khi auto-free ⇒ sai bất biến | Ghi thành yêu cầu bắt buộc trong §5.8; test K2/K6 |
| Cancel làm sai policy SCAN | Chỉ gỡ `QUEUED` bằng D17; không rollback head/direction; oracle L02 không thấy event mới |
| Timeout bị hiểu sai là "thiết bị đã dừng" | Không thêm timeout tuần 3; nếu thêm phải định nghĩa rõ |
| Đụng `proc.c` (kexit) gây hồi quy | PR riêng, test `usertests -q` CPU1/4 + `grind 60s`; review Hoàng |

**Backlog chuyển tuần 4+:** owner check + `aio_cancel`/`aio_abandon` + `io_owner_exit`
(hiện thực); `aio_wait` kill-aware; test K1–K6; cân nhắc `kkill` wake channel hoặc
timeout; bảng handle/fd khi mở syscall (Q3); async WRITE (Q2); merge/coherence.

---

## 10. Checklist review cho Hoàng (lifetime DMA)

1. Không có đường nào free slot/descriptor khi `state ∈ {QUEUED, INFLIGHT}`.
2. IRQ chỉ thu hồi chain đúng owner `ASYNC`; orphan path không đụng descriptor.
3. Staging buffer của slot `INFLIGHT` không bị zero/ghi bởi cleanup.
4. `gen` chỉ tăng một lần cho mỗi lần free; handle stale bị chặn.
5. `released++` có mặt trên **mọi** đường auto-free.
6. Hook `kexit` không chạy khi đang giữ `p->lock`; thứ tự khóa đúng D6.
7. Không thêm early-free vào `INFLIGHT` dưới bất kỳ lý do "timeout/hủy".

---

## 11. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-07 | base `49557bf` | Rà soát vòng đời request trên main; bảng kill/exit K1–K10; thiết kế owner/orphan/cancel; ngân sách bộ nhớ; 6 kịch bản test; backlog tuần 4. |
