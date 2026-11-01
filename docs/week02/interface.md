# W2-G01 — Đặc tả kỹ thuật: Giao diện Request, Cơ chế Buffer và Quy tắc Đồng bộ

> **Mã công việc:** W2-G01 (CARD 1/9) — *Chốt interface request, buffer ownership và quy tắc khóa*.  
> **Người thực hiện:** Phạm Trung Hiếu (MSSV: 20233402) · **Nhánh làm việc:** `week2/hieu-request`.  
> **Base commit:** `e809500` (origin/main sau tuần 1) · **Pin xv6 tạm thời:** `f780d785…` (chờ GV xác nhận tag chính thức).  
> **Người rà soát (Reviewers):** Nguyễn Văn Hoàng (G01/I01/I02), Lê Minh Lợi (G01) — *Trạng thái: PENDING*.  
> **File mã nguồn nguồn sự thật (Single Source of Truth):** [`kernel/io_request.h`](../../kernel/io_request.h).

---

## 1. Bối cảnh kỹ thuật và Đối chiếu mã nguồn

### 1.1 Vấn đề cốt lõi cần giải quyết
Trong Tuần 1, hai tài liệu thiết kế xuất hiện mâu thuẫn lớn đe dọa khả năng tích hợp:
- [`docs/week01/async-design.md`](../week01/async-design.md): Đề xuất Request Pool sở hữu buffer và quy về một khóa chung.
- [`docs/week01/decisions_report.md`](../week01/decisions_report.md): Đề xuất tiến trình gọi (caller) tự sở hữu `kbuf` và chưa chốt cơ chế đồng bộ khóa.

Nếu ba thành viên lập trình song song trên hai mô hình trái ngược nhau, hệ thống sẽ rơi vào tình trạng không thể ghép nối hoặc phát sinh lỗi deadlock AB-BA. Bản hợp đồng này (Contract) chuẩn hóa toàn bộ giao diện và cơ chế đồng bộ trước khi viết code.

### 1.2 Bảng đối chiếu mã nguồn gốc xv6
Nhóm đã rà soát trực tiếp trên commit `e809500` để rút ra các kết luận nền tảng:

| Thành phần nguồn | Hành vi hiện tại của xv6 | Nguyên tắc áp dụng vào Contract |
| :--- | :--- | :--- |
| `kernel/buf.h` & `bio.c` | `struct buf` dùng chung cho cả buffer cache và vùng DMA. Khóa `bcache.lock` và `b->lock` độc lập. | **D2 & D6:** Không tái dùng `struct buf` làm DMA async; `bcache.lock` độc lập, không lồng vào `io_lock`. Async READ MVP chưa thay thế `bread()`. |
| `kernel/virtio_disk.c` | Mảng `info[head]` lưu con trỏ buffer và status. Hàm `virtio_disk_rw` cấp 3 descriptor, caller tự thu hồi chain (`free_chain`). | **D7:** Mở rộng `info[head]` thêm cờ `owner` (`STOCK` vs `ASYNC`). Descriptor của stock do caller giải phóng, descriptor của async do ngắt IRQ giải phóng. |
| `kernel/proc.c` | Hỗ trợ chuỗi đồng bộ mới: `sleep_prepare(chan)` → `sleep()` → `wakeup(chan)`. | **D9:** Áp dụng mẫu chuẩn `sleep_prepare` khi còn giữ khóa để loại trừ triệt để khe hở mất tín hiệu đánh thức (lost-wakeup). |
| `kernel/fs.h` & `param.h` | `BSIZE=1024`, `ROOTDEV=1`, `FSSIZE=2000`. | **D3:** Đơn vị giao diện công khai là `blockno`, chỉ đổi sang sector (`blockno * 2`) tại một vị trí duy nhất trong driver. |

---

## 2. Mười quyết định thiết kế then chốt (D1 – D10)

### D1 — Phạm vi phiên bản thử nghiệm (MVP Scope)
- **Quyết định:** Giao diện C mức kernel, hỗ trợ duy nhất thao tác **READ 1 block** (`BSIZE = 1024 bytes`), trên một thiết bị gốc (`ROOTDEV`), hàng đợi điều phối **FCFS**. Các lệnh WRITE và hệ thống log giữ nguyên đường dẫn đồng bộ truyền thống.
- **Phân tích đánh đổi:** Tập trung kiểm chứng luồng bất đồng bộ cốt lõi; hoãn việc xây dựng system call người dùng, WRITE bất đồng bộ hoặc gom cụm I/O (merge) sang giai đoạn sau khi có ý kiến của giảng viên.

