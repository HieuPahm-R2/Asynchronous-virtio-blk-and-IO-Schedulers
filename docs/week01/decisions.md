# Quyết định kỹ thuật sơ bộ — tuần 1

> **Owner:** Hiếu (T1-08: buffer ownership, `bread`/`bwrite`/log, completion-before-wait,
> API async) + Lợi (T1-07: NUM/chain, lock order, định nghĩa policy).
> **Reviewer:** Hoàng. Mỗi quyết định phải ghi **lý do + hệ quả test**, không chỉ
> chép lại sách. Chỗ chưa chốt ghi `PENDING — cần GV` hoặc `PENDING — cần đo`.

## 1. Buffer ownership hiện tại (Hiếu)

Bảng cần điền — mỗi dòng là một tình huống trong code stock:

| Tình huống | Ai giữ `struct buf` | Khóa nào | Khi nào `brelse`? | Rủi ro |
| --- | --- | --- | --- | --- |
| `bread(dev, blockno)` | | `buf.lock` (sleeplock) | | |
| `bget` tìm thấy trong cache | | | | |
| `bget` recycle LRU | | | | |
| `bwrite` (chỉ log gọi) | | | | |
| buffer đang bay (`b->disk == 1`) | | | | |
| async request (đề xuất) | | | | |

Kết luận cần viết (1–3 đoạn):

- Buffer sống bao lâu trong đường đồng bộ? Điều gì đảm bảo không bị recycle?
- `refcnt` bảo vệ điều gì; `bpin/bunpin` dùng khi nào?
- Với async, cần thêm ownership/refcount gì để buffer sống tới completion?
- Vì sao **không** được release sleeplock thuộc caller trong interrupt?

## 2. Write path & logging (Hiếu)

Điền chuỗi (đánh số bước) và kết luận:

```
begin_op → log_write(b) → end_op/commit → write_log → write_head → install_trans → bwrite
```

- Vì sao giai đoạn đầu **chỉ merge read**, write giữ đồng bộ + fence?
- Write fence đề xuất: thứ tự dispatch/hoàn tất, điều kiện mở khoá.
- Ảnh hưởng tới scheduler/deadline: request write có được reorder không? Vì sao?

## 3. Completion-before-wait (Hiếu)

Giải thích bằng đúng API đang pin (`sleep_prepare()` + `sleep()` + `wakeup()`):

- Dấu hiệu completion là gì (`b->disk`, `disk.info[]`, used ring)?
- Vì sao `sleep_prepare` phải gọi **trước** `release(&vdisk_lock)`?
- Completion đến trước khi caller kịp `sleep()` thì chuyện gì xảy ra?
- Quy tắc cho interrupt: không sleep, không cấp phát có thể block, không printf mỗi request.
- Test case sẽ chứng minh: PENDING (tên case + oracle dự kiến).

## 4. API async đề xuất (Hiếu)

| Hàm | Semantics | Trả về | Buffer lifetime | Ghi chú |
| --- | --- | --- | --- | --- |
| `aio_read_submit(dev, sector, buf, nbytes)` | | handle / `-EAGAIN` | | |
| `aio_poll(id)` | | 0/1/<0 | | |
| `aio_wait(id)` | | trạng thái | | |
| `aio_release(id)` | | 0/<0 | | |

Quy tắc cần chốt:

- Queue/pool đầy → lỗi gì? Caller phải làm gì?
- Ai sở hữu buffer trong lúc INFLIGHT; copy ra user space ở đâu (process context)?
- Cấm: giữ user pointer tự do cho DMA sau khi process thoát; tái dùng slot trước khi
  device xong **và** caller thu hồi.
- Completion đúng **một lần** cho từng request (kể cả merged children).
- Đây **chưa phải tên syscall chốt** — cần hỏi GV: syscall user-space hay API kernel + demo.

## 5. Policy & lock (Lợi điền — Hiếu review)

| Nội dung | Kết luận |
| --- | --- |
| `NUM`/chain cost (`NUM=8`, 3 desc/request → tối đa 2 chain) | |
| Lock order hiện tại: `bcache.lock` → `buf.lock` → `disk.vdisk_lock` | |
| Điểm enqueue/dispatch trong code stock | |
| FCFS: tie-break, oracle test | |
| SCAN: biên capacity, chiều quét, khác LOOK ở đâu | |
| Deadline: hạn đọc/ghi, batch limit, chống starvation | |
| Đổi policy khi đang chạy: dữ liệu nào giữ, reset gì, counter nào | |

## 6. Câu hỏi mở / cần GV

| # | Câu hỏi | Owner | Trạng thái |
| ---: | --- | --- | --- |
| 1 | API async: user syscall hay kernel API + chương trình minh hoạ? | Hiếu | PENDING |
| 2 | Merging chỉ read hay cho phép write kèm fence? | Hiếu | PENDING |
| 3 | SCAN hay LOOK là định nghĩa học phần mong đợi? | Lợi | PENDING |
| 4 | Tag xv6 chính thức (API sleep cũ/mới)? | Hoàng | PENDING |

## 7. Review của Hoàng

- [ ] Buffer ownership đúng với code stock (`bio.c`, `virtio_disk.c`)
- [ ] Có kết luận write synchronous/fence
- [ ] Completion-before-wait giải thích bằng API đang pin (không dùng `sleep(chan,lock)`)
- [ ] API async có quy tắc buffer lifetime + lỗi queue đầy
- Nhận xét: TODO
