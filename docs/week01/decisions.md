# Quyết định kỹ thuật sơ bộ — tuần 1

> **Owner:** Hiếu (§1–§4, T1-08) + Lợi (§5, T1-07). **Reviewer:** Hoàng.
> Mỗi quyết định phải ghi **lý do + hệ quả test**, không chỉ chép lại sách.
> Chỗ chưa chốt ghi `PENDING — cần GV` hoặc `PENDING — cần đo`.
>
> **Trạng thái (21/10/2026):** §1–§4 ✅ Hiếu hoàn thiện (Bước 4b trong
> [`hieu.md`](hieu.md)), đối chiếu trực tiếp code tại pin `f780d785`.
> §5 📝 Lợi điền. §7 📝 Hoàng review. Mọi kết luận dưới đây là **đề xuất**,
> chưa phải đặc tả chốt với giảng viên.

## 1. Buffer ownership hiện tại (Hiếu)

### 1.1 Sự kiện kiểm chứng từ code

- `struct buf` (`kernel/buf.h`): `valid`, `disk`, `dev`, `blockno`,
  `struct sleeplock lock`, `refcnt`, `prev/next` (LRU), `data[BSIZE]`.
- `BSIZE = 1024`, `NBUF = 30`, `MAXOPBLOCKS = 10`, `LOGBLOCKS = 30`
  (`fs.h`, `param.h`).
- `bread`/`bget`/`brelse`/`bpin`/`bunpin` ở `kernel/bio.c`;
  `bwrite` **chỉ** được `log.c` gọi (`write_log`, `install_trans`, `write_head`);
  `readi`/`writei` ở `kernel/fs.c`.

### 1.2 Ai giữ buffer, khoá nào, khi nào trả

| Tình huống | Ai giữ `struct buf` | Khoá | Khi nào `brelse`? | Bất biến / rủi ro |
| --- | --- | --- | --- | --- |
| `bread()` — block đã có trong cache | caller giữ `buf.lock` (sleeplock) và 1 refcnt | `bget` lấy `bcache.lock` để `refcnt++` rồi **release trước** khi `acquiresleep(&b->lock)` | sau khi dùng xong dữ liệu | refcnt>0 ⇒ buffer không bị chọn làm nạn nhân LRU |
| `bread()` — miss, recycle LRU | caller giữ `buf.lock`, refcnt=1 | `bcache.lock` khi chọn buf `refcnt==0`, gán `dev/blockno`, `valid=0`, rồi release; `acquiresleep` | sau khi dùng xong | nếu **không còn buf refcnt==0** → `panic("bget: no buffers")`: đây là giới hạn cứng của async pool nếu dùng bcache |
| `readi()` đang copyout | caller giữ `buf.lock` trong lúc `either_copyout` | sleeplock (được phép sleep/page-fault), **không** giữ spinlock | `brelse` ngay sau mỗi block (không giữ nhiều block) | copyout lỗi vẫn `brelse` trước khi trả |
| `writei()` sửa dữ liệu | caller giữ `buf.lock` + refcnt | sleeplock | `log_write(bp); brelse(bp);` | dữ liệu chưa xuống đĩa; log giữ tham chiếu bằng `bpin` |
| `log_write()` / `commit()` | **log** giữ buffer qua `refcnt` (`bpin`) | `log.lock` → `bcache.lock` (thứ tự này) | `bunpin` trong `install_trans`, sau đó `brelse` của caller | buffer bị ghim tới khi transaction cài xong → async read dùng chung bcache sẽ giành buffer với log |
| `bwrite` (log gọi) | caller giữ `buf.lock`; `holdingsleep()` panic nếu không | sleeplock → `vdisk_lock` | sau `virtio_disk_rw` trả về | ghi đồng bộ: caller ngủ tới completion |
| Buffer đang bay (`b->disk == 1`) | **thiết bị** sở hữu nội dung `b->data` | `vdisk_lock` bảo vệ cờ/trạng thái | chỉ `brelse` **sau khi** `b->disk == 0` | cấm mọi đọc/ghi `b->data` khi `b->disk==1`; `disk.info[idx0].b` giữ con trỏ buf |
| Completion (`virtio_disk_intr`) | driver/intr | `vdisk_lock` | caller tự `free_chain` + `brelse` sau khi tỉnh | intr **không** release sleeplock của caller, chỉ `b->disk=0; wakeup(b)` |
| Async request (đề xuất) | request + caller; xem §4.4 | `ioq.lock` (spinlock mới) + luật buffer của §4 | `aio_release` (sau khi DONE/ERROR) | slot không được tái dùng trước khi caller thu hồi; buffer phải sống tới completion |

