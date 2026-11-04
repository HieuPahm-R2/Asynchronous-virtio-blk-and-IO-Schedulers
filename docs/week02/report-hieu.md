# Báo cáo kỹ thuật cá nhân — Tuần 2 (26/10 – 01/11/2026)

> **Người thực hiện:** Phạm Trung Hiếu (MSSV: 20233402)  

> **Trạng thái tổng quan:** Toàn bộ 3/3 card kỹ thuật đảm nhận đã hoàn thành đầy đủ mã nguồn kernel, bộ kiểm thử nội bộ (selftest harness), tài liệu kỹ thuật và đã vượt qua kiểm thử thực tế (PASS) trên nhánh làm việc. **Cả 3 card hiện đang ở trạng thái chờ rà soát chéo (peer review)** từ các thành viên trong nhóm (Hoàng review G01/I01/I02, Lợi review G01) trước khi chính thức đóng card. Các ca kiểm thử yêu cầu driver ngắt thực tế hoặc hàng đợi scheduler (T01, T07–T10, T12–T13) được ghi nhận minh bạch là **NOT RUN**

---

## 1. Tóm tắt

Trong tuần làm việc thứ 2, phần việc kỹ thuật của Hiếu tập trung vào việc thiết kế giao diện lõi, quy tắc đồng bộ và xây dựng tầng quản lý request bất đồng bộ (Request Layer) làm nền tảng cho toàn bộ hệ thống:

1. ** (Đặc tả giao diện & Quy tắc đồng bộ):**  
   Giải quyết dứt điểm xung đột kiến trúc tồn đọng từ Tuần 1 giữa hai tài liệu thiết kế. Nhóm thống nhất lựa chọn mô hình **staging buffer do Request Pool quản lý** (thay vì mô hình bộ đệm do caller sở hữu) và quy về **một miền khóa duy nhất** `io_lock` (đồng nhất với `disk.vdisk_lock`, loại trừ triệt để nguy cơ deadlock AB-BA khi dùng hai khóa riêng biệt). Hoàn thiện đặc tả API mức kernel, cấu trúc handle an toàn `struct io_handle { id, gen }`, phân định rạch ròi vòng đời của request và descriptor, chuẩn hóa chuỗi đồng bộ `wait/wakeup`, lập bảng ma trận ngữ cảnh–khóa–mã lỗi cho từng hàm, cùng 3 kịch bản phản biện thiết kế trên giấy.

2. *(Cơ chế Request Pool hữu hạn & Quản lý thế hệ Handle):**  
   Hiện thực hóa pool tĩnh gồm 16 slot nằm trọn trong phân vùng BSS, loại bỏ hoàn toàn việc cấp phát bộ nhớ động (`kalloc`) trên đường truyền I/O bất đồng bộ. Xây dựng cơ chế cấp phát không chặn (`try-alloc`), trả về lỗi an toàn khi pool đầy mà không làm panic kernel; cơ chế tra cứu và kiểm thực kép (chỉ số slot và thế hệ `gen`) trước mọi thao tác dereference nhằm loại trừ lỗi sử dụng handle cũ (stale handle / use-after-free); chỉ cho phép thu hồi slot khi request đã ở trạng thái kết thúc (`IO_DONE`/`IO_ERROR`) và không còn tiến trình nào đang chờ. Thiết kế bộ kiểm thử nội bộ chạy lúc khởi động kernel vượt qua các ca **T02, T03, T04, T11 (PASS)**, kèm thực nghiệm đối chứng nghịch (negative control) chứng minh test harness phát hiện lỗi tin cậy.

3. **(Giao diện Poll, Wait và Release an toàn):**  
   Hiện thực các hàm API chuẩn gồm `aio_poll`, `aio_wait`, `aio_data`, và callback `io_async_completed_locked` phục vụ tầng ngắt virtio-blk. Trong đó, `aio_wait` tuân thủ nghiêm ngặt mô hình đơn tiêu thụ (single consumer) và chuỗi đồng bộ của xv6 (`sleep_prepare -> release lock -> sleep -> acquire lock`), đảm bảo không giữ spinlock khi ngủ và không để lọt tín hiệu đánh thức (lost-wakeup). Triển khai khung kiểm thử trong ngữ cảnh tiến trình (process context) thông qua system call nội bộ `SYS_io_selftest`, vượt qua các ca **T05, T04, T06a (gap-completion) và T06b (ngủ thật và được timer IRQ đánh thức)**. Kiểm thử đối chứng nghịch bằng cách cố tình bỏ `wakeup(req)` xác nhận test harness bắt được lỗi treo do mất tín hiệu.


