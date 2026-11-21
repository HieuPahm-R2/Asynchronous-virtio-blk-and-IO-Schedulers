# Review phần driver/IRQ/API của Hoàng - 16/11/2026

Base đã đọc: Hiếu `ae6a7cf` (I01 `360b4df`), kế thừa Lợi `0dc296e`
(code deadline/switch `7ae79f7`). Phần test H01/H02 được bổ sung trên nhánh riêng.
Không xác nhận thay review của Lợi/Hiếu hoặc phê duyệt giảng viên.

| Phần review | Kết luận |
| --- | --- |
| `io_dispatch_locked` | Pick thuần; driver nhận rồi mới unlink/commit state/trace; EAGAIN không commit. `last_block` được cập nhật ở mọi policy. |
| `io_set_policy` / `_locked` | Wrapper lấy đúng một io_lock; validate/no-op trước mutation; không reset queue/id/gen/age, không free INFLIGHT; switch không tự dispatch. |
| `io_get_snapshot` | Public wrapper lấy io_lock; `_locked` helpers không acquire lại, request/queue/descriptor/latency cùng snapshot. Không dựng snapshot tải từ hai public getter khác thời điểm. |
| IRQ/completion | Reap ASYNC dưới io_lock; descriptor trả trước terminal/wakeup; không early free staging slot INFLIGHT. Thay đổi của Hoàng ở driver chỉ mở test hooks cho cờ stress mới. |
| Clock/timing | Đọc ticks trực tiếp, không thêm io_lock -> tickslock; phép tuổi wrap-safe theo miền D21. Debug tick không chứng minh latency vật lý; tổng uint có thể tràn trong chạy dài, chưa phải benchmark dài hạn. |
| Trace | 64 event, overflow được đếm. Ca READ thật reset trace test-only ở queue rỗng; không reset state/counter; stress dài dùng snapshot, không dùng trace cắt cụt làm bằng chứng đầy đủ. |
| Ownership | Không có owner_pid/orphan/cancel implementation trong base này. Không nhận claim cleanup khi kill ở báo cáo tuần 3 là code đã tồn tại. |
| I02 merge/lifecycle | Không free INFLIGHT/buffer DMA; cần buffer/master-child hữu hạn, fan-out đúng một lần và cleanup/coherence review trước khi code. Thiết kế không phải kết quả implementation. |

Kiểm động dùng cả model/6 mutant của Hiếu và READ thật/switch stress mới của Hoàng.
Các ca expired đợi thời gian thực, no-op/enum sai/EAGAIN và bảo toàn arrival/gen/seq
được kiểm riêng. Đối chứng hỏng dữ liệu và thay đổi marker/event trong log kiểm
khả năng oracle từ chối. Evidence cuối được dẫn trong báo cáo sau khi chạy suite.
