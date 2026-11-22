# W5-G02 / W5-I01 - Rà soát driver, IRQ và vòng đời dữ liệu

Ngày rà soát 22/11/2026. Revision nguồn `f5a1c04ebd20c6e69ff124b2c1f13301f87b1d68`. Ghi chú kỹ thuật để Hoàng dùng khi review cùng nhóm.

## Driver và hồi quy bản đã tích hợp

| Đường kiểm | Quan sát trong mã nguồn | Kiểm chứng |
| --- | --- | --- |
| Submit / EAGAIN | `virtio_disk_try_submit_read()` giữ cùng lock với dispatcher. `alloc3_desc()` trả lại descriptor cấp dở. Dispatcher chỉ unlink và cập nhật trạng thái chọn khi driver nhận request. | Real-policy CPU1/4, mock deadline/switch và negative control EAGAIN |
| Publish và IRQ | Driver ghi mapping owner, generation và `INFLIGHT` trước khi publish avail ring. `reap_head_locked()` xác minh used head, generation, head và state trước khi thu hồi chain. Nhánh STOCK để caller đồng bộ thu hồi chain. | FCFS real-virtio gồm test đảo thứ tự consume hai used entry và kiểm state sau drain |
| Lifetime | DMA dùng staging buffer theo slot. `aio_release()` từ chối slot đang QUEUED/INFLIGHT hoặc có waiter. Kết quả chỉ đọc sau DONE và trước release theo hợp đồng single-consumer. | Real fixture đọc đủ 1.024 byte mỗi block, stale handle sau release, pool/mock và 16 slot + 8 descriptor sau drain |
| Lock và wakeup | `aio_wait()` đăng ký sleep channel dưới `io_lock`, thả lock trước `sleep()` và kiểm state dưới lock khi quay lại. Snapshot lấy counters cùng lock. | Kiểm completion trước wait và khe prepare/sleep của harness FCFS, cùng oracle snapshot |

Nguồn đối chiếu: `kernel/virtio_disk.c`, `kernel/io_request.c`, `kernel/io_queue.c`, `kernel/io_hw_test.c` và `tests/cases/io_real_policy.py`.

## Nhận xét thiết kế merge cho tuần 6

1. **DMA và offset sau prepend/cancel.** Một command dùng ba descriptor theo layout hiện tại. Chốt `start`, số block, định danh `(id, gen)` và offset của từng child ngay trước publish. Tính offset bằng chênh lệch block so với `start`. Giữ mapping và bounce bất biến tới lúc IRQ reap. Với BOOT test, kiểm một used head cho toàn command và checksum khác nhau giữa các child để phát hiện nhầm slice.
2. **Fan-out và giải phóng.** Status thuộc toàn command. Khi lỗi, đặt mọi child còn sống thành ERROR với cùng mã và bỏ copy. Khi thành công, copy slice vào buffer của child còn owner trước khi công bố DONE/wakeup. Tái sử dụng bounce sau khi xử lý xong tất cả child. Thu hồi chain đúng một lần theo used head. Dùng negative control bỏ fan-out, đổi offset và thu hồi bounce trước fan-out.
3. **Tách miền kế toán.** Chốt một biểu diễn cho cancel. Nếu child cancel vẫn giữ slot ERROR cho caller thu hồi, nó đã nằm trong tổng `E` và state `X` ở D23, còn `canceled` là counter phân loại. Cộng `canceled` vào phương trình song song với `E` sẽ đếm đôi. Khi auto-free vì exit, cập nhật terminal, release và generation đúng một lần. Test cancel giữa dải kèm fallback, queue order và pool cạn.
4. **Giới hạn tài nguyên.** Thiết kế dành hai bounce 4 KiB và tám descriptor, đủ tối đa hai chain ba descriptor. Làm rõ single-block fallback dùng slot trực tiếp khi hết `merge_cmd` và đường IRQ phân biệt single với merged. Kiểm HEAD reuse xen request STOCK. Bảo toàn giới hạn image/device, và đo thời gian IRQ giữ lock khi copy tối đa 4 KiB.
5. **Exit và kill.** Giữ trình tự `io_lock` trước `p->lock` trên đường wakeup. Gọi cleanup từ `kexit` trước vùng giữ lock tiến trình. `ORPHAN` giữ slot và buffer khi DMA đang hoạt động. Thiết kế riêng wakeup cho kill-aware wait trước khi cam kết `EINTR`. Rà lại quyền sở hữu của con trỏ do `aio_data()` trả và consumer còn đọc trước auto-free.

Đối chiếu với [thiết kế W5-I01](merge-owner-cancel.md), đặc biệt §3-§10. Các nhận xét trên là đầu vào cho PTO-41 và M1-M10/N1-N4. Phần thực thi tuần 5 là kiểm thử bản tích hợp và review kỹ thuật. Phê duyệt PR chính thức vẫn thuộc reviewer của nhóm.