### D2 — Cơ chế sở hữu bộ đệm: Staging Buffer do Pool sở hữu
- **Quyết định:** Mỗi slot request sở hữu cố định một vùng đệm trung chuyển 1024 byte nằm tĩnh trong phân vùng BSS (`uchar data[BSIZE]` tích hợp trực tiếp trong `struct io_request`).
  - Caller **không** cấp phát bộ đệm, **không** giải phóng bộ đệm.
  - Sau khi request hoàn tất (`DONE`), caller nhận con trỏ dữ liệu chỉ đọc thông qua hàm `aio_data()`.
  - Con trỏ này lập tức hết hiệu lực sau khi caller gọi `aio_release()`.
- **Lý do chọn:** Vòng đời bộ đệm gắn chặt với vòng đời request; địa chỉ DMA bất biến trong suốt quá trình xử lý; tránh lỗi use-after-free khi caller bị hủy (kill) đột ngột trong lúc DMA đang hoạt động.
- **Lý do loại bỏ `caller-owned kbuf`:** Nếu caller sở hữu bộ đệm, hệ điều hành phải duy trì bộ đếm tham chiếu (refcount), kiểm soát tiến trình thoát bất ngờ và xử lý nhiều nhánh lỗi phức tạp, vượt quá giới hạn thời gian tuần 2.

> **Quy tắc truy cập `req->data` theo trạng thái:**
> - `ALLOCATED`: Chỉ Request Layer nội bộ được khởi tạo.
> - `QUEUED` / `INFLIGHT`: Cấm tuyệt đối CPU can thiệp (chỉ phần cứng DMA đọc/ghi).
> - `DONE`: Caller được cấp quyền **chỉ đọc** sau khi `aio_wait() == 0` hoặc `aio_poll() == 1`.
> - `ERROR`: Vùng nhớ không hợp lệ, cấm truy cập dữ liệu.
> - Sau `aio_release()`: Con trỏ hết hạn, slot được thu hồi về trạng thái tự do (`FREE`).

### D3 — Đơn vị địa chỉ: `blockno` ở API, quy đổi Sector tại Driver
- **Quyết định:** Giao diện công khai nhận đơn vị địa chỉ khối hệ thống tệp `blockno`. Việc nhân đôi sang sector (`sector = blockno * 2`) chỉ được thực hiện **duy nhất tại một vị trí** trong hàm `virtio_disk_try_submit_read()`.
- **Lý do chọn:** Loại trừ triệt để nguy cơ cả hai tầng cùng nhân đôi địa chỉ (lỗi double multiply bug). Submit sẽ từ chối ngay nếu `dev != ROOTDEV` (`-ENODEV`) hoặc `blockno >= FSSIZE` (`-ERANGE`).

### D4 — Định danh Request bằng Handle có Thế hệ (Generation)
- **Quyết định:** Định nghĩa cấu trúc định danh:
  ```c
  struct io_handle { int id; uint gen; };
  ```
  - `id`: Chỉ số slot trong pool, thuộc dải `[0, IO_NREQ - 1]`.
  - `gen`: Thế hệ của slot, khởi tạo bằng 1, tự động tăng sau mỗi lần giải phóng và không bao giờ nhận giá trị 0.
- **Lý do chọn:** Ngăn chặn hiện tượng ABA (Stale Handle). Mọi hàm API đều xác thực tính khớp của cặp `(id, gen)` trước khi dereference con trỏ. Handle cũ trỏ vào slot đã tái sử dụng sẽ bị từ chối với mã lỗi `-ENOENT` mà không gây panic.

### D5 — Tách biệt hai vòng đời Request và Descriptor
Hệ thống phân định độc lập hai vòng đời:
1. **Vòng đời Request (Tầng phần mềm):**  
   `IO_SLOT_FREE → IO_ALLOCATED → IO_QUEUED → IO_INFLIGHT → IO_DONE / IO_ERROR → IO_SLOT_FREE`  
   *(Trạng thái DONE/ERROR vẫn chiếm giữ slot cho đến khi caller chủ động gọi `aio_release()`)*.
2. **Vòng đời Descriptor (Tầng phần cứng virtio):**  
   `DESC_FREE → DESC_RESERVED → DESC_PUBLISHED → DESC_USED → DESC_RECLAIMED → DESC_FREE`  
   *(Một head descriptor có thể được tái sử dụng cho request B ngay sau khi ngắt thu hồi, dù caller của request A chưa release slot)*.