### 1.3 Bất biến rút ra (dùng cho review + test)

1. `b->lock` (sleeplock) được giữ từ lúc `bget` trả về tới `brelse`; **không**
   giữ spinlock khi sleep.
2. `refcnt > 0` ⇒ buffer không bị recycle; `bpin/bunpin` là cách log ghim buffer
   qua transaction.
3. `valid = 1` chỉ sau khi device đọc xong block.
4. `b->disk == 1` ⇔ device sở hữu dữ liệu; chỉ driver/intr được đổi cờ này.
5. Thứ tự khoá: `bcache.lock` → `buf.lock` (sleeplock) → `disk.vdisk_lock`;
   thêm `log.lock` → `bcache.lock` (trong `log_write` gọi `bpin`).
6. Interrupt không sleep, không release sleeplock của process khác, không printf
   theo từng request; chỉ cập nhật trạng thái + `wakeup`.

### 1.4 Hệ quả cho thiết kế async

- Nếu mỗi request async **ghim buf trong bcache** thì ngân sách buffer là
  `NREQ + log_pins ≤ NBUF = 30`, trong khi `LOGBLOCKS = 30` có thể ghim tới 30
  buffer → rất dễ `panic("bget: no buffers")` khi vừa chạy usertests vừa async.
  ⇒ **Không** dùng bcache buffer làm buffer DMA cho async ở bản đầu.
- Đề xuất: request sở hữu **buffer riêng** (kernel memory, pool cố định, xem
  §4.3) → không giành buffer với log/cache; đổi lại async read **không populate
  bcache** (coherence), chỉ dùng cho data blocks/demo/benchmark. Đây là đánh đổi
  cần review (PENDING — Hoàng + GV xem có chấp nhận không).
- Không DMA trực tiếp vào user pointer: chỉ `copyin`/`copyout` trong process
  context (submit/wait), xem §4.4.

## 2. Write path & logging (Hiếu)

### 2.1 Chuỗi thực tế (đã đối chiếu `kernel/log.c`, `kernel/bio.c`, `kernel/fs.c`)

```text
writei()
  → bread()                      (buf.lock, refcnt)
  → either_copyin(dữ liệu user/kernel → b->data)
  → log_write(b)                 (absorption theo blockno; bpin; lh.n++)
  → brelse(b)                    (refcnt-- nhưng log vẫn ghim)

end_op() khi outstanding == 0
  → commit()
      → write_log()              (bread log block + bread home; memmove;
                                  bwrite(log block) — 1 I/O đồng bộ/block)
      → write_head()             (bwrite header — ĐIỂM COMMIT thật)
      → install_trans(0)         (bread log block + bread home; memmove;
                                  bwrite(home); bunpin(home))
      → lh.n = 0
      → write_head()             (xoá header)
```

Điểm quan trọng: **`bwrite` chỉ được gọi từ log**, và mỗi `bwrite` là một
`virtio_disk_rw` chờ completion xong mới trả → thứ tự ghi trên đường hiện tại là
thứ tự chương trình.

### 2.2 Vì sao giai đoạn đầu chỉ merge read, write giữ đồng bộ + fence

- Recovery của xv6 dựa vào **thứ tự**: log data blocks phải bền **trước** header;
  home location chỉ được ghi **sau** khi header đã commit. Nếu scheduler đảo thứ
  tự write, một cú crash giữa chừng có thể làm header trỏ tới log block chưa
  bền (mất dữ liệu) hoặc home block ghi đè dữ liệu chưa commit (hỏng FS).
- Buffer cache + log absorption cho phép **cùng một block được sửa nhiều lần**
  trong transaction; ghi sớm/đảo thứ tự làm lộ dữ liệu trung gian chưa commit.