## 3. Chi tiết công việc đã thực hiện

### 3.1 W2-G01 — Thiết kế Contract interface, cơ chế sở hữu buffer và quy tắc khóa

#### Bối cảnh và bài toán kỹ thuật
Trong Tuần 1, hai tài liệu thiết kế xuất hiện điểm mâu thuẫn lớn: `async-design.md` đề xuất pool sở hữu buffer và dùng chung một khóa hệ thống; trong khi `decisions_report.md` lại quy định caller sở hữu con trỏ `kbuf` và chưa chốt được cơ chế khóa. Nếu các thành viên lập trình song song trên hai mô hình trái ngược này, hệ thống sẽ không thể tích hợp hoặc chắc chắn xảy ra deadlock khi đồng bộ. Card W2-G01 có nhiệm vụ giải quyết dứt điểm mâu thuẫn này trước khi viết code.

#### Bảng quyết định thiết kế then chốt (D1 – D10)

| Mã | Quyết định được chọn | Phương án bị loại trừ & Lý do kỹ thuật |
| :---: | :--- | :--- |
| **D1** | Phạm vi MVP kernel-level: Thao tác READ 1 block (`BSIZE=1024`), trên thiết bị gốc `ROOTDEV`, điều phối FCFS; các lệnh WRITE và hệ thống log giữ nguyên đường dẫn đồng bộ truyền thống. | Chưa mở rộng ra system call người dùng, WRITE bất đồng bộ hoặc gom cụm I/O (merge) để tập trung nguồn lực kiểm chứng luồng cốt lõi theo đúng yêu cầu tuần 2. |
| **D2** | **Request Pool sở hữu staging buffer** (`uchar data[BSIZE]` tích hợp trực tiếp trong từng slot tĩnh tại phân vùng BSS). | Loại bỏ mô hình caller tự sở hữu `kbuf` do vòng đời phức tạp, dễ gây rò rỉ bộ nhớ hoặc xung đột khi tiến trình bị hủy đột ngột trong lúc DMA đang chạy. |
| **D3** | Giao diện công khai sử dụng thống nhất đơn vị địa chỉ là **blockno**; việc chuyển đổi sang sector (`blockno * 2`) chỉ được thực hiện **duy nhất tại tầng driver**. | Loại trừ nguy cơ hai module cùng thực hiện phép nhân 2, dẫn đến việc tính sai địa chỉ sector trên đĩa (double multiply bug). |
| **D4** | Định danh request an toàn bằng cấu trúc `struct io_handle { id, gen }`; giá trị `gen` tự động tăng khi giải phóng slot và luôn khác 0; handle hết hạn trả về `-ENOENT`. | Loại trừ việc sử dụng chỉ số mảng trần (raw index), tránh tình trạng handle cũ vô tình thao tác nhầm vào slot đã được tái cấp phát (ABA problem / stale handle). |
| **D5** | Phân định rạch ròi hai vòng đời độc lập: Request (`FREE → ALLOCATED → QUEUED → INFLIGHT → DONE/ERROR → FREE`) và Descriptor phần cứng (`FREE → RESERVED → PUBLISHED → USED → RECLAIMED → FREE`). | Không gộp chung request, descriptor phần cứng và bộ đệm thành một đối tượng duy nhất nhằm đảm bảo tính độc lập giữa logic điều phối và tầng driver. |
| **D6** | **Quy về một miền khóa duy nhất** `io_lock` (đồng nhất với `disk.vdisk_lock` thông qua hàm `virtio_disk_io_lock()`); cấm acquire lồng nhau; tuyệt đối không ngủ khi đang giữ spinlock. | Loại bỏ thiết kế dùng hai khóa riêng biệt (`ioq.lock` và `vdisk_lock`) vì dễ gây deadlock AB-BA khi luồng enqueue cần lấy `ioq → vdisk` còn luồng ngắt lại cần `vdisk → ioq`. |
| **D7** | Mỗi descriptor head gắn cờ sở hữu rõ ràng: `STOCK` hoặc `ASYNC`. Luồng **async do ngắt IRQ giải phóng**, luồng **stock do caller giải phóng**; cơ chế dispatch được kích hoạt tại 3 điểm (submit, ngắt IRQ, và sau khi stock thu hồi head). | Không dùng chung hàm giải phóng nếu không kiểm tra quyền sở hữu, ngăn ngừa lỗi giải phóng hai lần (double-free) đối với các request đồng bộ truyền thống. |
| **D8** | Chuẩn hóa bảng mã lỗi kernel: `-EINVAL`, `-ENODEV`, `-ERANGE`, `-ENOENT`, `-EAGAIN`, `-EIO`, `-EBUSY`. Khi pool đầy, trả về mã lỗi `-EAGAIN`, không gây block và không làm panic kernel. | Tránh việc hệ điều hành rơi vào trạng thái chờ vô hạn hoặc bị crash ngoài ý muốn khi tải I/O tăng đột biến. |
| **D9** | Kênh chờ (wait channel) sử dụng trực tiếp con trỏ của `struct io_request`; giới hạn số lượng waiter `∈ {0, 1}` (đơn tiêu thụ); ngắt IRQ phải cập nhật trạng thái kết thúc **trước** khi gọi `wakeup`; bên chờ phải gọi `sleep_prepare` khi còn đang giữ khóa. | Tránh việc giải phóng slot trước khi caller kịp đọc kết quả; loại trừ khe hở mất tín hiệu đánh thức (lost-wakeup) khi ngắt xảy ra ngay trước lệnh ngủ. |
| **D10** | Thiết lập bộ đếm thống kê và các bất biến kế toán nghiêm ngặt (`submitted = queued + inflight + done + error`; số slot rảnh và descriptor tự do phải hoàn trả đầy đủ sau chu kỳ xả hàng đợi). | Không chấp nhận tiêu chí kiểm thử mơ hồ "chạy không panic là đạt", mà buộc mọi tài nguyên phải được cân bằng kế toán tuyệt đối. |

