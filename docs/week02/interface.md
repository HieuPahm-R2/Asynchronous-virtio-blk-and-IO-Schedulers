# W2-G01 — Contract: interface request, buffer ownership và quy tắc khóa

> **Card:** W2-G01 (CARD 1/9) · **Owner:** Phạm Trung Hiếu (20233402) ·
> **Reviewer:** Nguyễn Văn Hoàng + Phạm Quý Lợi · **Estimate:** 1,5h ·
> **Hạn nội bộ:** 2026-10-28 · **Bản này:** 2026-10-30.
>
> **Trạng thái:** 📄 CONTRACT — **CHƯA ĐƯỢC DUYỆT**. Bảng chữ ký ở §12 còn
> `PENDING`; card W2-G01 chỉ được đóng sau khi Hoàng và Lợi review **cùng một
> revision** (commit của PR này) và ghi nhận xét. Không ghi "đã duyệt" trước khi
> có comment/approve thật.
>
> **Nguồn sự thật:** file này là contract duy nhất cho async READ tuần 2.
> Header [`kernel/io_request.h`](../../kernel/io_request.h) là bản chuyển thể
> trực tiếp của §2–§6; nếu hai bên lệch nhau, sửa cả hai trong cùng PR.
> Tài liệu tuần 1 **không còn hiệu lực ở hai điểm** (buffer ownership và mô hình
> khóa): xem §10.
>
> **Base:** `e8095001b2e64f361cd80b25e98a1bea5fd60888` (origin/main sau 3 PR
> tuần 1, đã fetch ngày 2026-10-30) · **Pin xv6 tạm:**
> `f780d7850765d74cbdcd1fff4b822d8829f7c9bd` (GV **chưa** xác nhận tag chính
> thức — giữ nguyên, không tự đổi).

## 0. Vì sao phải chốt trước khi ghép code

Hai tài liệu tuần 1 mâu thuẫn ở đúng hai điểm mà ba nhánh code sẽ va nhau:

