# BÁO CÁO PHÂN TÍCH VÀ ĐỀ XUẤT THIẾT KẾ ASYNCHRONOUS I/O TRÊN XV6

> **CẬP NHẬT 2026-10-30 (W2-G01):** mô hình **caller-owned `kbuf`** và chữ ký
> `aio_read_submit(dev, sector, kbuf, nbytes)` ở §3.2–§3.3 (và câu hỏi §5.3)
> **đã được thay thế** bởi quyết định D2/D3 trong
> [`docs/week02/interface.md`](../week02/interface.md): pool sở hữu staging
> buffer cố định, public API dùng `blockno` + `struct io_handle`. Tài liệu này
> giữ nguyên làm phân tích thiết kế lịch sử; **không** dùng để code/ghép module.

## 1. Mục tiêu và phạm vi

Mục tiêu của đề xuất là bổ sung cơ chế **đọc đĩa bất đồng bộ (asynchronous read)** cho xv6. Thay vì chờ mỗi yêu cầu đọc hoàn tất mới thực hiện công việc tiếp theo, hệ thống có thể đưa yêu cầu vào hàng đợi, gửi nhiều yêu cầu xuống thiết bị khi còn tài nguyên và thông báo cho bên gọi khi có kết quả.

Để hạn chế rủi ro ảnh hưởng tới tính đúng đắn của hệ thống tệp, **giai đoạn đầu chỉ áp dụng lập lịch và merge cho lệnh đọc**. Đường ghi cùng cơ chế logging hiện tại vẫn được giữ đồng bộ. Việc mở rộng sang ghi bất đồng bộ hoặc syscall dành cho chương trình người dùng chưa được chốt.

## 2. Phân tích cơ chế I/O hiện tại và các ràng buộc

### 2.1. Buffer cache: quản lý dữ liệu đọc/ghi

Trong xv6, buffer cache giữ các block đĩa trong bộ nhớ, giúp tái sử dụng dữ liệu và phối hợp với cơ chế ghi log. Các hàm quan trọng gồm `bread()`, `brelse()`, `bpin()` và `bunpin()`.

- `bread()` trả về buffer đã được khóa để caller có thể thao tác an toàn; `brelse()` mở khóa và giảm số tham chiếu sau khi sử dụng.
- `refcnt > 0` bảo vệ buffer khỏi bị tái sử dụng làm block khác. Logging dùng `bpin()`/`bunpin()` để giữ buffer cần thiết trong transaction.
- Nếu tất cả buffer đều đang được tham chiếu, `bget()` có thể dừng hệ thống bằng lỗi `panic("bget: no buffers")`.

Theo cấu hình, mỗi block có kích thước `BSIZE = 1024` byte và buffer cache có `NBUF = 30` phần tử. Nếu giữ nhiều buffer cache cho các lệnh đọc async, chúng có thể tranh tài nguyên với logging và hoạt động đọc/ghi thông thường.

**Hướng thiết kế:** Không giữ các `struct buf` thuộc buffer cache làm vùng DMA lâu dài cho request async. Thay vào đó, dùng **kernel buffer riêng** để thực hiện I/O bất đồng bộ. Cách làm này giảm tranh chấp buffer, nhưng phát sinh vấn đề nhất quán dữ liệu vì đường đọc async không tự động cập nhật buffer cache. Do đó, trong giai đoạn đầu, chỉ nên sử dụng trên vùng dữ liệu thử nghiệm được kiểm soát, **không coi đây là đường đọc thay thế trực tiếp cho hệ thống tệp** nếu chưa giải quyết cache coherence.

### 2.2. Vì sao chưa triển khai async write?

Đường ghi hiện tại gắn với cơ chế log của hệ thống tệp. Trình tự rút gọn như sau:

```text
writei() → log_write() → end_op() → commit()
                                      |
                                      +→ write_log()      (ghi dữ liệu vào log)
                                      +→ write_head()     (ghi header để commit)
                                      +→ install_trans()  (chép dữ liệu về vị trí thật)
                                      +→ write_head()     (xóa thông tin transaction)
```