#### Kết quả bàn giao (Deliverables)
- [`docs/week02/interface.md`](interface.md): Tài liệu đặc tả kỹ thuật chi tiết gồm bảng ma trận ngữ cảnh–khóa–lỗi của từng hàm, biểu đồ chuyển trạng thái, 3 kịch bản phản biện thiết kế (xử lý cạn kiệt pool; ngắt hoàn tất trước khi tiến trình vào chờ; tái sử dụng head trước khi giải phóng), ánh xạ bộ kiểm thử T01–T13, cùng danh mục câu hỏi kỹ thuật gửi giảng viên.
- [`kernel/io_request.h`](../../kernel/io_request.h): Header trung tâm định nghĩa các kiểu dữ liệu, hằng số trạng thái, `struct io_request` (được tối ưu ở kích thước 1080 B), `struct io_handle`, các prototype API cùng các chỉ thị kiểm tra kiểu tại thời điểm biên dịch (`_Static_assert`).
- Cập nhật đồng bộ các tài liệu liên quan: [`docs/week01/kickoff.md`](../week01/kickoff.md), [`docs/architecture.md`](../architecture.md) (§2.6–§2.7), gắn banner thông báo thay thế tại [`docs/week01/async-design.md`](../week01/async-design.md) và [`docs/week01/decisions_report.md`](../week01/decisions_report.md).
- Hồ sơ kiểm chứng thực nghiệm: [`results/week02/g01-contract-2026-10-30/summary.md`](../../results/week02/g01-contract-2026-10-30/summary.md) xác nhận header biên dịch nghiêm ngặt với các cờ `-Wall -Werror`, vượt qua 3 lệnh `_Static_assert`, build production sạch và bộ kiểm thử `make test-fast` đạt 2/2 PASS.
---

### 3.2 W2-I01 — Hiện thực Request Pool tĩnh và Handle có Generation

