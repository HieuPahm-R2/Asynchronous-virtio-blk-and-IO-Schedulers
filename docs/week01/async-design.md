# Thiết kế submit và complete bất đồng bộ đề xuất

Hoàng, T1-06/T1-11, 23/10/2026. DESIGN ONLY: các API dưới đây chưa có trong
kernel hiện tại, chưa có kết quả test async. Tên hàm/errno/chữ ký chờ nhóm
review. Xem sequence ở [Mermaid](diagrams/async-submit-complete.mmd) và
[SVG](diagrams/async-submit-complete.svg).

Bản chỉnh sửa trong draw.io: [virtio-submit-complete.drawio](diagrams/virtio-submit-complete.drawio), trang **02 Async đề xuất**. Mọi nhãn, lifeline và mũi tên là đối tượng riêng, không phải ảnh nhúng.

## Contract và hai vòng đời

Async read dùng kernel buffer riêng, không DMA vào user pointer hoặc stack
sống ngắn. Pool hữu hạn sở hữu header/status/buffer. Submit enqueue rồi trả
handle; không đợi device. Nếu bước chuẩn bị buffer có thể block, phải tách nó
khỏi try-submit. Slot đầy trả lỗi (đề xuất EAGAIN), không ngủ trong IRQ.

Request: FREE -> ALLOCATED -> QUEUED -> INFLIGHT -> DONE/ERROR -> FREE.
Descriptor: FREE -> RESERVED -> PUBLISHED -> USED -> RECLAIMED -> FREE.
Trong đề xuất, IRQ thu hồi descriptor sau completion thật, giữ request/result/
buffer tới aio_release. Đây là thay đổi với stock, phải test head reuse trước
caller release. Bản đầu chưa merge; mapping một head tới một request.

Một spinlock chung, gọi tạm io_lock, bảo vệ queue/state/head map/descriptor ở
phiên bản đầu. Cần thống nhất với Lợi/Hiếu, không lồng thêm khóa theo thứ tự
ngược vdisk_lock. Tài nguyên cho dispatch IRQ được chuẩn bị trước, không
malloc/block, không copyout hoặc nhả buf sleeplock của caller.

| API logic | Contract |
| --- | --- |
| aio_read_submit | validate, try-allocate, enqueue, dispatch nếu đủ chỗ, trả handle/lỗi |
| aio_poll | PENDING/DONE/ERROR dưới khóa |
| aio_wait | process context; while, sleep_prepare(req), release, sleep, acquire |
| aio_release | chỉ terminal state và không còn DMA/ref; free slot, đổi generation |

Wrapper virtio_disk_rw đồng bộ sau này là submit -> wait -> release; buf
sleeplock vẫn thuộc caller. Write/log giữ thứ tự cũ, không tự ý reorder/merge.
Chỉ có wrapper sync chưa đủ chứng minh ordering khi trộn với async read:
cần thống nhất ordering domain/fence với nhóm trước khi sửa kernel.

## Pseudocode đề xuất

```text
aio_read_submit(args):
  acquire(io_lock)
  req = try_alloc_prepared_slot()  // full -> EAGAIN, không sleep
  validate(args)                  // lỗi -> rollback slot
  req.state = QUEUED; enqueue(req)
  dispatch_locked()               // đủ 3 desc mới publish + fence + notify
  handle = (req.id, req.generation)
  release(io_lock)
  return handle

aio_wait(handle):
  acquire(io_lock)
  req = validate_handle(handle)    // lỗi -> trả lỗi trước dereference
  while req.state in {QUEUED, INFLIGHT}:
    sleep_prepare(req)            // còn giữ khóa state
    release(io_lock)
    sleep()
    acquire(io_lock)
  result = req.status
  release(io_lock)
  return result                    // release request là bước riêng

completion_irq():
  acquire(io_lock)
  ack_mmio_and_fence()
  while have_unconsumed_used_entry():
    head = used_head(); req = head_to_req[head]
    validate_mapping_and_state(req)
    status = read_device_status(req)
    clear_mapping(head); free_chain(head)
    advance_used_idx()
    req.status = status; req.state = DONE_or_ERROR(status)
    wakeup(req)
  dispatch_locked()                // tiến triển dù producer đã ngủ
  release(io_lock)
  // devintr gọi plic_complete sau khi handler trả
```

Đây không phải C build được nguyên trạng. Trong triển khai phải thêm reference
counting, validation, cleanup đúng một lần và generation. Timeout/kill caller
không có nghĩa device đã dừng DMA: giữ buffer tới completion hoặc reset được
xác nhận an toàn. Không free chỉ vì caller hết thời gian chờ.

## Bất biến và kiểm chứng tuần sau

1. Head map chỉ trỏ request INFLIGHT; clear map trước reuse descriptor.
2. Thiếu descriptor không publish chain dở; giữ QUEUED, completion gọi dispatch
   tiếp để tránh queue kẹt khi producer không submit nữa.
3. Mỗi request complete một lần; submitted = completed + inflight + queued
   (không tính bị từ chối). DONE/ERROR chưa release vẫn chiếm pool slot.
4. Dispatcher đặt INFLIGHT và head map trước publication/notify; completion trước wait trả ngay; prepare/release/sleep không mất wakeup.
5. Header/status/buffer sống suốt DMA; kết quả không overwrite trước release;
   stale handle bị từ chối sau khi đổi generation.
6. Error truyền về caller và reclaim descriptor; write ordering phải giữ đúng.

Test kế tiếp: 2 submit trước wait với pattern/checksum riêng, trace
max_inflight>=2; descriptor/pool đầy; complete-before-wait; IOERR/UNSUPP;
reverse completion order; head reuse trước release; CPUS=1/4, accounting sau
drain và stock usertests/grind. Các test async này hiện đều NOT RUN.
Hai submit trước wait trên hình chỉ là lịch minh họa, không thay cho số đo.

## Nguồn bố cục hiện tại

File draw.io và SVG đã đồng bộ theo bản người dùng chỉnh sửa trong
[ProjectTerm - ET4290](https://app.diagrams.net/#G1lpHCZ3cDq0vzGF7y1B910eJgA_-NZf_m).
Mermaid giữ thứ tự thông điệp tương đương, không điều khiển bố cục.
Các API và reclaim trong IRQ ở đây vẫn là đề xuất, không phải mã đã triển khai.