Việc ghi các block log, header và block đích phải tuân theo thứ tự mà cơ chế khôi phục của xv6 giả định. Tự ý đổi thứ tự hoặc cho scheduler xử lý lệnh ghi mà không có rào chắn (write fence) có thể khiến hệ thống tệp không nhất quán khi có lỗi giữa chừng.

**Quyết định đề xuất cho bản đầu:** Giữ nguyên đường ghi đồng bộ và thứ tự xử lý log. Scheduler async chỉ quản lý các lệnh **READ**. Nếu mở rộng sang async write, cần thiết kế riêng cơ chế bảo toàn thứ tự, write fence và kiểm thử khôi phục sau sự cố.

### 2.3. Giới hạn thiết bị VirtIO và xử lý completion

Theo mã nguồn, hàng đợi VirtIO có `NUM = 8` descriptor. Với cấu trúc thông thường gồm **3 descriptor cho mỗi lệnh**, thiết bị có thể có tối đa **2 yêu cầu đồng thời đang thực thi** theo cách tổ chức này.

Một trường hợp quan trọng khác là **I/O hoàn tất trước khi caller bắt đầu đợi** (*completion-before-wait*). Để không bỏ lỡ tín hiệu wake-up:

1. Waiter kiểm tra trạng thái request khi đang giữ lock thích hợp.
2. Nếu chưa hoàn tất, waiter đăng ký kênh chờ bằng `sleep_prepare()` **trước khi nhả lock**, rồi mới `sleep()`.
3. Interrupt cập nhật trạng thái thành `DONE` hoặc `ERROR` **trước khi** gọi `wakeup()`.
4. Khi được đánh thức, waiter kiểm tra lại trạng thái trong vòng lặp.

Nếu nhả lock rồi mới đăng ký chờ, interrupt có thể hoàn tất và gửi `wakeup()` trước lúc waiter đăng ký; kết quả là waiter bị sleep vô thời hạn. Đây là lỗi *lost wakeup* cần được kiểm thử riêng. Interrupt chỉ cập nhật trạng thái và thông báo hoàn tất.

## 3. Thiết kế đọc bất đồng bộ đề xuất

### 3.1. Luồng xử lý tổng quát

```text
Caller trong kernel
    |
    v
 aio_read_submit()
    |
    v
 Hàng đợi READ (QUEUED)
    |
    v
 Scheduler chọn request
    |
    v
 VirtIO driver (INFLIGHT) ──> Interrupt báo DONE / ERROR
    |                                  |
    +----------------------------------+
                                       v
                               aio_poll() / aio_wait()
                                       |
                                       v
                                  aio_release()
```

`submit()` trả về một mã định danh (*handle*) sau khi nhận request, **không cần chờ thiết bị đọc xong**. Phần mềm có thể tiếp tục xử lý công việc khác, kiểm tra tình trạng bằng `poll()` hoặc chờ kết quả bằng `wait()`.

### 3.2. API dự kiến

| Hàm | Chức năng | Kết quả chính |
| --- | --- | --- |
| `aio_read_submit(dev, sector, kbuf, nbytes)` | Kiểm tra tham số, tạo request và đưa vào queue. `kbuf` là buffer hợp lệ trong kernel. | `handle > 0` hoặc mã lỗi |
| `aio_poll(handle)` | Kiểm tra nhanh, không chờ và không sao chép dữ liệu. | `0`: chưa xong; `1`: xong; số âm: lỗi |
| `aio_wait(handle)` | Đợi đến khi request `DONE` hoặc `ERROR`; an toàn cả khi I/O đã hoàn tất từ trước. | `0`: thành công; số âm: lỗi |
| `aio_release(handle)` | Thu hồi slot sau khi hoàn tất và caller đã dùng xong kết quả. | `0`: thành công; số âm: lỗi |

Các lỗi cần được xử lý gồm: `-EINVAL` (tham số không hợp lệ), `-ERANGE` (vượt giới hạn đĩa), `-ENODEV` (thiết bị không hợp lệ), `-EAGAIN` (hết tài nguyên tạm thời), `-EIO` (lỗi I/O), `-ENOENT` (handle không hợp lệ) và `-EBUSY` (chưa thể giải phóng).