#### Nội dung kỹ thuật đã triển khai
- **Cấu trúc Pool tĩnh trong phân vùng BSS:** Khởi tạo mảng `io_pool[IO_NREQ=16]` trong BSS. Giải pháp này đảm bảo địa chỉ bộ nhớ của header request, trạng thái và staging buffer luôn cố định trong suốt vòng đời của kernel, loại bỏ hoàn toàn chi phí cấp phát động (`kalloc`) và nguy cơ phân mảnh bộ nhớ trên luồng xử lý I/O.
- **Hệ thống hàm quản lý vòng đời Request:**
  - `io_init()`: Khởi tạo pool ngay trong hàm `main()` sau khi driver đĩa `virtio_disk_init()` đã sẵn sàng.
  - `io_alloc_slot_locked()`: Cấp phát tuần tự slot đang ở trạng thái `IO_SLOT_FREE`. Khi pool đầy, hàm trả về con trỏ `NULL` và tăng biến đếm `eagain_pool++` một cách an toàn mà không làm treo hay panic hệ thống.
  - `io_lookup_handle_locked()`: Cơ chế tra cứu handle an toàn 3 lớp. Kiểm tra dải chỉ số slot (`0 <= id < IO_NREQ`), kiểm tra slot có đang hoạt động hay không, và so khớp thế hệ (`req->gen == handle.gen`) trước khi cho phép dereference con trỏ.
  - `io_release_locked()`: Chỉ chấp nhận giải phóng các slot đã ở trạng thái kết thúc (`IO_DONE` hoặc `IO_ERROR`) và không còn tiến trình nào đang chờ (`waiters == 0`). Khi giải phóng, hàm tự động tăng thế hệ `gen++` (tránh giá trị 0) và đưa slot về trạng thái `IO_SLOT_FREE`.
  - `aio_release()`: Giao diện bọc ngoài, tự động quản lý việc chiếm giữ và giải phóng `io_lock`.
  - `io_get_stats()`: Truy vấn số liệu thống kê (`free_req`, `queued`, `inflight`). Số lượng slot rảnh và đang bay được suy luận trực tiếp từ trạng thái thực tế của các phần tử trong pool nhằm loại trừ hiện tượng trôi lệch số liệu đếm (counter drift).
- **Phân đoạn tích hợp sớm với H01:** Bổ sung hàm `virtio_disk_io_lock()` trả về địa chỉ con trỏ `&disk.vdisk_lock` của driver đĩa, bảo đảm toàn bộ hệ thống tuân thủ nghiêm ngặt nguyên tắc một miền khóa duy nhất (D6).
- **Bộ kiểm thử nội bộ tự động (Kernel Selftest):** Xây dựng các ca kiểm thử chuyên sâu chạy ngay khi kernel khởi động, được kích hoạt thông qua cờ biên dịch `-DIO_SELFTEST` và mục tiêu `make test-io`:
  - **T02 (Cạn kiệt Pool):** Cấp phát hết 16 slot, kiểm tra việc từ chối slot thứ 17 an toàn, giải phóng toàn bộ và kiểm tra pool phục hồi nguyên vẹn 16 slot tự do.
  - **T03 (Chống Handle cũ / Stale Handle):** Giải phóng slot rồi tái cấp phát, kiểm tra việc từ chối handle cũ và đảm bảo dữ liệu mới không bị rò rỉ cho handle cũ.
  - **T04 (Chống giải phóng Slot đang hoạt động):** Ngăn chặn việc release slot khi đang ở các trạng thái sống (`ALLOCATED`, `QUEUED`, `INFLIGHT`) hoặc khi còn waiter.
  - **T11 (Cân bằng kế toán & Tính ổn định của Buffer):** Thực hiện 10 chu kỳ cấp phát và giải phóng liên tục, xác nhận không rò rỉ tài nguyên và địa chỉ staging buffer hoàn toàn bất biến.

#### Bằng chứng thực nghiệm
Toàn bộ log được lưu trữ tại [`results/week02/i01-pool-2026-10-30/summary.md`](../../results/week02/i01-pool-2026-10-30/summary.md):
- Kiểm tra tính đúng đắn của header compile `-Wall -Werror`: **PASS**.
- Biên dịch bản production sạch và chạy bộ smoke test `make test-fast`: **PASS (2/2)**.
- Chạy kiểm thử nội bộ qua `make test-io`: Toàn bộ các ca T02, T03, T04, T11 đều **PASS**.
- **Thực nghiệm đối chứng nghịch (Negative Control):** Cố tình vô hiệu hóa điều kiện kiểm tra thế hệ `gen` trong `io_lookup_handle_locked()`. Kết quả cho thấy ca kiểm thử T03 lập tức báo **FAIL** (bắt đúng 4 assertion) và lệnh make dừng với mã lỗi khác 0. Khi khôi phục lại mã nguồn chuẩn, toàn bộ bài test **PASS** trở lại.