| Điểm | `async-design.md` (Hoàng) | `decisions_report.md` (Hiếu) | Chốt ở đây |
| --- | --- | --- | --- |
| Buffer | pool sở hữu header/status/**buffer** | caller sở hữu `kbuf`, pool chỉ cấp slot | **pool-owned staging buffer** (D2) |
| Khóa | một `io_lock` chung | chưa chốt, còn `vdisk_lock` riêng | **một lock domain duy nhất** (D6) |

Nếu ba người code theo hai mô hình khác nhau, module sẽ không ghép được hoặc
deadlock. Contract này chốt một mô hình, ghi rõ phương án bị loại và lý do; phần
còn mở với GV được tách sang §11 (không lấy giả định làm quyết định).

## 1. Đối chiếu nguồn tại cùng revision (bước 1 của card)

Đã đọc lại các file sau ở base nêu trên (số dòng theo revision này):

| Vị trí | Nội dung đối chiếu | Kết luận dùng cho contract |
| --- | --- | --- |
| `kernel/buf.h:1-11` | `struct buf`: `valid`, `disk`, `dev`, `blockno`, `lock` (sleeplock), `refcnt`, `data[BSIZE]` | Stock dùng `struct buf` vừa làm cache vừa làm vùng DMA; **không** tái dùng làm vùng DMA async (D2) |
| `kernel/bio.c:57-88` | `bget`: `bcache.lock` bảo vệ lookup/refcnt; nhả trước `acquiresleep(&b->lock)` | `bcache.lock` và `buf.lock` không lồng vào io_lock; thứ tự chỉ một chiều (D6) |
| `kernel/bio.c:90-112` | `bread` gọi `virtio_disk_rw` khi cache miss; `bwrite` chỉ log gọi | Async READ **không** thay `bread` trong tuần 2 (D1) |
| `kernel/virtio_disk.c:22-59` | `struct disk`: `free[NUM]`, `used_idx`, `info[head].{b,status}`, `ops[head]`, `vdisk_lock` | Mở rộng `info[head]` bằng owner + `struct io_request *`; giữ `b` cho stock (D7) |
| `kernel/virtio_disk.c:155-213` | `alloc_desc/free_desc/free_chain/alloc3_desc`; rollback phần dở | Một allocator chung stock+async; try-submit rollback đúng (D7) |
| `kernel/virtio_disk.c:215-298` | `virtio_disk_rw`: 3 descriptor, publish + fence + notify, `b->disk`, `sleep_prepare(b)`, caller `free_chain` sau wake | Stock giữ nguyên semantics; **caller stock vẫn reclaim**; async reclaim ở IRQ (D7) |
| `kernel/virtio_disk.c:300-333` | `virtio_disk_intr`: ACK MMIO, drain `used`, `info[id]`, status, `wakeup(b)`, `used_idx++` | IRQ phân nhánh theo owner; async copy status rồi mới tái dùng head (D7) |
| `kernel/virtio.h:51-99` | `NUM=8`, ring, `struct virtio_blk_req` (16B) | `NUM/3 = 2` chain tối đa; `ops[head]` có lifetime toàn cục → header async không nằm trên stack (D7) |
| `kernel/proc.c:545-595` | `sleep_prepare(chan)` + `sleep()` + `wakeup(chan)` (API mới của pin) | Wait dùng đúng pattern prepare→release→sleep→acquire; IRQ cập nhật terminal **trước** wakeup (D9) |
| `kernel/riscv.h:370-375` | `io_fence()` = fence iorw,iorw + compiler clobber | Giữ nguyên chuỗi publish/consume như stock (D7) |
| `kernel/fs.h:5`, `kernel/param.h:8,11,12` | `BSIZE=1024`, `ROOTDEV=1`, `NBUF=30`, `FSSIZE=2000` | Validate `dev==ROOTDEV`, `blockno<FSSIZE`; block → sector ×2 (D3) |
| `kernel/main.c:19-31` | boot order: `binit → iinit → fileinit → virtio_disk_init → userinit` | `io_init()` gọi sau `virtio_disk_init()`, trước `userinit()` (D1) |
| `kernel/trap.c:188-210` | `devintr()`: `plic_claim`, `virtio_disk_intr`, `plic_complete` | IRQ path không đổi; chỉ thân handler phân nhánh owner (D7) |

## 2. Quyết định chốt (decision log)

### D1 — Phạm vi MVP

Chốt: **kernel-level C API**, READ **một block** `BSIZE=1024`, **một thiết bị**
(`ROOTDEV`), queue **FCFS**, không syscall user-space trong tuần 2. WRITE/log giữ
nguyên đường đồng bộ hiện có. Async READ **không phải** là đường thay thế
`bread()`: chỉ đọc fixture read-only cho test; coherence với buffer cache là việc
của kỳ sau.

Lý do: đúng phạm vi card W2-G01/W2-I01/H01/L01 và ma trận T01–T13; giảm bề mặt
sai vào log/ordering. Phương án bị loại trong tuần 2: syscall user-space (chờ GV
trả lời Q3), async WRITE/merge thật, nhiều thiết bị, SCAN/deadline.

### D2 — Buffer ownership: **pool sở hữu staging buffer**

Chốt: mỗi slot request sở hữu **một vùng staging 1024 byte cố định** nằm trong
pool tĩnh (`uchar data[BSIZE]` trong `struct io_request`, BSS, **không** `kalloc`
trong IRQ, **không** DMA vào stack/user pointer). Caller **không** cấp buffer,
**không** được free; nhận con trỏ đọc qua `aio_data()` sau khi terminal và chỉ
được dùng tới `aio_release()`.

Lý do: một chủ sở hữu duy nhất ⇒ IRQ không cần tin caller, không có
use-after-free khi caller thoát/kill; địa chỉ DMA ổn định suốt QUEUED/INFLIGHT;
test T02–T06 kiểm được độc lập; về sau merge READ dễ hơn vì staging liên tục.
Chi phí: 17 280 B BSS (~16,9 KiB) và một lần copy khi tích hợp filesystem (chưa
làm tuần này).

Phương án bị loại: **caller-owned `kbuf`** (đề xuất của `decisions_report.md`
§3.3). Nếu chọn, contract buộc caller giữ buffer sống và không sửa tới
completion, release sớm phải bị từ chối, IRQ/exit/kill phải có refcount — nhiều
đường lỗi hơn trong 1,5h contract và 6h pool. Ghi nhận: **nếu GV yêu cầu API
nhận `kbuf`**, đây là contract change phải mở lại G01, không tự đổi ở nhánh
module.

Quy tắc bắt buộc kèm theo:

| Thời điểm | Ai được đọc/ghi `req->data` |
| --- | --- |
| trước khi `aio_read_submit` trả về (ALLOCATED) | không ai ngoài request layer |
| QUEUED/INFLIGHT | **không ai** (device DMA khi INFLIGHT); không copyout, không sửa |
| DONE | caller được **đọc** sau `aio_wait()==0` / `aio_poll()==1`; không ghi |
| ERROR | nội dung không hợp lệ; không dùng làm dữ liệu |
| sau `aio_release()` | con trỏ `aio_data()` hết hiệu lực; không giữ, không free |
| IRQ | chỉ driver ghi status 1 byte qua descriptor; **không** đụng `req->data` |

### D3 — Đơn vị địa chỉ: **blockno** ở API, đổi sector tại **một chỗ**

Chốt: public kernel API nhận `blockno` (đơn vị block FS). `struct io_request`
lưu `blockno`; **request layer không bao giờ nhân**. Chuyển đổi duy nhất cho
async nằm trong `virtio_disk_try_submit_read()`:
`sector = req->blockno * IO_SECTORS_PER_BLOCK` với `IO_SECTORS_PER_BLOCK =
BSIZE/512 = 2`. Đường stock giữ nguyên công thức hiện có trong
`virtio_disk_rw` (cùng module `virtio_disk.c`, cùng công thức, không module nào
nhân hai lần). Validate tại submit: `dev == ROOTDEV` (nếu không `-ENODEV`) và
`blockno < FSSIZE` (nếu không `-ERANGE`); alignment tự động đúng vì luôn đọc
nguyên block.

### D4 — Handle có generation

```c
struct io_handle { int id; uint gen; };
```

`id ∈ [0, IO_NREQ)`; `gen` khởi tạo 1, tăng mỗi lần `aio_release()`; nếu tràn về
0 thì gán 1 (không dùng 0). Handle hợp lệ ⇔ `id` trong khoảng **và** slot có
`gen` bằng **và** `state != IO_SLOT_FREE`. Mọi hàm public validate **trước mọi
dereference**; handle cũ/stale trả `-ENOENT`, không panic.

Ghi chú tràn: `gen` 32-bit; một slot tái sử dụng 2^32−1 lần mới có thể trùng
handle cũ — ngoài phạm vi tuần 2, được ghi nhận chứ không "chứng minh" là không
bao giờ tràn.

### D5 — Hai vòng đời tách rời

Request (pool phần mềm):

```text
FREE -> ALLOCATED -> QUEUED -> INFLIGHT -> DONE | ERROR -> FREE
```

- `ALLOCATED` chỉ tồn tại bên trong `aio_read_submit()` dưới io_lock, không CPU
  khác thấy.
- `DONE/ERROR` **chưa** trả slot: caller còn cần đọc kết quả; slot chỉ về FREE
  qua `aio_release()`.
- Không bao giờ free slot QUEUED/INFLIGHT/còn `waiters`.

Descriptor (driver):

```text
FREE -> RESERVED -> PUBLISHED -> USED -> RECLAIMED -> FREE
```

- `RESERVED`: `alloc3_desc` đã lấy; rollback nếu thiếu.
- `PUBLISHED`: đã ghi avail ring + fence + notify, state INFLIGHT, head map đã
  trỏ request (đặt **trước** publish).
- `USED`: device đã ghi used entry; `REAPED` thuộc IRQ; `RECLAIMED` là lúc
  `free_chain` — **chỉ một chủ** reclaim (D7).

Head có thể được dùng lại cho request B **trước khi** caller release request A.
Vì vậy mapping head→request, slot request và staging buffer là ba vòng đời
khác nhau: kết quả A nằm trong slot A, không nằm ở `info[head]` sau reclaim.
Xem kịch bản §8.3.

### D6 — Một lock domain duy nhất (quyết định quan trọng nhất)

Chốt: **đúng một spinlock cho prototype**, gọi là `io_lock`, chính là
`disk.vdisk_lock` của driver, truy cập qua accessor
`struct spinlock *virtio_disk_io_lock(void)`. Lock này bảo vệ **tất cả**:

1. request pool + state + generation + waiters;
2. pending queue + `enqueue_seq` + policy state (tuần này chỉ FCFS);
3. descriptor allocator `disk.free[]`, avail/used ring, `disk.used_idx`;
4. owner map `info[head].{owner, req, b, status}` + `req->head`;
5. `struct buf::disk` của đường stock (như hiện tại).

Không có `ioq.lock` riêng trong tuần 2. Không hàm nào acquire lồng; hàm hậu tố
`_locked` giả định đã giữ lock và **không** acquire lại. Không ngủ khi giữ
lock: mẫu bắt buộc `sleep_prepare(chan); release(io_lock); sleep();
acquire(io_lock);`.

Vì sao không giữ hai khóa `ioq.lock` và `vdisk_lock` (đã phân tích trên giấy):
enqueue/dispatch đi theo chiều `ioq.lock → vdisk_lock`; nếu IRQ completion giữ
`vdisk_lock` rồi gọi callback lấy `ioq.lock` để đặt DONE/wakeup thì đó là chiều
ngược `vdisk_lock → ioq.lock` ⇒ **deadlock tiềm ẩn**. Muốn tách khóa phải thiết
kế deferred completion (IRQ chỉ ghi kết quả vào chỗ trung gian rồi process
context drain) — vượt phạm vi và ngân sách tuần 2. Ưu tiên correctness; chi phí
của một khóa là tuần tự hóa dispatch/completion giữa các CPU, chấp nhận được cho
MVP CPUS=1/4 (đo sau, tuần benchmark). Đường nâng cấp (tuần 4+): đặt tên hai
khóa, thứ tự **duy nhất** `ioq.lock → vdisk_lock`, completion chỉ ghi terminal +
wakeup dưới `vdisk_lock`, không gọi ngược.

Không đổi `bcache.lock`/`buf.lock` của stock. Quan hệ khóa (một chiều):

```text
(bcache.lock)  độc lập, KHÔNG lồng với io_lock
(buf.lock sleeplock) -> io_lock     // caller stock giữ buf lock khi vào driver
io_lock -> p->lock                  // sleep_prepare()/wakeup() nội bộ proc.c
io_lock KHÔNG BAO GIỜ -> buf.lock / bcache.lock
```

`io_lock -> p->lock` là chiều duy nhất xuất hiện ở cả `sleep_prepare()` (process)
và `wakeup()` (IRQ), nên nhất quán, không đảo chiều.

### D7 — Contract driver ↔ request layer

**Owner tag:** mỗi head có `enum io_head_owner` (`FREE/STOCK/ASYNC`) + mapping:

```c
struct {
  struct buf *b;               // stock
  struct io_request *req;      // async
  enum io_head_owner owner;    // quyết định ai reclaim
  char status;                 // 1 byte device status
} info[NUM];
```

Mọi head tạo mới phải set `owner` **trước** publish; head về FREE phải clear
`owner=IO_HEAD_FREE, req=NULL, b=NULL` trước khi tái sử dụng.

**Try-submit async** (`virtio_disk_try_submit_read`, W2-H01), giữ io_lock:

1. Validate `req` (state QUEUED, op READ, `blockno < FSSIZE`) — lỗi logic ⇒ panic
   invariant, không tự sửa.
2. `alloc3_desc`; thiếu descriptor ⇒ rollback mọi desc đã lấy, **không publish**,
   request vẫn QUEUED, trả `-EAGAIN` (không sleep, không panic).
3. Fill chain: header = `&disk.ops[head0]` (type `VIRTIO_BLK_T_IN`, sector),
   data = `req->data` (1024B), status = `&info[head0].status` (đặt `0xff`).
4. Trước khi publish: `req->head = head0; req->state = INFLIGHT;
   req->t_dispatch = ticks; info[head0].owner = IO_HEAD_ASYNC;
   info[head0].req = req;`.
5. Publish y hệt stock: `avail->ring[avail->idx % NUM] = head0; io_fence();
   avail->idx++; io_fence(); *QUEUE_NOTIFY = 0;` (số 0 là queue number).
6. Trả 0. Caller (`io_dispatch_locked`) **không** được giả định completion chưa
   xảy ra — thiết bị có thể báo used ngay sau fence.

**IRQ completion** (`virtio_disk_intr`, W2-H02), giữ io_lock, giữ ACK MMIO +
`io_fence` + drain `used` như stock, với mỗi used entry:

1. `head = used->ring[used_idx % NUM].id`; `disk.used_idx++` (đúng một lần).
2. Phân nhánh `info[head].owner`:
   - `STOCK`: giữ nguyên hành vi stock — `b->disk = 0; wakeup(b)`; **không**
     free chain ở IRQ; caller stock sẽ reclaim.
   - `ASYNC`: validate (`req != NULL`, `state == INFLIGHT`, `req->head == head`,
     owner khớp); nếu sai ⇒ `panic` invariant (không âm thầm bỏ qua completion).
     Đọc `info[head].status` → gọi `io_async_completed_locked(req, status)`;
     clear mapping (`owner=FREE; req=NULL; b=NULL`); `free_chain(head)`;
     tăng counter (`completed_async`, `head_reuse` nếu head này vừa map request
     khác trước release).
   - `FREE/khác`: panic invariant (used entry không có chủ).
3. Sau khi xử lý hết used entry: gọi `io_dispatch_locked()` (IRQ tạo cơ hội
   dispatch request QUEUED dù producer đã ngừng submit).
4. Nhả io_lock; `devintr()` gọi `plic_complete()` như stock (không gọi hai lần).

**Ai reclaim — bảng chốt:**

| Owner | Nơi reclaim `free_chain` | Nơi wakeup | Ai gọi dispatch tiếp |
| --- | --- | --- | --- |
| STOCK | caller trong `virtio_disk_rw` sau `while (b->disk==1)` (như stock) | IRQ `wakeup(b)` | sau `free_chain`, caller stock gọi `io_dispatch_locked()` (W2-H02/G02) |
| ASYNC | IRQ ngay sau completion, trước khi nhả lock | IRQ `wakeup(req)` | IRQ sau khi drain, cùng lần giữ lock |

**Không free hai lần:** mỗi head có đúng một owner; `free_desc` stock đã panic
nếu free trùng (`virtio_disk.c:174-175`) — giữ panic này. Cấm mọi nhánh
"free_chain cho mọi request" mà không xét owner (rủi ro double-free stock như
card W2-H02 đã cảnh báo).

**Điểm kích dispatcher** (để queue tiến triển khi producer đã ngừng submit):
(1) `aio_read_submit` sau enqueue; (2) IRQ sau khi reclaim chain async; (3) nhánh
stock sau khi caller `free_chain` (W2-H02/G02). `io_dispatch_locked()` dừng ngay
ở `-EAGAIN` đầu tiên (FCFS, giữ vị trí), không busy-spin.

**Thay đổi đường stock (tối thiểu):** H01 thêm owner=STOCK + accessor
`virtio_disk_io_lock()` + `virtio_disk_try_submit_read`; H02 phân nhánh IRQ và
thêm dispatch-kick sau reclaim stock. Không đổi chữ ký `virtio_disk_rw`, không
đổi `bread/bwrite/log`, không reorder WRITE.

### D8 — Mã lỗi và semantics

Mã âm (không có `<errno.h>` trong kernel; giá trị theo errno Linux để sau này
map syscall):

| Mã | Khi nào | Ai trả |
| --- | --- | --- |
| `-EINVAL` | `out == NULL`; tham số sai hình thức; `aio_wait` gọi ngoài process context | request layer |
| `-ENODEV` | `dev != ROOTDEV` | request layer |
| `-ERANGE` | `blockno >= FSSIZE` | request layer |
| `-ENOENT` | handle stale/không hợp lệ (id/gen/state) | request layer |
| `-EAGAIN` | pool đầy lúc submit (không ngủ, không panic) | request layer |
| `-EIO` | request terminal ERROR (device status ≠ 0) | poll/wait |
| `-EBUSY` | release khi chưa terminal hoặc còn waiter; wait lần hai đồng thời | request layer |
| `-EAGAIN` (nội bộ) | thiếu 3 descriptor trong try-submit; **không** trả cho caller submit | driver → dispatcher |

`aio_read_submit` khi lỗi **không** ghi vào `*out`. `aio_poll`: 1 = DONE,
0 = đang bay, `-EIO` = ERROR, `-E*` = handle lỗi. `aio_wait`: 0 = DONE,
`-EIO` = ERROR, `-E*` = lỗi handle/context. Device status khác 0 **không**
được coi là dữ liệu hợp lệ và **không** panic trong nhánh async.

### D9 — Wait/wakeup và chống mất wakeup

- Kênh chờ async = chính con trỏ `struct io_request *req` (duy nhất trong lúc
  slot đang dùng; slot không thể tái sử dụng khi còn `waiters`).
- `aio_wait` chỉ process context (không gọi trong IRQ); kiểm
  `myproc() == 0` ⇒ `-EINVAL`.
- Vòng lặp: giữ io_lock → validate handle → nếu `waiters != 0` trả `-EBUSY` →
  `waiters = 1` → `while state ∈ {QUEUED, INFLIGHT}`:
  `sleep_prepare(req); release(io_lock); sleep(); acquire(io_lock);` → đọc
  terminal → `waiters = 0` → release.
- IRQ (hoặc fake driver) đặt `state = DONE/ERROR`, `status`, `t_complete`
  **trước** `wakeup(req)`. Nhờ vậy nếu wakeup xảy ra giữa `sleep_prepare` và
  `sleep()`, `sleep()` thấy `p->chan == 0` và trả ngay (không mất wakeup).
- Single consumer trong MVP: `waiters ∈ {0,1}`; wait thứ hai đồng thời trả
  `-EBUSY`; release khi `waiters != 0` trả `-EBUSY`. Multi-waiter/cancel/kill
  đầy đủ để kỳ sau (ngoài W2-I02).
- Gọi `aio_wait` lặp lại trên handle terminal: trả ngay cùng kết quả, không ngủ.
  Không tự release sau wait: `aio_release` là thao tác riêng.

### D10 — Counters và bất biến kế toán

Counter bắt buộc (chi tiết struct ở header): `submitted`, `completed`,
`errors`, `queued`, `inflight`, `max_inflight`, `free_req`, `eagain_pool`,
`stale_handle`, và phía driver `free_desc`, `eagain_desc`, `completed_stock`,
`completed_async`, `head_reuse`.

Bất biến kiểm được bằng test (T02/T03/T08/T11):

1. `submitted == queued + inflight + done + error` (slot đang giữ; DONE/ERROR
   chưa release vẫn tính).
2. `completed + errors == số request đã terminal` và mỗi request đã nhận
   (`submitted`) terminal **đúng một lần**.
3. `free_req == IO_NREQ − (queued + inflight + done + error)`; submit bị
   `-EAGAIN` không làm đổi bất kỳ counter nào trừ `eagain_pool`.
4. `inflight <= max_inflight <= min(IO_NREQ, 2)` với NUM=8, 3 desc/request —
   `max_inflight` **chỉ là số đo**, không cam kết đạt 2.
5. Sau drain + release hết: `queued = inflight = 0`, `done = error = 0`,
   `free_req = IO_NREQ`, `free_desc = NUM`.
6. Descriptor: `free_desc + 3×(chain đang giữ) == NUM`; không rò khi
   EAGAIN/rollback; head được reuse chỉ sau khi đã clear owner/map.

## 3. API chốt (chữ ký + context + khóa + lỗi)

Khai báo đầy đủ ở [`kernel/io_request.h`](../../kernel/io_request.h). Bảng này
là phần nghiệm thu "mỗi hàm ghi context/khóa/trả về khi hết tài nguyên":

| Hàm | Context | Khóa vào/ra | Ngủ? | Hết tài nguyên / lỗi |
| --- | --- | --- | --- | --- |
| `io_init()` | boot CPU, 1 lần | không giữ → không giữ (tự acquire nếu cần) | không | không có (pool tĩnh) |
| `aio_read_submit(dev, blockno, *out)` | process | không giữ → không giữ | **không** | `-EAGAIN` khi pool đầy; `-ENODEV/-ERANGE/-EINVAL` |
| `aio_poll(h)` | process (mọi context không ngủ) | không giữ → không giữ | không | `-ENOENT`, `-EIO`; không free slot |
| `aio_wait(h)` | **chỉ process** | không giữ → không giữ (release trong lúc ngủ) | có | `-ENOENT/-EBUSY/-EINVAL`; `-EIO` terminal |
| `aio_release(h)` | process | không giữ → không giữ | không | `-ENOENT/-EBUSY` |
| `aio_data(h)` | process | acquire ngắn để validate → release | không | `NULL` nếu handle lỗi |
| `io_get_stats(*out)` | process | không giữ → không giữ | không | không |
| `io_queue_enqueue_locked(req)` | process/IRQ, **giữ io_lock** | giữ → giữ | không | không (queue hữu hạn = pool) |
| `io_dispatch_locked()` | process/IRQ, **giữ io_lock** | giữ → giữ | **không** | EAGAIN nội bộ ⇒ dừng dispatch, request ở lại QUEUED |
| `virtio_disk_try_submit_read(req)` | process, **giữ io_lock** | giữ → giữ | **không** | `-EAGAIN` khi thiếu 3 desc; rollback toàn bộ |
| `virtio_disk_intr()` | **IRQ**, tự acquire io_lock | không giữ → không giữ | **không** | panic chỉ khi invariant mapping/head sai; device status ≠ 0 → ERROR |
| `virtio_disk_rw(b, write)` (stock) | process, caller giữ `b->lock` | không giữ → không giữ | có (chờ desc/completion) | giữ nguyên stock: sleep/retry khi hết desc |
| `virtio_disk_io_lock()` | mọi context | — | — | trả `&disk.vdisk_lock` |
| `io_async_completed_locked(req,status)` | process/IRQ, **giữ io_lock** | giữ → giữ | không | panic nếu state ≠ INFLIGHT |

Ngân sách bộ nhớ: `sizeof(struct io_request) = 1080 B` (14 field 4B + 1024B
data), `IO_NREQ=16` ⇒ **17 280 B** BSS tĩnh (đã kiểm bằng `_Static_assert` trong
`results/.../logs/header-check.log`). Không `kalloc` trên đường async.

## 4. State machine và bất biến request/descriptor

### 4.1 Bảng chuyển trạng thái request

| Từ | Sang | Ai / điều kiện |
| --- | --- | --- |
| FREE | ALLOCATED | `aio_read_submit`, còn slot, dưới io_lock |
| ALLOCATED | QUEUED | enqueue thành công (`enqueue_seq`, `next`) |
| QUEUED | INFLIGHT | `virtio_disk_try_submit_read` thành công (set **trước** publish) |
| QUEUED | QUEUED | try-submit `-EAGAIN`: rollback desc, giữ vị trí/seq |
| INFLIGHT | DONE | `io_async_completed_locked(status==0)` |
| INFLIGHT | ERROR | `io_async_completed_locked(status!=0)` |
| DONE/ERROR | FREE | `aio_release` (terminal, `waiters==0`) |

Không có chuyển ALLOCATED→FREE trong luồng hiện tại (mọi lỗi validate xảy ra
**trước** khi chiếm slot); nếu implementation cần, phải giữ bất cập pool counter.

### 4.2 Bất biến (review dựa vào đây)

1. Head map chỉ trỏ request `INFLIGHT`; clear map **trước** tái sử dụng head.
2. Thiếu descriptor: không publish chain dở, request ở lại QUEUED, seq không
   đổi; completion (bất kỳ owner) tạo cơ hội dispatch lại.
3. Mỗi accepted request terminal đúng một lần: `completed+errors` tăng đúng 1
   lần/request.
4. `DONE/ERROR` chưa release vẫn giữ slot + buffer; không free khi còn DMA/ref.
5. Handle stale bị từ chối nhờ `gen`; không trả kết quả của request mới.
6. Header/status/buffer có địa chỉ ổn định suốt QUEUED/INFLIGHT; không stack,
   không user pointer, không `kalloc` trong IRQ.
7. Staging buffer chỉ về FREE sau release, không do completion/timeout.
8. `submit` không ngủ; `wait` ngủ đúng pattern; IRQ chỉ terminal + wakeup.
9. Stock và async dùng chung allocator, mỗi head một owner, mỗi chain một nơi
   free.
10. Không `copyout`, không nhả `buf` sleeplock của caller, không printf mỗi
    request trong IRQ.

## 5. Ba kịch bản review trên giấy (nghiệm thu bước review của card)

### 5.1 Hết pool (T02)

Giả sử `IO_NREQ=16`, cả 16 slot đang giữ (ví dụ 2 INFLIGHT + 14 DONE chưa
release).

1. Caller gọi `aio_read_submit(ROOTDEV, b, &h)`: giữ io_lock, validate OK,
   `io_alloc_slot_locked()` trả NULL ⇒ `eagain_pool++`, release, trả `-EAGAIN`.
   `submitted/free_req` **không đổi**; `*out` không bị ghi; không ngủ.
2. Caller release một request DONE: `gen++`, state FREE, `free_req=1`.
3. Caller submit lại: chiếm đúng slot đó, `enqueue_seq` mới, handle mới. Handle
   cũ (gen trước) tra cứu ⇒ `-ENOENT`.
4. Nếu request vừa submit bị nghẽn descriptor: vẫn QUEUED, `aio_wait` ngủ trên
   `req`; completion của request đang INFLIGHT giải phóng descriptor + gọi
   `io_dispatch_locked()` ⇒ request được publish, terminal, wakeup. Không mất
   wakeup, không panic.

### 5.2 IRQ completion trước khi wait (T05)

1. Submit return; request có thể INFLIGHT.
2. Caller chưa gọi `aio_wait`; IRQ chạy: giữ io_lock, drain used, owner ASYNC,
   `io_async_completed_locked(req,0)` đặt DONE + `wakeup(req)` (không ai ngủ),
   clear map, free chain, dispatch, release lock.
3. Caller gọi `aio_wait(h)`: acquire, validate, thấy DONE ngay ⇒ không
   `sleep_prepare`, trả 0. `poll` trước đó trả 1.
4. Caller đọc `aio_data()`, rồi `aio_release()` ⇒ slot FREE, gen++. Head có thể
   đã được dùng cho request khác từ bước 2 — không ảnh hưởng kết quả A.

Trường hợp completion **rơi vào khe** `sleep_prepare`→`release`→`sleep`:
`wakeup` clear `p->chan`; `sleep()` thấy chan 0 nên trả ngay; vòng `while` lấy
lại lock kiểm DONE. Đây là lý do bắt buộc `sleep_prepare` khi còn giữ lock.

### 5.3 Head được tái sử dụng khi request cũ chưa release (T08)

1. Request A (head 0) terminal DONE; IRQ copy status vào `req_A->status`, clear
   `info[0].{owner,req}`, free chain ⇒ desc 0/1/2 FREE.
2. Dispatcher lấy ngay desc 0/1/2 cho request B: set `req_B->head=0`,
   `info[0].owner=ASYNC, .req=req_B`, publish. Lúc này A **chưa** release.
3. Caller A vẫn `aio_wait`/`aio_data` đọc `req_A->data` (staging riêng) — đúng
   dữ liệu; handle A còn hợp lệ tới release.
4. IRQ hoàn tất B: `used->ring[...].id = 0`, owner ASYNC, `info[0].req == req_B`
   ⇒ complete B, không đụng A, không complete đôi.
5. `aio_release(A)` chỉ đổi slot A, không đụng descriptor/head.

Điều kiện để đúng: (a) kết quả nằm trong slot request, không trong
`info[head]`; (b) clear map trước reuse; (c) validate `req->head == head` khi
completion; (d) mỗi head một owner.

## 6. Map kiểm thử T01–T13 → contract

| Test | Kiểm rule nào | Ai chạy / môi trường |
| --- | --- | --- |
| T01 single READ | D2 buffer, D3 blockno/sector, D6 lock | Hoàng — QEMU 1/4 |
| T02 pool full | D8 `-EAGAIN`, D10 counter | Hiếu — kernel test |
| T03 stale handle | D4 generation | Hiếu — kernel test |
| T04 release sớm | D5/D8 `-EBUSY`, không free DMA | Hiếu — hook + QEMU |
| T05 complete-before-wait | D9 | Hiếu — hook + QEMU |
| T06 wait-before-complete | D9 sleep pattern, không mất wakeup | Hiếu/Hoàng — hook + QEMU |
| T07 backpressure descriptor | D7 EAGAIN/rollback/dispatch-kick | Lợi — mock → QEMU |
| T08 head reuse trước release | D5/D7, §5.3 | Hoàng — hook + QEMU |
| T09 completion mapping/order đảo | D7 used-head + owner | Hoàng — mock/hook |
| T10 submit không chờ completion | D6 submit không ngủ, IRQ độc lập | Cả nhóm — hook + QEMU |
| T11 drain/accounting | D10 | Cả nhóm — QEMU 1/4 ×10 |
| T12 stock regression | D7 đường stock không đổi semantics | Cả nhóm — QEMU thật |
| T13 FCFS oracle | D5 + interface queue (`enqueue_seq`) | Lợi — mock + QEMU |

Lưu ý: T02/T03/T07/T13 chạy được với fake driver (đăng ký/hook theo header);
kết luận về IRQ/thiết bị thật phải có log QEMU riêng. Không lấy completion
order chứng minh FCFS.

## 7. Phạm vi file, owner và thứ tự merge

| File | Owner | Nội dung | Card |
| --- | --- | --- | --- |
| `docs/week02/interface.md` | Hiếu | contract này | G01 |
| `kernel/io_request.h` | Hiếu | struct/state/handle/API/prototypes | G01 |
| `docs/week01/kickoff.md` | Hiếu | cập nhật trạng thái thật + câu hỏi GV | G01 |
| `kernel/io_request.c` | Hiếu | pool, handle, poll/wait/release, stats, `io_init` | I01/I02 |
| `kernel/io_queue.c` | Lợi | pending queue, FCFS, `enqueue_seq`, dispatcher | L01 |
| `kernel/virtio_disk.c` | Hoàng | owner tag, try-submit, IRQ completion/reclaim, lock accessor | H01/H02 |
| `kernel/defs.h`, `Makefile`, `kernel/main.c` | Hiếu | khai báo, object mới, `io_init()` sau `virtio_disk_init()` | I01 |

Thứ tự merge đề xuất (mỗi PR **phải build xanh** sau khi merge vào main):
`G01 header` → `H01 accessor + owner tag + try-submit` → `I01 pool` (dùng
accessor) → `L01 queue` → `H02 IRQ` (cần I01) → `I02 wait/release` → `G02`.
H01 có thể tách PR nhỏ chỉ gồm `virtio_disk_io_lock()` + owner=STOCK để mở khóa
cho I01/I02 trước khi có try-submit đầy đủ. Không dùng `#ifdef` tạm trong main
để che symbol thiếu.

## 8. Quan hệ với tài liệu tuần 1 (thay thế phần nào)

- `docs/week01/decisions_report.md` §3.2–§3.3 (API `aio_read_submit(dev, sector,
  kbuf, nbytes)`, caller-owned `kbuf`): **được thay thế** bởi D2/D3 ở đây.
  Bản mô tả cũ giữ làm lịch sử; không dùng để code.
- `docs/week01/async-design.md` (một `io_lock` chung, pool-owned buffer):
  thống nhất với D2/D6; API lấy theo §3 ở đây (khác `aio_*` mô tả cũ).
- `docs/architecture.md` §2.6/§2.7 đã trỏ về contract này.
- `docs/week01/io-path.md` vẫn đúng cho phần stock/lock/IRQ; dùng làm nguồn
  phân tích driver, không phải contract async.

**Chưa chốt / không tự quyết:** syscall user-space hay kernel API (Q3); READ-only
có đủ phạm vi học phần không (Q2); SCAN/LOOK (Q4); phạm vi merge (Q5); rubric
(Q6); có cần mở rộng virtqueue để `max_inflight>2` (Q7). Các câu này giữ
`PENDING` ở §11, không ảnh hưởng D1–D10.

## 9. Câu hỏi mở cho GV + trạng thái PTO

### 9.1 Câu hỏi GV (tổng hợp vào PTO-7, không tạo card trùng)

| # | Câu hỏi | Owner hỏi | Trạng thái | Ghi chú cho tuần 2 |
| ---: | --- | --- | --- | --- |
| Q1 | Tag/commit xv6 chính thức của học phần? | Hoàng | **PENDING** | Đang dùng pin tạm `f780d785`; API sleep mới khác sách cũ |
| Q2 | Phạm vi I/O async: chỉ READ + WRITE đồng bộ có đạt yêu cầu không? | Hiếu | **PENDING** | MVP tuần 2 giả định READ-only |
| Q3 | Async API: kernel API + chương trình minh hoạ hay bắt buộc syscall user-space? | Hiếu | **PENDING** | Contract này chốt kernel API trước |
| Q4 | SCAN: SCAN hay LOOK; biên/đảo chiều thế nào? | Lợi | **PENDING** | Tuần 2 chỉ FCFS |
| Q5 | Phạm vi merge READ được chấp nhận (chỉ read, cùng ordering domain, tối đa bao nhiêu block)? | Hiếu | **PENDING** | Không merge trong tuần 2 |
| Q6 | Trọng số rubric Functionality/Testing/Measurement? | Hiếu | **PENDING** | Không suy từ ước lượng nội bộ |
| Q7 | Có cần mở rộng virtqueue/NUM để chứng minh `max_inflight>2`? | Hoàng | **PENDING** | Tuần 2 chỉ đo số thực, không hứa speedup |

Tất cả mục chưa có trả lời: giữ `PENDING`, không ghi "đã được duyệt".

### 9.2 Đối chiếu PTO (bước 5 của card)

Môi trường làm việc này **không có quyền truy cập Jira**; không thể tự đổi
trạng thái issue. Theo kế hoạch tuần 2 (S6, đọc ngày 27/10): PTO-1/3/5/6 `Done`;
PTO-4/7/9 `In Progress`; kế hoạch nhắc PTO-10/11 là subtask cần kiểm lại.
Bằng chứng repo để reviewer đối chiếu: 3 PR tuần 1 đã merge tới base `e809500`
(`ad539ab`, `918d1d5`, `e809500`); `docs/week01/io-path.md` (driver/lock),
`docs/week01/decisions_report.md` (buffer/API), `docs/week01/test-plan.md`
(test), `.xv6-commit` (pin tạm) — tương ứng các đầu ra PTO-4/9/10/11 trong hồ sơ
tuần 1.

Hành động còn lại (owner: **Lợi**, có tài khoản tracker): mở Jira, đối chiếu
từng issue/task tuần 1 với bằng chứng trên, quyết định `Done`/giữ `In Progress`
kèm ghi chú review; không tự đóng chỉ vì tài liệu đã có. Ghi kết quả vào
comment W2-G01 trước khi đóng card.

## 10. Tiêu chí nghiệm thu card W2-G01

- [x] Một contract duy nhất (§2–§6) + header build được; không còn hai mô hình
      buffer/khóa mâu thuẫn (D2, D6 thay thế tài liệu tuần 1 — §8).
- [x] Mỗi hàm có context, khóa vào/ra, hành vi khi hết tài nguyên (§3).
- [x] Ba kịch bản review trên giấy đã ghi (§5.1–§5.3).
- [x] Câu hỏi GV + PTO tổng hợp, ghi `PENDING` có owner (§9), không ghi đã duyệt.
- [x] Header contract compile độc lập (`-Wall -Werror`); base build + check-text
      PASS (bằng chứng ở §11).
- [ ] **Hoàng review** D6/D7, try-submit/IRQ/reclaim, đường stock: `PENDING`.
- [ ] **Lợi review** D5/D8, interface queue/`enqueue_seq`, EAGAIN: `PENDING`.
- [ ] Cả hai review **cùng revision** (commit của PR này) và ghi nhận xét/approve;
      khi đó mới đóng card. Nếu chưa thống nhất ⇒ dừng tích hợp module phụ thuộc;
      mỗi người vẫn có thể viết unit test/stub theo header này.

## 11. Bằng chứng thực thi của bản contract

| Lệnh | Kết quả | Log |
| --- | --- | --- |
| `riscv64-linux-gnu-gcc -fsyntax-only ... results/local/io_hdr_check.c` (gnu11, `-Wall -Werror`, 3 `_Static_assert` về size/NREQ/sector) | PASS | `results/week02/g01-contract-2026-10-30/logs/header-check.log` |
| `make clean && make -j$(nproc)` (base + header, header chưa vào build) | PASS | `.../logs/build.log` |
| `make check-text` | PASS | `.../logs/check-text.log` |
| `make test-fast` (2 case smoke, CPUS=3) | PASS | `.../logs/test-fast.log` |

Các test kernel T01–T13 **chưa** chạy (chưa có implementation I01/H01/H02/L01) —
ghi đúng trạng thái NOT RUN, không lấy contract làm kết quả test.

## 12. Chữ ký review (cùng một revision = commit của PR này)

| Vai trò | Người | Phạm vi bắt buộc review | Trạng thái | Ngày / comment |
| --- | --- | --- | --- | --- |
| Owner | Phạm Trung Hiếu | toàn bộ contract + header | ✅ đã soạn | 2026-10-30 |
| Reviewer driver/IRQ | Nguyễn Văn Hoàng | D6, D7, §3 driver, §5.2–§5.3, đường stock | ⬜ `PENDING` | — |
| Reviewer queue/FCFS | Phạm Quý Lợi | D5, D8, §3 queue, FCFS/`enqueue_seq`, EAGAIN | ⬜ `PENDING` | — |

Checklist review tối thiểu (mỗi reviewer tick vào comment PR):

- [ ] Đọc §1 (đối chiếu code) + D2/D6: đồng ý một buffer model, một lock domain.
- [ ] Kiểm hàm mình phụ trách trong bảng §3: context, khóa, EAGAIN đúng.
- [ ] Kiểm kịch bản §5.1/§5.2/§5.3 không còn lỗ hổng lost-wakeup/double-free.
- [ ] Kiểm merge order §7: PR của mình không làm main không build.
- [ ] Ghi rõ `approve` hoặc danh sách sửa; nếu sửa contract ⇒ bump revision và
      review lại, **không** đóng card khi chỉ có 1/3 chữ ký.

## 13. Change log

| Ngày | Revision | Nội dung |
| --- | --- | --- |
| 2026-10-27 | — | Kế hoạch tuần 2 (PDF) đặt card W2-G01; phát hiện mâu thuẫn buffer/lock ở tài liệu tuần 1 |
| 2026-10-30 | `week2/hieu-request` (commit của PR) | Bản contract đầu tiên: D1–D10, header `kernel/io_request.h`, 3 kịch bản review, câu hỏi GV/PTO; chờ Hoàng + Lợi review |