Để tránh nhận nhầm request cũ sau khi slot được tái sử dụng, handle cần chứa **index và generation**. Đây là API mức kernel đang được đề xuất; **chưa xác nhận** có cần triển khai thêm syscall user-space hay không.

### 3.3. Trạng thái request và vòng đời buffer

Các trạng thái chính: `FREE → QUEUED → INFLIGHT → DONE/ERROR → FREE`.

| Giai đoạn | Quy tắc an toàn |
| --- | --- |
| `submit` | Caller cung cấp kernel buffer đủ lớn và hợp lệ; request ghi nhận kích thước, block đích và chủ sở hữu. |
| `QUEUED` / `INFLIGHT` | Không được sửa, giải phóng hoặc tái sử dụng buffer khi I/O còn có thể truy cập nó. |
| `DONE` / `ERROR` | Sau khi `aio_wait()` trả về thành công, caller mới sử dụng dữ liệu đã đọc. Nếu lỗi, không dùng nội dung buffer như kết quả hợp lệ. |
| `release` | Trả request slot về pool; không cho phép giải phóng request còn thực thi; tăng generation để tránh handle cũ. |

**Lưu ý về cấp buffer:** Bản mô tả API đang chọn mô hình **caller sở hữu `kbuf`**, còn pool cấp phát các **request slot**. Nếu chuyển sang mô hình mỗi request có một buffer staging riêng, phải chốt lại API và ngân sách bộ nhớ.

Với syscall user-space (nếu được yêu cầu), việc truyền dữ liệu phải qua kernel buffer và `copyout()` trong ngữ cảnh process sau khi hoàn tất; **không DMA thẳng vào địa chỉ user**. Khi process thoát hoặc bị kill trong lúc request đang thực thi, buffer vẫn phải tồn tại cho tới completion và tài nguyên phải được thu hồi an toàn.

### 3.4. Hàng đợi, giới hạn tài nguyên và gộp request

Các tham số dự kiến cho bản đầu:

| Thành phần | Giá trị/giới hạn đề xuất | Ghi chú |
| --- | --- | --- |
| Kích thước block xv6 | `BSIZE = 1024` byte | Theo cấu hình mã nguồn được ghi nhận |
| Đơn vị địa chỉ đĩa | Sector `512` byte | Request cần căn theo block: `sector % 2 == 0` và `nbytes % BSIZE == 0` |
| Số request slot | `NREQ = 16` (ví dụ) | Giới hạn queue phần mềm; cần điều chỉnh theo thiết kế thực tế |
| Dữ liệu mỗi request | Tối đa `4 * BSIZE = 4096` byte (đề xuất) | Giả định driver xử lý được vùng DMA tương ứng; cần xác nhận layout bộ nhớ |
| Request đang bay | Tối đa `2` với `NUM = 8`, `3` descriptor/request | Chỉ đúng với định dạng descriptor đang xét |

Scheduler có thể áp dụng các chính sách như **FCFS, SCAN/LOOK hoặc Deadline** để chọn request từ hàng đợi READ. Thứ tự ưu tiên, quy tắc chống starvation và hành vi đổi policy cần được xác định trước khi đánh giá;

**Gộp read (merge)** chỉ được phép khi các request cùng thiết bị, cùng thao tác READ, địa chỉ sector liên tiếp và không vượt giới hạn kích thước/descriptor. Merge đúng nghĩa phải tạo **một lệnh thiết bị** cho các request con và trả kết quả đúng cho từng request con.

Cần lưu ý: nếu mỗi request dùng `kbuf` độc lập, chúng **không mặc nhiên tạo thành một vùng DMA liên tục**. Muốn merge thật phải chọn phương án buffer staging liên tục hoặc scatter-gather (nhiều data descriptor), đồng thời kiểm tra lại ngân sách descriptor và cơ chế completion. Vì vậy, **tính khả thi và kích thước merge tối đa vẫn là nội dung cần chốt**; không coi merge là tính năng đã hoạt động.

### 3.5. Đồng bộ hóa và phân tách trách nhiệm

- **API/request layer:** cấp slot, quản lý handle, kiểm tra input, vòng đời request và xử lý kết quả.
- **Scheduler:** quản lý hàng đợi, chọn request theo policy, chỉ dispatch khi driver còn tài nguyên.
- **VirtIO driver:** cấp descriptor, gửi lệnh xuống thiết bị, ghi nhận completion và thông báo cho request layer.