**Tiêu chí nghiệm thu card:** ✅ Cấp phát chuẩn xác 16 slot, từ chối slot 17 an toàn và duy trì đúng biến đếm thống kê; ✅ Handle cũ bị từ chối truy cập tuyệt đối sau khi slot được tái sử dụng; ✅ Ngăn chặn việc giải phóng slot đang xử lý hoặc còn tiến trình chờ; ✅ Không rò rỉ slot sau 10 vòng lặp kế toán.

---

### 3.3 W2-I02 — Hiện thực cơ chế Poll, Wait và Release an toàn tối thiểu

#### Nội dung kỹ thuật đã triển khai
- **API `aio_poll()`:** Hàm kiểm tra trạng thái không chặn (non-blocking). Trả về 1 khi request hoàn thành (`DONE`), 0 khi đang xử lý (`INFLIGHT`/`QUEUED`), `-EIO` khi gặp lỗi phần cứng, và `-ENOENT` nếu handle không hợp lệ hoặc đã hết hạn. Hàm tuyệt đối không đưa tiến trình vào giấc ngủ và không tự ý giải phóng slot.
- **API `aio_wait()`:** Hàm chờ đồng bộ an toàn, được thiết kế với các ràng buộc kỹ thuật nghiêm ngặt:
  - Chỉ cho phép gọi từ ngữ cảnh tiến trình (process context); cấm gọi từ ngữ cảnh ngắt hoặc scheduler (kiểm tra `myproc() == 0` lập tức trả về `-EINVAL`).
  - Áp dụng mô hình đơn tiêu thụ (single consumer): biến đếm `waiters` chỉ nhận giá trị 0 hoặc 1.
  - **Đường xử lý nhanh (Fast-path):** Nếu request đã hoàn tất trước thời điểm gọi wait, hàm lập tức trả về kết quả thành công mà không cần chuyển trạng thái tiến trình sang ngủ.
  - **Chuỗi thao tác tránh Lost-wakeup:** Khi request chưa hoàn tất, tiến trình gọi `sleep_prepare(req)` ngay khi còn đang giữ `io_lock` để đăng ký vào kênh chờ, sau đó giải phóng `io_lock`, gọi `sleep()` để nhường CPU, và tái sở hữu `io_lock` khi được đánh thức để kiểm tra lại trạng thái. Thiết kế này loại bỏ hoàn toàn khe hở chạy đua (race condition) và **tuyệt đối không ôm spinlock khi ngủ**.
- **API `aio_data()`:** Trả về con trỏ vùng nhớ staging buffer tương ứng với request đã hoàn thành.
- **Callback `io_async_completed_locked()`:** Hàm chuẩn hóa để tầng ngắt thiết bị (`virtio_disk_intr` do Hoàng hiện thực tại H02) gọi khi phần cứng hoàn tất lệnh đọc. Hàm thực hiện chuyển trạng thái request sang `IO_DONE` hoặc `IO_ERROR`, ghi nhận mã trạng thái và timestamp `t_complete`, cập nhật các biến đếm kế toán và phát tín hiệu `wakeup(req)`.
- **Hạ tầng kiểm thử trong ngữ cảnh tiến trình (Process-Context Test Harness):**  
  Do `aio_wait` bắt buộc phải chạy trong ngữ cảnh tiến trình có cấu trúc `struct proc` hợp lệ, bài test không thể thực thi trong pha khởi động kernel đơn thuần. Hệ thống đã bổ sung:
  - System call nội bộ `SYS_io_selftest` (chỉ mở khi có cờ `-DIO_SELFTEST`, ở bản production syscall này lập tức trả về -1).
  - Chương trình `user/init.c` tự động kích hoạt `SYS_io_selftest` ngay trước khi mở shell người dùng.
  - Kịch bản `scripts/io-selftest.sh` khởi động QEMU nạp trực tiếp file nhị phân kernel (không gọi qua make nhằm tránh việc relink làm mất cờ `-DIO_SELFTEST`).
  - Danh mục các ca kiểm thử đã vượt qua:
    - **T05 (Complete-before-wait):** Kiểm tra đường dẫn fast-path cho cả trường hợp DONE, ERROR và stale handle; xác nhận wait trả về ngay lập tức.
    - **T04 (Process context):** Cố tình gọi release khi request đang ở trạng thái INFLIGHT; hệ thống từ chối an toàn với mã lỗi `-EBUSY`.
    - **T06a (Lost-wakeup gap test):** Giả lập trường hợp completion xảy ra chính xác tại khe hở giữa `sleep_prepare` và `sleep`; xác nhận tiến trình không bao giờ bị mất tín hiệu đánh thức.
    - **T06b (Sleep & Timer IRQ wakeup):** Waiter thực sự đi ngủ trên kênh chờ, sau đó được ngắt đồng hồ định kỳ (`clockintr`) giả lập hoàn tất request và phát tín hiệu đánh thức sau 2 tick (nhật ký ghi nhận tiến trình đã ngủ thực tế `slept >= 3 tick(s)`).
    - **T03 & T11:** Kiểm tra mở rộng các dạng handle lỗi biên (`id` âm, vượt ngưỡng, `gen` bằng 0) và xác nhận xả sạch toàn bộ tài nguyên sau bài test.