### D6 — Một miền khóa duy nhất (Single Lock Domain)
- **Quyết định:** Sử dụng đúng **một spinlock duy nhất** cho toàn bộ nguyên mẫu: `io_lock` (đồng nhất với `disk.vdisk_lock`, truy cập qua hàm `virtio_disk_io_lock()`).
- **Phạm vi bảo vệ:** (1) Request pool, state, gen, waiters; (2) Pending queue, thứ tự FCFS; (3) Allocator descriptor, avail/used ring; (4) Bản đồ sở hữu `info[head]`; (5) Cơ chế đồng bộ `b->disk` của stock.
- **Lý do loại bỏ phương án hai khóa riêng (`ioq.lock` và `vdisk_lock`):**  
  Thao tác submit nạp request đi theo chiều `ioq.lock → vdisk_lock`. Nếu ngắt IRQ completion giữ `vdisk_lock` rồi lấy `ioq.lock` để đánh thức tiến trình, sẽ tạo ra chu kỳ nghịch chiều `vdisk_lock → ioq.lock` gây **deadlock AB-BA**. Quy về một khóa đảm bảo tính đúng đắn tuyệt đối.
- **Thứ tự khóa một chiều (không lồng nhau):**  
  `bcache.lock (độc lập)` · `buf.lock (sleeplock) → io_lock → proc->lock`. Cấm ngủ khi đang giữ `io_lock`.

### D7 — Giao ước phân quyền giữa Driver và Request Layer
- **Nhãn sở hữu (Owner Tag):** Mỗi phần tử `info[head]` gắn cờ `owner` (`FREE`, `STOCK`, `ASYNC`).
- **Quy tắc thu hồi Descriptor (`free_chain`):**
  - **Luồng STOCK:** Caller của hàm `virtio_disk_rw()` tự thu hồi chain sau khi thức dậy (như cũ).
  - **Luồng ASYNC:** Ngắt IRQ `virtio_disk_intr()` chủ động thu hồi chain ngay sau khi chép kết quả status.
  - *Cấm tuyệt đối việc thu hồi chung không xét owner để tránh lỗi double-free.*
- **Ba điểm kích hoạt Dispatcher:** (1) Sau khi enqueue tại `aio_read_submit`; (2) Trong ngắt IRQ sau khi thu hồi chain async; (3) Trong driver stock sau khi caller thu hồi chain stock.

### D8 — Chuẩn hóa mã lỗi Kernel
Áp dụng quy chuẩn mã lỗi âm kiểu Linux:

| Mã lỗi | Giá trị | Ý nghĩa và Ngữ cảnh phát sinh |
| :--- | :---: | :--- |
| `-EINVAL` | -22 | Tham số không hợp lệ, con trỏ NULL, hoặc gọi `aio_wait` ngoài process context. |
| `-ENODEV` | -19 | Thiết bị không phải `ROOTDEV`. |
| `-ERANGE` | -34 | Chỉ số khối vượt ngưỡng đĩa (`blockno >= FSSIZE`). |
| `-ENOENT` | -2 | Handle không hợp lệ hoặc đã hết hạn (stale handle). |
| `-EAGAIN` | -11 | Pool đầy lúc submit (không ngủ, không panic); hoặc thiếu descriptor trong driver. |
| `-EIO` | -5 | Lỗi phần cứng đọc đĩa từ thiết bị (device status ≠ 0). |
| `-EBUSY` | -16 | Release khi request chưa terminal hoặc còn waiter; hoặc gọi wait lần hai đồng thời. |

### D9 — Cơ chế Đồng bộ Wait/Wakeup và Chống Lost-Wakeup
- **Kênh chờ (Wait Channel):** Sử dụng trực tiếp con trỏ `struct io_request *req`. Giới hạn đơn tiêu thụ (`waiters ∈ {0, 1}`).
- **Nguyên tắc chống mất tín hiệu đánh thức:**  
  Tầng ngắt cập nhật trạng thái `DONE/ERROR` và status **trước** khi gọi `wakeup(req)`.  
  Tiến trình chờ tuân thủ nghiêm ngặt chuỗi:  
  `Giữ io_lock → sleep_prepare(req) → nhả io_lock → sleep() → nhận lại io_lock`.  
  Nếu ngắt xảy ra ngay tại khe hở giữa `sleep_prepare` và `sleep`, hàm `sleep()` nhận thấy `p->chan == 0` và sẽ lập tức trả về mà không bị ngủ quên.