Các trạng thái request được dùng chung phải được cập nhật dưới cơ chế đồng bộ hóa thống nhất; tránh để cả driver và scheduler tự ý thay đổi cùng trạng thái mà không có quy ước sở hữu. Không giữ spinlock khi thực hiện thao tác có thể ngủ. Cần rà soát thứ tự lấy lock giữa queue mới và driver trước khi lập trình.

## 4. Kiểm thử và đánh giá

Kiểm thử cần chứng minh **đúng dữ liệu, đúng đồng bộ và có concurrency thực sự** trước khi kết luận về hiệu năng.

| Nhóm kiểm thử | Mục tiêu kiểm chứng |
| --- | --- |
| Đọc dữ liệu | Nội dung nhận được khớp với block/sector yêu cầu, kể cả vùng biên và tham số lỗi. |
| Submit bất đồng bộ | `aio_read_submit()` có thể trả về khi request chưa hoàn tất. |
| Completion-before-wait | Gọi `aio_wait()` sau khi request đã xong vẫn trả về, không bị treo. |
| Nhiều yêu cầu đồng thời | Theo dõi `max_inflight` để xác nhận có thể đạt mức 2 khi workload và driver cho phép. |
| Merge READ | Số lệnh thiết bị giảm khi gộp; mỗi request con có kết quả đúng và chỉ hoàn tất một lần. |
| Thoát process và lỗi thiết bị | Không use-after-free, mất buffer, lặp completion hoặc treo khi lỗi. |
| Hồi quy hệ thống tệp | Đường write/log hoạt động như trước; chạy các bộ test hệ thống tệp phù hợp. |

Chỉ số đề xuất: thời điểm `enqueue`, `dispatch`, `complete`; từ đó tính **thời gian đợi trong queue**, **thời gian thiết bị xử lý** và **độ trễ đầu-cuối**. Thu thập thêm `max_inflight`, số request lỗi, số lần thiếu descriptor và tỷ lệ merge. Có thể dùng bộ đếm thời gian `r_time()` thay vì `ticks` để tăng độ phân giải; trước khi báo cáo latency theo giây phải xác nhận tần số timebase trong môi trường chạy.


## 5. Các quyết định còn cần xác nhận

Để tránh mở rộng phạm vi quá sớm, nhóm cần thống nhất những điểm sau trước khi triển khai đầy đủ:

1. **Phạm vi API:** Chỉ cần kernel API hay bắt buộc có syscall từ user space?
2. **Phạm vi I/O:** Bản đầu chỉ hỗ trợ async READ và giữ WRITE đồng bộ có đáp ứng yêu cầu môn học không?
3. **Buffer và coherence:** Có chấp nhận demo đọc async ngoài buffer cache trên vùng dữ liệu kiểm soát? Sử dụng buffer của caller hay staging buffer của pool?
4. **Merge:** Driver hỗ trợ scatter-gather hay cần một vùng DMA liên tục? Giới hạn descriptor và kích thước merge là bao nhiêu?
5. **Scheduler và tài nguyên:** Chính sách nào bắt buộc (FCFS, SCAN/LOOK, Deadline)? `max_inflight = 2` có đáp ứng yêu cầu hay phải mở rộng queue/driver?
6. **Phiên bản xv6:** Xác nhận commit chuẩn và giao diện `sleep_prepare()` / `sleep()` / `wakeup()` để thống nhất khi tích hợp.

## 6. Kết luận

Phương án được đề xuất là triển khai **async READ trước, WRITE tiếp tục đồng bộ**, tách request khỏi buffer cache, sử dụng queue phần mềm và completion qua interrupt. Cách tiếp cận này giảm phạm vi thay đổi vào logging và cho phép chứng minh cơ chế I/O bất đồng bộ bằng các phép đo, bài test rõ ràng.

Tuy nhiên, ba vấn đề phải được xử lý trước khi có thể khẳng định thiết kế sẵn sàng: **nhất quán với buffer cache**, **vòng đời kernel buffer khi request/process kết thúc**, và **cơ chế DMA thực sự khi merge nhiều request**.