#### Bằng chứng thực nghiệm
Toàn bộ log được lưu trữ tại [`results/week02/i02-poll-wait-2026-10-30/summary.md`](../../results/week02/i02-poll-wait-2026-10-30/summary.md):
- Biên dịch header ở cả 2 chế độ (production và test): **PASS**.
- Biên dịch production và chạy `make test-fast`: **PASS (2/2)**.
- Chạy bộ kiểm thử tự động `make test-io`: Toàn bộ các ca T02, T03, T04, T05, T06a, T06b, T11 đều **PASS**.
- **Negative Control:** Cố tình loại bỏ lời gọi `wakeup(req)` trong hàm completion. Kết quả ca kiểm thử T06a bị treo hoàn toàn, không thể in ra dòng xác nhận PASS và tiến trình QEMU bị cơ chế watchdog cưỡng chế dừng sau khoảng thời gian timeout, khiến lệnh make kết thúc với lỗi. Khi phục hồi lại lệnh `wakeup`, bài test lập tức **PASS** trở lại.

**Tiêu chí nghiệm thu card:** ✅ `aio_wait` sau khi có kết quả trả về tức thời; `aio_wait` trước khi hoàn tất được đánh thức chuẩn xác, không bị treo hệ thống; ✅ Từ chối an toàn việc giải phóng request đang xử lý (`-EBUSY`); ✅ Đảm bảo tuyệt đối không giữ spinlock khi ngủ và cấm wait trong ngắt; ✅ Xử lý an toàn các dạng handle lỗi mà không gây crash kernel;.


## 5. Tổng hợp kết quả kiểm thử và bằng chứng thực nghiệm

### 5.1 Các ca kiểm thử đã đạt (PASS)

Toàn bộ nhật ký kiểm thử chi tiết được lưu trữ có cấu trúc trong thư mục `results/week02/`:

| Nhóm kiểm thử | Nội dung ca kiểm thử chi tiết | Môi trường thực nghiệm | Bằng chứng lưu vết |
| :--- | :--- | :--- | :--- |
| **Contract (W2-G01)** | Biên dịch header nghiêm ngặt (`-Wall -Werror`, 3 lệnh `_Static_assert`), build production sạch hoàn toàn, chạy smoke test `make test-fast` đạt 2/2 PASS. | WSL2 Ubuntu-24.04, riscv64-linux-gnu-gcc 13.3.0, QEMU 8.2.2 | [Hồ sơ nghiệm thu G01](../../results/week02/g01-contract-2026-10-30/summary.md) |
| **Pool & Handle (W2-I01)** | **T02:** Cạn kiệt pool; **T03:** Phát hiện stale-handle; **T04:** Chống giải phóng slot đang bận; **T11:** Cân bằng kế toán qua 10 chu kỳ cấp phát và tính bất biến của địa chỉ bộ đệm. | Chạy kernel selftest thông qua lệnh `make test-io` | [Hồ sơ nghiệm thu I01](../../results/week02/i01-pool-2026-10-30/summary.md) |
| **Poll & Wait (W2-I02)** | **T05:** Complete-before-wait (nhánh DONE, ERROR và stale handle); **T04:** Chống giải phóng request INFLIGHT trong process context; **T06a:** Chống lost-wakeup tại khe hở chuẩn bị ngủ; **T06b:** Ngủ thật và được Timer IRQ đánh thức; **T03:** Handle lỗi biên; **T11:** Xả sạch hàng đợi. | Ngữ cảnh tiến trình qua system call `SYS_io_selftest` trên `make test-io` | [Hồ sơ nghiệm thu I02](../../results/week02/i02-poll-wait-2026-10-30/summary.md) |
| **Đối chứng nghịch (Negative Control)** | **I01:** Tắt kiểm tra generation ⇒ T03 lập tức báo FAIL; **I02:** Bỏ lệnh `wakeup(req)` ⇒ T06a bị treo và watchdog hủy QEMU; sau khi khôi phục mã nguồn ⇒ cả hai đều PASS trở lại. | Tương tự các môi trường trên | Nhật ký `negative-control-*` trong 2 thư mục bằng chứng I01 và I02 |
| **Hồi quy hệ thống (Regression)** | Lệnh `make test-fast` đạt **PASS 2/2** trên bản build production ở cả hai mốc I01 và I02 mà không bị ảnh hưởng bởi mã kiểm thử. | QEMU đa xử lý ảo (CPUS=1 và CPUS=3) | File `logs/test-fast.log` trong các thư mục evidence |