- **Fast-path:** Nếu request đã hoàn tất trước khi gọi `aio_wait()`, hàm lập tức trả về kết quả thành công mà không vào giấc ngủ.

### D10 — Bộ đếm thống kê và Bất biến kế toán
Hệ thống duy trì các bất biến kiểm tra được bằng test tự động:
1. `submitted == queued + inflight + done + error`.
2. `free_req == IO_NREQ - (queued + inflight + done + error)`. Khi pool đầy, submit trả `-EAGAIN` và chỉ tăng biến đếm `eagain_pool`, không làm thay đổi các biến khác.
3. Sau khi xả sạch hàng đợi và giải phóng hết: `free_req == IO_NREQ` (16) và `free_desc == NUM` (8).

---

## 3. Đặc tả Cấu trúc Dữ liệu và Giao diện API

### 3.1 Khai báo cấu trúc cốt lõi
*(Được định nghĩa tại [`kernel/io_request.h`](../../kernel/io_request.h))*

```c
#define IO_NREQ 16
#define IO_SECTORS_PER_BLOCK (BSIZE / 512)

struct io_handle {
  int id;       // Chỉ số slot: 0 .. IO_NREQ - 1
  uint gen;     // Thế hệ slot: >= 1 (tăng sau mỗi lần giải phóng)
};

struct io_request {
  int id;                  // Chỉ số slot cố định trong pool BSS
  uint gen;                // Thế hệ hiện tại của slot
  enum io_state state;     // Trạng thái (FREE, ALLOCATED, QUEUED, INFLIGHT, DONE, ERROR)
  enum io_op op;           // IO_OP_READ
  int status;              // 0: OK, >0: Lỗi phần cứng virtio, <0: Lỗi nội bộ
  uint dev;                // Thiết bị (ROOTDEV)
  uint blockno;            // Khối logic cần đọc
  uint enqueue_seq;        // Số thứ tự FCFS
  int next;                // Liên kết hàng đợi chờ
  int head;                // Head descriptor khi đang INFLIGHT
  uint t_enqueue, t_dispatch, t_complete; // Đo lường thời gian (ticks)
  uint waiters;            // Số tiến trình chờ (0 hoặc 1)
  uchar data[BSIZE];       // Vùng đệm DMA staging tĩnh (1024 bytes)
};
```

Ngân sách bộ nhớ: `sizeof(struct io_request) = 1080 B` × 16 slots = **17.280 B** trong phân vùng BSS. Không cấp phát động (`kalloc`) trong luồng xử lý.

### 3.2 Bảng ma trận Giao diện API

| Tên hàm | Ngữ cảnh (Context) | Trạng thái Khóa `io_lock` | Có chặn / ngủ? | Hành vi khi lỗi / cạn tài nguyên |
| :--- | :--- | :--- | :---: | :--- |
| `io_init()` | Boot CPU (1 lần) | Không giữ → Không giữ | Không | Khởi tạo tĩnh, không phát sinh lỗi |
| `aio_read_submit(dev, blockno, *out)` | Tiến trình (Process) | Tự acquire → release | **Không** | Trả `-EAGAIN` khi pool đầy; `-ENODEV`, `-ERANGE`, `-EINVAL` |
| `aio_poll(h)` | Mọi ngữ cảnh không ngủ | Tự acquire → release | Không | Trả 1 (DONE), 0 (bận), `-EIO` (lỗi đĩa), `-ENOENT` (stale) |
| `aio_wait(h)` | **Chỉ Process** | Acquire → nhả khi ngủ → acquire | **Có** | Trả 0 (DONE), `-EIO` (lỗi đĩa), `-EBUSY`, `-ENOENT`, `-EINVAL` |
| `aio_release(h)` | Tiến trình (Process) | Tự acquire → release | Không | Trả `-EBUSY` nếu chưa terminal / còn waiter; `-ENOENT` |
| `aio_data(h)` | Tiến trình (Process) | Acquire ngắn validate | Không | Trả con trỏ `req->data` hoặc `NULL` nếu handle lỗi |
| `io_get_stats(*out)` | Tiến trình (Process) | Tự acquire → release | Không | Truy vấn snapshot số liệu kế toán |
| `io_alloc_slot_locked()` | Nội bộ, **giữ io_lock** | Giữ → Giữ | Không | Trả `NULL` và tăng `eagain_pool++` khi hết slot |
| `io_lookup_handle_locked(h)` | Nội bộ, **giữ io_lock** | Giữ → Giữ | Không | Trả `NULL` và tăng `stale_handle++` nếu handle stale/sai |
| `io_release_locked(h)` | Nội bộ, **giữ io_lock** | Giữ → Giữ | Không | Thu hồi slot về FREE, tăng `gen++`, trả `-EBUSY` / `-ENOENT` |
| `virtio_disk_try_submit_read(req)` | Nội bộ, **giữ io_lock** | Giữ → Giữ | **Không** | Trả `-EAGAIN` và rollback nếu thiếu 3 descriptor |
| `virtio_disk_intr()` | **Ngắt phần cứng (IRQ)** | Tự acquire → release | **Không** | Cập nhật terminal, thu hồi desc async, kích hoạt dispatcher |
| `io_async_completed_locked(req, st)` | Nội bộ, **giữ io_lock** | Giữ → Giữ | Không | Đặt `DONE/ERROR`, ghi `status`, gọi `wakeup(req)` |