- Vì vậy: **bản đầu chỉ merge/reorder read**; write vẫn đi qua wrapper đồng bộ
  (submit → wait) đúng như stock. Đây cũng là tinh thần mục 4 của kế hoạch.

### 2.3 Write fence đề xuất (nếu sau này mở async write)

| Quy tắc | Nội dung |
| --- | --- |
| W1 | Write **không** vào scheduler như read; wrapper đồng bộ tự submit + wait. |
| W2 | Nếu buộc phải async write: write là **barrier** — chỉ dispatch khi không còn request khác INFLIGHT và các read xếp trước nó đã dispatch; chờ write complete rồi mới dispatch request kế tiếp. |
| W3 | `commit()` là fence cứng: không được dispatch bất kỳ request nào chen giữa các `bwrite` của một lần commit. |
| W4 | Deadline/FCFS/SCAN chỉ áp cho read; write không đổi thứ tự tương đối. |
| W5 | Test: chạy `usertests -q`/`grind` + `test-xv6.py crash` (log recovery) sau khi mở async write; CPUS=1/4. |

Trạng thái: **W1 là quyết định bản đầu**; W2–W4 `PENDING — cần GV` (mục "phạm vi
merging/write fence") và chỉ làm sau khi có mô hình phụ thuộc + test riêng.

### 2.4 Ảnh hưởng tới scheduler

- Queue phần mềm chỉ chứa **read** ở bản đầu; `write` đi thẳng wrapper đồng bộ.
- Nếu GV yêu cầu write cũng vào scheduler: phải có ordering domain + fence như
  W2, và deadline cho write phải công bố riêng (không trộn với read).
- Test tương ứng: `merge-*` chỉ read; thêm case `write-fence` khi mở W2.

## 3. Completion-before-wait (Hiếu)

### 3.1 Cơ chế stock (đối chiếu `virtio_disk.c`, `proc.c`)

```c
// virtio_disk_rw (rút gọn)
b->disk = 1;                      // device sở hữu
disk.info[idx[0]].b = b;
disk.avail->ring[...] = idx[0];
io_fence();
disk.avail->idx += 1;
io_fence();
*R(VIRTIO_MMIO_QUEUE_NOTIFY) = 0;

while (b->disk == 1) {            // vẫn giữ disk.vdisk_lock
  sleep_prepare(b);               // đăng ký channel TRƯỚC khi mở khoá
  release(&disk.vdisk_lock);
  sleep();
  acquire(&disk.vdisk_lock);
}
disk.info[idx[0]].b = 0;
free_chain(idx[0]);

// virtio_disk_intr
while (disk.used_idx != disk.used->idx) {
  id = disk.used->ring[...].id;
  if (disk.info[id].status != 0) panic("virtio_disk_intr status");
  b = disk.info[id].b;
  b->disk = 0;
  wakeup(b);                      // đánh thức đúng channel là b
  disk.used_idx++;
}
```

### 3.2 Vì sao `sleep_prepare` phải nằm trong vùng khoá

Timeline (2 CPU):

```text
CPU0 (caller, đang giữ vdisk_lock)          CPU1 (interrupt)
b->disk == 1  → thấy cần ngủ
sleep_prepare(b)  → p->chan = b
release(vdisk_lock)  ─────────────────────▶  acquire(vdisk_lock)
                                             b->disk = 0
                                             wakeup(b): p->chan == b → p->chan = 0
                                             release
sleep() → p->chan == 0 → KHÔNG ngủ, trả về ngay
```

- Nếu `sleep_prepare` gọi **sau** `release`: interrupt có thể chạy giữa hai bước,
  `wakeup` xảy ra khi `p->chan` chưa đăng ký ⇒ **mất wakeup** (deadlock).
- Việc kiểm tra điều kiện (`b->disk == 1`) và `sleep_prepare` nằm cùng vùng khoá
  `vdisk_lock` là điều kiện đủ để không mất wakeup với API mới.
- `sleep()` kiểm tra `p->chan != 0` dưới `p->lock`; `wakeup()` xoá `p->chan` và
  set RUNNABLE nếu đã SLEEPING → "complete trước wait" không mất tín hiệu.

### 3.3 Quy tắc cho interrupt (áp dụng cả stock lẫn async)

1. **Không sleep**, không `acquire` sleeplock; chỉ spinlock ngắn (`vdisk_lock`,
   `p->lock` trong `wakeup`, `ioq.lock` của dự án).
2. Không copyin/copyout, không `kalloc`/`kfree`, không printf theo từng request
   trong benchmark (chỉ counter).
3. Completion phải đánh dấu state/`b->disk=0` **trước** `wakeup`; wakeup sau khi
   đã cập nhật trạng thái để waiter thấy dữ liệu đúng.
4. Kiểm tra status của device; status khác 0 phải chuyển request sang ERROR (kế
   hoạch error path — Hoàng phụ trách driver), không panic trong bản async.
5. Completion đúng **một lần**: intr chỉ xử lý state INFLIGHT; merged request chỉ
   complete parent một lần rồi chia cho children.

### 3.4 Áp dụng cho async request layer

```c
// waiter (process context)
acquire(&ioq.lock);
for (;;) {
  r = lookup_handle(id);            // kiểm tra generation để chống ABA
  if (!r) { release; return -ENOENT; }
  if (r->state == DONE || r->state == ERROR) break;
  sleep_prepare(r);                 // đăng ký channel TRƯỚC khi mở ioq.lock
  release(&ioq.lock);
  sleep();
  acquire(&ioq.lock);
}
status = r->status; release(&ioq.lock);
copyout_if_needed(...);             // process context
```

- `complete_request(r, status)` chạy trong intr/softirq: `acquire(ioq.lock)`,
  kiểm tra `r->state == INFLIGHT`, set DONE/ERROR + counters, `wakeup(r)`,
  release. Không copy dữ liệu ở đây.
- Với merged request: completion parent đánh dấu DONE cho từng child đúng một
  lần (counter child), wakeup từng child.
- Buffer copyout chỉ ở `aio_wait` (hoặc `aio_poll` khi state DONE? — chốt: poll
  **không** copy, chỉ trả trạng thái; wait mới copy, xem §4.2).

### 3.5 Test chứng minh

| Case dự kiến | Oracle |
| --- | --- |
| `aio-complete-before-wait` | submit → chờ completion xảy ra (log/counter) → mới gọi wait; wait trả ngay, dữ liệu đúng, không treo |
| `aio-wait-multiple` | 2 request, wait request đã xong trước rồi wait request còn lại |
| `aio-submit-before-complete` | submit trả trước completion; caller làm việc khác rồi wait |
| `aio-kill-exit` | kill process khi còn INFLIGHT: không panic, không leak buffer/descriptor, tài nguyên về ban đầu |
| Lặp CPUS=1/4, ≥10 lần | không deadlock/mất wakeup |

Các case trên thuộc `docs/week01/test-plan.md` (tag `async`); hiện **NOT RUN**
vì chưa có code tuần 2–5.

## 4. API async đề xuất (Hiếu)

### 4.1 Phạm vi bản đầu (đề xuất, chờ GV xác nhận)

| Quyết định | Giá trị bản đầu | Lý do |
| --- | --- | --- |
| Chiều I/O | **chỉ read** (write theo wrapper đồng bộ, §2) | tránh rủi ro crash consistency của log |
| Đơn vị | `sector` 512B; `sector % 2 == 0`, `nbytes % BSIZE == 0` | ví dụ mở: `virtio_disk_rw` tính `sector = blockno*2` |
| Buffer | **kernel buffer** do caller sở hữu; API core không nhận user pointer | tách tầng: syscall (nếu có) tự copyin/copyout |
| Tầng API | core kernel API trước; **syscall user-space là PENDING — cần GV** | tránh làm tầng syscall khi chưa chốt R06 |
| Queue depth | tối đa 2 chain INFLIGHT (giới hạn `NUM=8`, 3 desc/request) | bằng chứng R01 cần `max_inflight >= 2` |
| Merge | chỉ read, cùng device/op, sector liền kề; giới hạn xem §4.6 | R05 |

### 4.2 Interface (kernel API đề xuất)

| Hàm | Semantics | Trả về | Buffer lifetime | Lỗi |
| --- | --- | --- | --- | --- |
| `int aio_read_submit(uint dev, uint sector, void *kbuf, uint nbytes)` | kiểm tra tham số, cấp slot pool, ghi request vào pending queue; **trả trước khi device xong**; có thể merge với request QUEUED liền kề | `handle > 0` | `kbuf` (kernel memory) do caller giữ hợp lệ tới khi wait/release xong; kernel không copy | `-EAGAIN` pool/queue đầy, `-EINVAL`, `-ERANGE`, `-ENODEV` |
| `int aio_poll(int handle)` | kiểm tra trạng thái, **không block, không copy dữ liệu** | `0` chưa xong, `1` DONE, `<0` lỗi/không tồn tại | không đổi | `-ENOENT` |
| `int aio_wait(int handle)` | chờ tới DONE/ERROR (xử lý complete-before-wait theo §3.4); trả trạng thái; **nếu có tầng user: copy dữ liệu ra user ở đây** | `0` OK, `<0` lỗi | caller thu hồi sau khi trả về | `-EIO`, `-ENOENT` |
| `int aio_release(int handle)` | trả slot pool sau khi caller đã dùng xong kết quả; tăng `generation` để chống dùng lại handle cũ | `0` / `<0` | giải phóng tham chiếu request; buffer do caller tự quản | `-EBUSY` nếu còn INFLIGHT, `-ENOENT` |

Handle = `(generation << 8) | index` (hoặc struct); mọi API kiểm tra generation
để tránh ABA sau khi slot được tái sử dụng.

### 4.3 Pool & giới hạn

- `NREQ` (ví dụ 16) request slot cấp phát tĩnh lúc init; mỗi slot có buffer
  kernel riêng nếu cần (xem §4.4) — **không** `kalloc` trong interrupt.
- Queue depth phần mềm đo được; **INFLIGHT tối đa = 2** do `NUM=8` descriptor,
  3 desc/request. Muốn 4 INFLIGHT phải chứng minh giới hạn thiết bị/queue — ghi
  kết quả đo, không giả định.
- `MAX_IO_BYTES` bản đầu = `4 * BSIZE` (4 KB, 1 page): request chỉ cần
  1 data descriptor → 3 desc/request, giữ 2 chain đồng thời.
- Merge mở rộng lên `8 * BSIZE` (8 KB) cần 2 segment (2 page) và chain 4 desc;
  khả thi về số descriptor (2 chain × 4 = 8) nhưng cần driver hỗ trợ segment
  list → **PENDING — Hoàng** (driver) + đo thực tế.
- Tổng buffer cần: `NREQ × MAX_IO_BYTES` (16 × 4 KB = 64 KB) — nằm ngoài `NBUF`,
  không giành buffer cache/log.

### 4.4 Buffer ownership & copy rules

| Thời điểm | Buffer ở đâu | Quy tắc |
| --- | --- | --- |
| `submit` | kernel buffer của caller (bản đầu) | tham số phải hợp lệ, sector/nbytes trong capacity; lưu con trỏ + length + owner pid |
| QUEUED/INFLIGHT | request giữ tham chiếu; device DMA vào `kbuf` | cấm caller đọc/ghi/sửa/free `kbuf`; cấm tái dùng cho request khác |
| DONE | dữ liệu đã nằm trong `kbuf` | caller chỉ được đọc sau khi `aio_wait` trả OK (với tầng user: sau copyout) |
| release | slot về FREE; generation++ | nếu còn INFLIGHT → `-EBUSY` |
| Process exit khi INFLIGHT | request có `owner pid` + cờ `abandoned` | không copyout cho process đã chết; completion vẫn phải chạy, giải phóng buffer/slot, không leak; test `aio-kill-exit` |

Nếu GV yêu cầu API user-space: **không** DMA vào user page; syscall layer giữ
một buffer kernel/request, `copyin` trước khi submit (write sau này) và
`copyout` trong `aio_wait` sau completion. Không giữ user pointer sống sau khi
process thoát.

### 4.5 Mã lỗi & quy ước

| Mã | Khi nào | Caller xử lý |
| --- | --- | --- |
| `-EAGAIN` | pool/queue đầy, không cấp được slot/descriptor | retry sau, hoặc giảm tải; không chặn trong interrupt |
| `-EINVAL` | `kbuf` NULL, `sector/nbytes` không đúng bội số | sửa tham số |
| `-ERANGE` | ngoài capacity device (`FSSIZE * 2` sector) | clamp theo capacity thật |
| `-EIO` | device status != 0, lỗi completion | báo lỗi, không dùng dữ liệu |
| `-ENOENT` | handle sai/generation cũ/đã release | bug ở caller hoặc double-release |
| `-EBUSY` | release khi chưa DONE | chờ `aio_wait` trước |

### 4.6 Điều kiện merge (read, bản đầu)

Hai request merge được khi: cùng device, cùng op READ, **sector liền kề** (request
sau bắt đầu đúng sector kết thúc request trước), cùng ordering domain, tổng
`nbytes` ≤ `MAX_MERGE_BYTES`, không vượt giới hạn segment/descriptor.
Hệ quả test: merge phải gửi **một lệnh thiết bị** (không phải gom list rồi submit
từng lệnh), completion trả cho từng child đúng một lần, checksum từng child đúng;
hỗ trợ cả append và prepend.

### 4.7 Ranh giới module (cần chốt với Hoàng/Lợi tuần 2)

| Module | Owner | Interface đề xuất |
| --- | --- | --- |
| Driver/descriptor/completion | Hoàng | `int vdisk_submit(struct io_request *r)` — cấp descriptor + notify, **không sleep**, trả `-EAGAIN` nếu hết descriptor; completion path set `r->status`, `r->state` (hoặc gọi hook) |
| Queue/scheduler/policy | Lợi | `ioq_enqueue`, `ioq_pick(policy)`, `ioq_set_policy`, biến đếm queue; lock `ioq.lock` thống nhất với §1 |
| Pool/API/merge/buffer/metrics | Hiếu | `aio_*`, cấp slot, merge, counters, copyout (nếu có tầng user) |

Không được hai module cùng sửa một request state mà không qua lock/hàm của owner.

### 4.8 Đo đạc (counter & timestamp)

- Timestamp: dùng `r_time()` (`kernel/riscv.h`, đọc CSR `time`) thay cho `ticks`
  (tick hiện tại quá thô để tính latency) — ghi rõ đơn vị là *time units* và
  cách quy đổi ra giây (tần số timebase; xác nhận bằng QEMU virt trước khi báo
  số).
- Counter tối thiểu: `max_inflight`, `inflight`, `queued`, `merge_ratio`,
  `descriptor_exhausted`, `request_error`, `policy_switch` (phần policy do Lợi).
- Đo: `t_enqueue`, `t_dispatch`, `t_complete` ⇒ queue_wait, service, latency.

### 4.9 Câu hỏi còn mở (xem §6)

1. API bắt buộc là **syscall user-space** hay kernel API + chương trình minh hoạ?
2. Có cần async **write** không, hay chỉ read + write fence?
3. Có chấp nhận async read đi **ngoài buffer cache** (không populate cache) không?
4. GV có yêu cầu queue depth > 2 không (giới hạn descriptor hiện tại) hay chấp
   nhận `max_inflight = 2` là đủ bằng chứng R01?

## 5. Policy & lock (Lợi điền — Hiếu review)

Dữ kiện Hiếu đã kiểm chứng từ code (Lợi dùng, không cần suy lại):

- `NUM = 8`, 3 descriptor/request ⇒ **tối đa 2 chain** đồng thời; caller thứ 3
  ngủ chờ `disk.free[0]` (channel là địa chỉ `disk.free[0]`).
- Thứ tự khoá: `bcache.lock` → `buf.lock` → `disk.vdisk_lock`; thêm
  `log.lock` → `bcache.lock`.
- Điểm **enqueue** (đề xuất): `aio_read_submit` → `ioq_enqueue` (dưới `ioq.lock`).
- Điểm **dispatch**: scheduler chọn request QUEUED → `vdisk_submit` (cấp
  descriptor + notify); nếu `-EAGAIN` thì quay lại queue, chờ tín hiệu descriptor
  free (channel do Hoàng định nghĩa).
- Điểm **completion**: `virtio_disk_intr` → completion hook → state DONE/ERROR →
  `wakeup(request)`.
- Cần công bố: tie-break FCFS, biên SCAN (sector capacity), deadline read/write,
  batch limit, quy tắc reset khi đổi policy.

| Nội dung | Kết luận (Lợi điền) |
| --- | --- |
| `NUM`/chain cost | (dữ kiện trên) |
| Lock order | (dữ kiện trên) |
| Điểm enqueue/dispatch | (dữ kiện trên) |
| FCFS: tie-break, oracle test | |
| SCAN: biên capacity, chiều quét, khác LOOK ở đâu | |
| Deadline: hạn đọc/ghi, batch limit, chống starvation | |
| Đổi policy khi đang chạy: dữ liệu nào giữ, reset gì, counter nào | |

## 6. Câu hỏi mở / cần GV

| # | Câu hỏi | Đề xuất mặc định nếu chưa có trả lời | Owner | Trạng thái |
| ---: | --- | --- | --- | --- |
| 1 | Async API phải là **syscall user-space** hay kernel API + chương trình minh hoạ? | Làm core kernel API trước; syscall wrapper sau (tách tầng) | Hiếu | PENDING |
| 2 | Merging chỉ read, hay cho phép cả write kèm fence? | Chỉ read + write đồng bộ | Hiếu | PENDING |
| 3 | Có cần async write API không? | Không ở bản đầu | Hiếu | PENDING |
| 4 | Async read có được đi ngoài buffer cache (không populate cache) không? | Có, ghi rõ hạn chế coherence trong báo cáo | Hiếu | PENDING |
| 5 | Queue depth/inflight > 2 có bắt buộc không (giới hạn NUM=8)? | `max_inflight = 2` là bằng chứng R01; depth queue 1/2/4 là tham số benchmark | Hoàng | PENDING |
| 6 | SCAN hay LOOK là định nghĩa học phần mong đợi? | Gọi đúng tên theo định nghĩa GV | Lợi | PENDING |
| 7 | Tag xv6 chính thức (API sleep cũ/mới)? | Pin hiện tại `f780d785` (API mới) | Hoàng | PENDING |

## 7. Review của Hoàng

- [ ] §1 Buffer ownership khớp code (`bio.c`, `virtio_disk.c`); bảng không tự suy
- [ ] §2 Kết luận write synchronous/fence hợp lý; không hứa async write bản đầu
- [ ] §3 Completion-before-wait dùng đúng `sleep_prepare()`/`sleep()`/`wakeup()`
  (không dùng mẫu `sleep(chan, lock)` của bản cũ)
- [ ] §4 API có quy tắc buffer lifetime, lỗi queue đầy, handle generation,
  process-exit/abandoned request
- [ ] §4.3 giới hạn `NREQ`/`MAX_IO_BYTES`/inflight đúng ngân sách descriptor,
  không làm `bget: no buffers`
- [ ] §4.7 ranh giới module rõ (driver/queue/pool) — không cùng sửa state
- Nhận xét: TODO
- Kết luận: ☐ Approve ☐ Cần sửa (ghi rõ mục)

## 8. Bằng chứng & cách kiểm chứng lại

Đã đối chiếu code tại pin `f780d785` (`.xv6-commit`). Commands để review lại:

```bash
grep -n "^bget\|^bread\|^bwrite\|^brelse\|^bpin\|^bunpin" kernel/bio.c
grep -n "begin_op\|log_write\|end_op\|commit\|write_log\|write_head\|install_trans" kernel/log.c
grep -n "readi\|writei" kernel/fs.c
grep -n "virtio_disk_rw\|virtio_disk_intr\|b->disk\|wakeup" kernel/virtio_disk.c
grep -n "sleep_prepare\|^sleep\|^wakeup" kernel/proc.c kernel/sleeplock.c
grep -n "NUM\|BSIZE\|NBUF\|LOGBLOCKS\|MAXOPBLOCKS\|FSSIZE" kernel/virtio.h kernel/fs.h kernel/param.h
```

Tham chiếu chéo: [`architecture.md`](../architecture.md) mục 1–2, test case tương
ứng trong [`test-plan.md`](test-plan.md) tầng T3–T4, và kết quả baseline
(`results/baseline/2026-10-19_222935/`) để so sánh khi có code.