### 5.2 Các ca kiểm thử chưa chạy (NOT RUN)

Nhóm duy trì tính kỷ luật kỹ thuật, ghi nhận minh bạch trạng thái **NOT RUN** và tuyệt đối không làm tròn thành PASS đối với các bài kiểm tra đòi hỏi sự tích hợp của các module khác:

| Ca kiểm thử | Lý do kỹ thuật chưa thể thực thi | Kế hoạch triển khai |
| :--- | :--- | :---: |
| **T01** — Đọc 1 block dữ liệu thực tế từ thiết bị | Yêu cầu hàm nạp request vào phần cứng (`try-submit` thuộc H01) và ngắt xử lý hoàn tất (`completion IRQ` thuộc H02). | Mốc G02 |
| **T07** (Áp lực descriptor), **T08** (Tái sử dụng head), **T09** (Đảo thứ tự hoàn tất), **T10** (Submit không chờ) | Yêu cầu tầng điều khiển driver thực tế hoặc bộ giả lập driver chuyên biệt từ nhóm phần cứng (H01/H02). | Mốc G02 |
| **T12** — Kiểm thử hồi quy toàn diện hệ thống (`usertests -q`, `grind 60s` trên CPUS=1/4) | Chưa thực hiện trong phạm vi hẹp của từng card riêng lẻ; thuộc trách nhiệm kiểm thử nghiệm thu toàn hệ thống. | Mốc G02 |
| **T13** — Kiểm chứng thuật toán điều phối FCFS | Yêu cầu hàng đợi I/O scheduler do Lợi hiện thực tại card L01. | Mốc L02 + G02 |
| **T06 mở rộng** (Đa waiter, xử lý hủy tiến trình kill/exit/cancel trên CPUS=4) | Nằm ngoài phạm vi của phiên bản MVP tuần 2; được hoạch định giải quyết toàn diện trong kỳ tiếp theo (K04). | Kỳ tiếp theo |
| **`aio_read_submit` đầu-cuối** | Đòi hỏi sự kết nối hoàn chỉnh giữa hàng đợi L01 và tầng driver H01/G02. | Mốc G02 |
| **Đo lường baseline trên máy cá nhân của Hiếu** | Chưa thu thập vào hồ sơ kỹ thuật chung; cấu hình máy cá nhân chạy Ubuntu 26.04 sẽ được đo đồng bộ. | Mốc G02 |


## 6. Trạng thái, Điểm nghẽn kỹ thuật và Công việc tồn đọng

| Nội dung công việc | Người phụ trách | Trạng thái hiện tại | Ghi chú kỹ thuật |
| :--- | :---: | :---: | :--- |
| Rà soát chéo W2-G01 (Contract / Buffer / Lock) | Hoàng + Lợi | ⬜ PENDING | Review trực tiếp trên commit của Pull Request; bắt buộc hoàn thành trước khi merge module. |
| Rà soát chéo W2-I01 (Pool / Generation / Lock slice) | Hoàng | ⬜ PENDING | Đặc biệt chú trọng rà soát hàm chia sẻ `virtio_disk_io_lock()` dùng chung cho H01. |
| Rà soát chéo W2-I02 (Wait / Wakeup / Harness test-only) | Hoàng | ⬜ PENDING | Đánh giá mức độ ảnh hưởng đến mã nguồn production (đã có kết quả build sạch và test-fast làm cơ sở). |