---

## 4. Vòng đời State Machine và Bất biến Hệ thống

```
+---------------+
| IO_SLOT_FREE  |<-----------------------------------+
+---------------+                                    |
        | aio_read_submit()                          | aio_release()
        v                                            | (terminal & waiters==0)
+---------------+                                    |
| IO_ALLOCATED  | (chỉ tồn tại nội bộ khi submit)    |
+---------------+                                    |
        | enqueue thành công                         |
        v                                            |
+---------------+                                    |
|   IO_QUEUED   |<--+ (thiếu desc: giữ nguyên vị trí)|
+---------------+   |                                |
        | try_submit thành công                      |
        v                                            |
+---------------+                                    |
|  IO_INFLIGHT  |                                    |
+---------------+                                    |
        | Ngắt IRQ: io_async_completed_locked()      |
        +-----------------------+                    |
        | status == 0           | status != 0        |
        v                       v                    |
+---------------+       +---------------+            |
|    IO_DONE    |       |   IO_ERROR    |------------+
+---------------+       +---------------+
        |                       ^
        +-----------------------+
```

### Các bất biến kỹ thuật bắt buộc khi Review mã nguồn:
1. **Địa chỉ bất biến:** Vùng nhớ staging buffer nằm cố định trong BSS, tuyệt đối không cấp phát qua con trỏ stack, user memory hoặc `kalloc` trong ngắt.
2. **Ngăn chặn rò rỉ:** Thiếu descriptor trong try-submit phải rollback sạch sẽ các descriptor trung gian, giữ nguyên thứ tự `enqueue_seq` trong hàng đợi.
3. **Độc quyền thu hồi:** Mỗi descriptor head chỉ có đúng một chủ sở hữu giải phóng (Async do IRQ, Stock do caller).
4. **An toàn kết quả:** Trạng thái `DONE`/`ERROR` không tự giải phóng; dữ liệu được bảo vệ an toàn cho đến khi caller chủ động gọi `aio_release()`.

---

## 5. Phân tích đồng bộ qua 3 kịch bản kiểm chứng then chốt

### 5.1 Kịch bản 1: Cạn kiệt Request Pool (T02)
- **Tình huống:** Cả 16 slot đều đang bận. Tiến trình gọi `aio_read_submit()`.
- **Hành vi chuẩn:** Hàm kiểm tra thấy pool hết slot rảnh, lập tức tăng `eagain_pool++`, nhả `io_lock` và trả về `-EAGAIN`. Con trỏ kết quả không bị ghi đè, hệ thống không rơi vào giấc ngủ và không panic. Khi có một request hoàn tất được release, slot tự do được thu hồi ngay lập tức để phục vụ lệnh submit kế tiếp.

### 5.2 Kịch bản 2: Ngắt hoàn tất xảy ra trước khi tiến trình vào chờ (T05 / Lost-Wakeup)
- **Tình huống:** Request được nạp vào đĩa và phần cứng xử lý cực nhanh, ngắt IRQ kích hoạt hoàn tất trước khi tiến trình kịp gọi `aio_wait()`.
- **Hành vi chuẩn (Fast-path):** Khi tiến trình gọi `aio_wait()`, hàm sở hữu `io_lock` và nhận thấy request đã ở trạng thái `IO_DONE`. Hàm lập tức trả về 0 mà không gọi `sleep_prepare()` hay chuyển sang trạng thái ngủ.
- **Trường hợp ngắt rơi vào khe hở đồng bộ (Gap Test - T06a):**  
  Nếu ngắt hoàn tất xảy ra ngay sau khi caller vừa chạy `sleep_prepare(req)` và vừa nhả `io_lock`: Lệnh `wakeup(req)` từ ngắt sẽ xóa kênh chờ `p->chan = 0`. Khi caller tiếp tục thực thi hàm `sleep()`, hệ điều hành nhận thấy kênh chờ rỗng nên trả về ngay lập tức. Khe hở mất tín hiệu đánh thức được triệt tiêu hoàn toàn.