| Rà soát các mục PTO trên Jira (PTO-4/7/9/10/11) | Lợi | ⬜ PENDING | Cập nhật minh chứng trực tiếp từ tài liệu kỹ thuật đã ghi nhận tại `interface.md` §9.2. |
| Giải đáp 7 câu hỏi kỹ thuật gửi GV (PTO-7) | Toàn nhóm | ⬜ PENDING | Các vấn đề về tag xv6, API/syscall, phạm vi READ-only, thuật toán scheduler, cơ chế merge block và rubric chấm điểm. |
| Tích hợp hệ thống MVP và chạy test ngắt thật (G02) | Hoàng chủ trì | ⏳ Chờ H01/H02/L01 | Hiếu sẵn sàng tham gia rà soát quyền sở hữu buffer/API và chạy lại ma trận test khi có nhánh tích hợp. |
| Đo đạc baseline hiệu năng riêng trên máy Hiếu | Hiếu | ⬜ PENDING | Thực hiện trong mốc G02 trên cùng base commit để đối chiếu chéo. |

**Phân tích điểm nghẽn kỹ thuật (Blockers):**  
Hiện tại, hệ thống chưa thể kiểm thử luồng submit bất đồng bộ đầu-cuối (`aio_read_submit`) do tầng nạp lệnh và xử lý ngắt (`try-submit` / `IRQ handler` thuộc H01/H02) cùng hàng đợi scheduler (L01) đang được các thành viên khác hoàn thiện độc lập. Để khắc phục điểm nghẽn này mà không phá vỡ tính bao gói, Hiếu đã chủ động cung cấp sẵn callback `io_async_completed_locked` cùng tài liệu đặc tả contract hoàn chỉnh để H02/L01 dễ dàng tích hợp, kiên quyết không tự ý thay đổi mô hình sở hữu buffer để đi tắt.


### C. Hướng dẫn lệnh tái lập và kiểm chứng thực nghiệm

```bash
# 1. Biên dịch và kiểm tra tính toàn vẹn của bản build production
make clean && make -j"$(nproc)"
make test-fast

# 2. Thực thi toàn bộ bộ kiểm thử nội bộ tự động (Kernel Selftest & Process Context Selftest)
make test-io

# 3. Phục hồi môi trường kernel về trạng thái production sạch
make clean && make

# 4. Kiểm tra chuẩn mã hóa và tính toàn vẹn của toàn bộ tài liệu trong kho lưu trữ
make check-text
```

### D. Ghi chú kỹ thuật và Các giải pháp xử lý rủi ro

- **Ngăn chặn lỗi relink thiếu cờ biên dịch:** Công cụ `make qemu` mặc định của xv6 không theo dõi sự thay đổi của biến `CFLAGS`, do đó có thể dẫn tới việc vô tình liên kết lại các file object của bản production khi đang cần cờ `-DIO_SELFTEST` (từng gây lỗi thiếu biểu tượng `io_test_timer_tick`). Giải pháp được áp dụng là xây dựng kịch bản `scripts/io-selftest.sh` để nạp trực tiếp file nhị phân kernel vào QEMU mà không triệu gọi lại make.
- **Bảo toàn tính an toàn tuyệt đối cho bản Production:** Toàn bộ các điểm can thiệp kiểm thử đều được bao bọc chặt chẽ sau chỉ thị tiền xử lý `#ifdef IO_SELFTEST`. Khi biên dịch ở chế độ production thông thường, system call `SYS_io_selftest` trả về mã lỗi `-1`, các hàm `init` và bộ xử lý ngắt đồng hồ `clockintr` hoàn toàn không gọi mã test. Tính toàn vẹn này đã được kiểm chứng thông qua bài kiểm tra `make test-fast`.
- **Lưu ý khi cập nhật phiên bản gốc của xv6 (Pin xv6):** Do một số đoạn mã kiểm thử được đưa vào các file nguồn cốt lõi (`kernel/syscall.{h,c}`, `kernel/trap.c`, `user/usys.pl`, `user/init.c`), nhóm cần chú ý áp dụng lại (re-apply) các đoạn mã này sau mỗi lần thực thi kịch bản cập nhật `scripts/update-xv6.sh`.
- **Môi trường làm việc đa luồng:** Trong quá trình thực hiện, cây làm việc có ghi nhận một số thay đổi tài liệu độc lập từ các thành viên khác (`docs/architecture.md`, `docs/baseline.md`, `docs/upstream.md`); các thay đổi này được tách biệt hoàn toàn khỏi các commit chuyên môn của Hiếu.