### 5.3 Kịch bản 3: Tái sử dụng Head Descriptor trước khi Caller giải phóng Request (T08)
- **Tình huống:** Request A (đang dùng head descriptor 0) hoàn tất. Ngắt IRQ sao chép trạng thái vào `req_A->status`, thu hồi chuỗi descriptor về `free_desc`, và lập tức nạp request B vào chính head descriptor 0 vừa rảnh. Trong lúc này, caller của request A vẫn chưa gọi `aio_release()`.
- **Hành vi chuẩn:** Dữ liệu đọc của request A nằm trọn vẹn trong `req_A->data` (staging buffer riêng của slot A), hoàn toàn tách biệt với descriptor phần cứng. Caller của A vẫn gọi `aio_data()` và đọc chính xác dữ liệu của mình. Khi ngắt hoàn tất request B, hệ thống đối chiếu khớp `info[0].req == req_B` và cập nhật độc lập cho B mà không ảnh hưởng tới A.

---

## 6. Ma trận kiểm thử T01 – T13 ánh xạ vào Contract

| Ca kiểm thử | Quy tắc thiết kế kiểm chứng | Người phụ trách & Môi trường |
| :--- | :--- | :--- |
| **T01** — Đọc 1 block thực tế | **D2** (Buffer), **D3** (Blockno/Sector), **D6** (Miền khóa `io_lock`) | Hoàng — QEMU (CPUS=1/4) |
| **T02** — Cạn kiệt Request Pool | **D8** (Mã lỗi `-EAGAIN`), **D10** (Bất biến kế toán) | Hiếu — Kernel Selftest |
| **T03** — Xử lý Handle cũ (Stale Handle) | **D4** (Thế hệ Generation và từ chối `-ENOENT`) | Hiếu — Kernel Selftest |
| **T04** — Chống giải phóng sớm | **D5** & **D8** (Từ chối `-EBUSY` khi chưa terminal hoặc còn waiter) | Hiếu — Hook + QEMU |
| **T05** — Hoàn tất trước khi wait | **D9** (Đường dẫn Fast-path của `aio_wait`) | Hiếu — Process Context Test |
| **T06** — Chuỗi ngủ và đánh thức | **D9** (Chống lost-wakeup, ngủ thật và timer IRQ đánh thức) | Hiếu & Hoàng — Hook + QEMU |
| **T07** — Áp lực thiếu descriptor | **D7** (Cơ chế rollback an toàn và kích hoạt lại dispatcher) | Lợi — Mock Driver → QEMU |
| **T08** — Tái sử dụng head trước release | **D5** & **D7** (Tách biệt vòng đời slot và descriptor) | Hoàng — Hook + QEMU |
| **T09** — Đảo thứ tự hoàn tất ngắt | **D7** (Ánh xạ chuẩn xác used-ring và thẻ owner) | Hoàng — Mock Driver |
| **T10** — Submit không chặn | **D6** (Thao tác nạp lệnh không ngủ, ngắt xử lý độc lập) | Toàn nhóm — QEMU |
| **T11** — Cân bằng kế toán & xả hàng đợi | **D10** (Thu hồi toàn vẹn 16 slot pool và 8 descriptor) | Toàn nhóm — QEMU (10 chu kỳ) |
| **T12** — Kiểm thử hồi quy hệ thống | **D7** (Đảm bảo đường dẫn đồng bộ truyền thống không đổi) | Toàn nhóm — `usertests -q` |
| **T13** — Kiểm chứng điều phối FCFS | **D5** (Bảo toàn thứ tự `enqueue_seq` trong hàng đợi) | Lợi — Mock + QEMU |

---

## 7. Phân công Mã nguồn và Thứ tự Tích hợp (Merge Order)

### 7.1 Bảng phân công file theo Card kỹ thuật

| Tập tin | Người phụ trách | Vai trò kỹ thuật | Mã Card |
| :--- | :---: | :--- | :---: |
| `docs/week02/interface.md` | Hiếu | Tài liệu đặc tả kỹ thuật và giao ước kiến trúc | W2-G01 |
| `kernel/io_request.h` | Hiếu | Header trung tâm: cấu trúc dữ liệu, enum, prototype API | W2-G01 |
| `kernel/io_request.c` | Hiếu | Request pool, quản lý handle, poll/wait/release, thống kê | W2-I01 / I02 |
| `kernel/io_queue.c` | Lợi | Hàng đợi chờ, thuật toán FCFS, dispatcher | W2-L01 |
| `kernel/virtio_disk.c` | Hoàng | Thẻ owner, try-submit, ngắt hoàn tất, accessor `io_lock` | W2-H01 / H02 |
| `kernel/defs.h`, `Makefile`, `main.c` | Hiếu | Tích hợp hệ thống, khởi tạo `io_init()` sau disk init | W2-I01 |

### 7.2 Thứ tự Merge Pull Request đề xuất
Mỗi PR bắt buộc phải vượt qua biên dịch sạch (`make clean && make`) trước khi merge vào nhánh chính `main`:
1. **Bước 1:** Merge `W2-G01` (Header và đặc tả giao diện).
2. **Bước 2:** Merge `W2-H01` (Accessor `virtio_disk_io_lock()`, thẻ owner và try-submit).
3. **Bước 3:** Merge `W2-I01` (Request pool tĩnh và kiểm thử T02/T03/T04/T11).
4. **Bước 4:** Merge `W2-L01` (Hàng đợi điều phối FCFS).
5. **Bước 5:** Merge `W2-H02` (Xử lý ngắt hoàn tất IRQ và thu hồi descriptor).
6. **Bước 6:** Merge `W2-I02` (API `aio_wait`, `aio_poll` và harness test process context).
7. **Bước 7:** Thực hiện card tích hợp toàn diện `G02`.

---

## 8. Kế thừa và Thay thế Tài liệu Tuần 1

- [`docs/week01/decisions_report.md`](../week01/decisions_report.md) §3.2–§3.3 (về mô hình `aio_read_submit(dev, sector, kbuf, nbytes)` và caller-owned `kbuf`): **Chính thức bị thay thế** bởi quyết định D2 và D3 trong tài liệu này. Bản cũ được lưu trữ phục vụ việc tra cứu lịch sử thiết kế.
- [`docs/week01/async-design.md`](../week01/async-design.md): Được thống nhất với D2 (staging buffer của pool) và D6 (một khóa `io_lock` duy nhất); giao diện hàm chuẩn hóa theo Mục 3 của tài liệu này.
- [`docs/architecture.md`](../architecture.md) §2.6–§2.7: Đã cập nhật trỏ trực tiếp về bản Contract này.
- [`docs/week01/io-path.md`](../week01/io-path.md): Tiếp tục giữ nguyên giá trị tham khảo cho tầng điều khiển đĩa đồng bộ hiện hữu của xv6.

---

## 9. Các vấn đề kỹ thuật mở và Đối chiếu Tracker

### 9.1 Danh mục câu hỏi mở gửi Giảng viên hướng dẫn (Tổng hợp PTO-7)

| STT | Nội dung câu hỏi kỹ thuật | Thành viên gửi | Trạng thái | Ghi chú áp dụng cho tuần 2 |
| :---: | :--- | :---: | :---: | :--- |
| **Q1** | Cam kết tag/commit xv6 chính thức của học phần? | Hoàng | **PENDING** | Tạm dùng pin `f780d785`; cơ chế sleep mới của xv6 khác tài liệu cũ. |
| **Q2** | Phạm vi I/O async: Chỉ hỗ trợ READ và giữ WRITE đồng bộ có đạt yêu cầu? | Hiếu | **PENDING** | Phiên bản MVP tuần 2 tập trung hoàn thiện nhánh READ. |
| **Q3** | Giao diện bất đồng bộ: Kernel C API kèm demo có đạt chuẩn hay bắt buộc syscall người dùng? | Hiếu | **PENDING** | Chốt hoàn thiện kernel C API trong tuần 2 để đảm bảo độ tin cậy. |
| **Q4** | Thuật toán SCAN: Áp dụng SCAN truyền thống hay LOOK; quy tắc xử lý biên đổi chiều? | Lợi | **PENDING** | Tuần 2 tập trung điều phối tuần tự FCFS. |
| **Q5** | Phạm vi gom khối READ (Merge): Giới hạn số block tối đa và điều kiện cùng miền thứ tự? | Hiếu | **PENDING** | Tạm hoãn cơ chế merge trong tuần 2. |
| **Q6** | Tỷ trọng đánh giá giữa Tính năng (Functionality) / Kiểm thử (Testing) / Đo lường (Measurement)? | Hiếu | **PENDING** | Đảm bảo hoàn thiện đầy đủ cả 3 khía cạnh theo chuẩn kỹ thuật. |
| **Q7** | Có cần mở rộng độ dài virtqueue (`NUM`) để chứng minh mức độ song song `max_inflight > 2`? | Hoàng | **PENDING** | Tuần 2 ghi nhận số đo thực tế của phần cứng, không đưa ra cam kết ảo. |

### 9.2 Đối chiếu trạng thái các Task trên Jira (PTO Tracker)
Do môi trường làm việc không tích hợp quyền truy cập hệ thống Jira, thành viên **Lê Minh Lợi** chịu trách nhiệm mở tracker, đối chiếu các mã nhiệm vụ Tuần 1 với minh chứng cụ thể trong kho mã nguồn:
- **PTO-4, PTO-9, PTO-10, PTO-11:** Đối chiếu trực tiếp với các tài liệu đã nộp tại [`docs/week01/io-path.md`](../week01/io-path.md), [`docs/week01/decisions_report.md`](../week01/decisions_report.md), [`docs/week01/test-plan.md`](../week01/test-plan.md) và các PR tuần 1 đã merge vào base `e809500`.

---

## 10. Bằng chứng Thực thi và Lịch sử Thay đổi

### 10.1 Bằng chứng kiểm thử của bản Contract

| Thao tác kiểm tra | Kết quả | Hồ sơ bằng chứng lưu trữ |
| :--- | :---: | :--- |
| Kiểm tra cú pháp header và các ràng buộc kiểu biên dịch nghiêm ngặt (`-Wall -Werror`, 3 lệnh `_Static_assert`) | **PASS** | [`results/week02/g01-contract-2026-10-30/logs/header-check.log`](../../results/week02/g01-contract-2026-10-30/logs/header-check.log) |
| Biên dịch sạch toàn bộ hệ thống (`make clean && make -j$(nproc)`) | **PASS** | [`results/week02/g01-contract-2026-10-30/logs/build.log`](../../results/week02/g01-contract-2026-10-30/logs/build.log) |
| Kiểm tra chuẩn mã hóa văn bản (`make check-text`) | **PASS** | [`results/week02/g01-contract-2026-10-30/logs/check-text.log`](../../results/week02/g01-contract-2026-10-30/logs/check-text.log) |
| Chạy bộ smoke test hồi quy (`make test-fast`, 2 ca kiểm thử trên CPUS=3) | **PASS 2/2** | [`results/week02/g01-contract-2026-10-30/logs/test-fast.log`](../../results/week02/g01-contract-2026-10-30/logs/test-fast.log) |

### 10.2 Lịch sử sửa đổi tài liệu (Change Log)

| Ngày cập nhật | Phiên bản / Revision | Nội dung thay đổi chi tiết |
| :---: | :---: | :--- |
| 2026-10-27 | Kế hoạch tuần 2 | Đặt card W2-G01; phát hiện mâu thuẫn buffer/lock trong tài liệu thiết kế tuần 1. |
| 2026-10-30 | Commit `fa0746e` | Ban hành bản Contract đầu tiên: Chốt D1–D10, header `kernel/io_request.h`, 3 kịch bản kiểm thử trên giấy. |
| 2026-11-01 | Tinh chỉnh & Tái cấu trúc | Chuẩn hóa văn phong kỹ thuật, tối ưu hóa bố cục trực quan 10 mục, tinh gọn câu chữ nhưng bảo toàn 100% chi tiết đặc tả. |

---

> **Cam kết nghiệm thu:** Tài liệu này là căn cứ kỹ thuật ràng buộc trách nhiệm giữa các thành viên phụ trách các card W2-I01, W2-I02, W2-L01, W2-H01 và W2-H02. Mọi thay đổi về chữ ký hàm, cơ chế sở hữu bộ đệm hoặc quy tắc khóa đều phải được thông qua bằng cách cập nhật đồng bộ file này và header `kernel/io_request.h` trong cùng một Pull Request.
