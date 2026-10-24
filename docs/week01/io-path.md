# Bản đồ đường I/O & lock — tuần 1 (T1-06)

> **Owner:** Hoàng. **Reviewer:** Hiếu. Điền theo [`../architecture.md`](../architecture.md)
> mục 1.
>
> Yêu cầu checklist: mô tả **cả đường descriptor hết** (khi không còn descriptor
> free), không kết luận stock chỉ có 1 outstanding khi chưa đo.

## 1. Sơ đồ (dán ảnh FigJam / Mermaid)

TODO — link ảnh hoặc sơ đồ Mermaid.

## 2. Luồng `bread` / `bwrite` → driver → interrupt → wakeup

| Bước | Hàm | Lock đang giữ | Ghi chú |
| ---: | --- | --- | --- |
| 1 | `bread` → `bget` | `bcache.lock` → `buf.lock` | |
| 2 | `virtio_disk_rw` | `disk.vdisk_lock` | cấp 3 descriptor, format, notify |
| 3 | sleep chờ `b->disk` | giải phóng `vdisk_lock` khi `sleep_prepare`+`release` | tránh mất wakeup |
| 4 | `devintr` → `virtio_disk_intr` | `vdisk_lock` | đọc used ring, `b->disk=0`, `wakeup` |
| 5 | caller thức, `free_chain` | | trả descriptor, `brelse` |

## 3. Descriptor lifecycle & đường "hết descriptor"

- `NUM = 8`, mỗi request 3 descriptor → tối đa **2 chain** đồng thời; caller thứ 3
  ngủ chờ `disk.free[0]` (kênh chờ nào?).
- `alloc_desc/free_desc/free_chain` hoạt động ra sao? Điều gì xảy ra khi `alloc3_desc`
  trả `-1`?
- Đo thực tế: cần spike counter `max_inflight` (chưa có — ghi NOT RUN).

## 4. Lock order & điểm ngủ

- Thứ tự khóa: `bcache.lock` → `buf.lock` (sleeplock) → `disk.vdisk_lock`.
- Nơi được sleep: `virtio_disk_rw` (chờ descriptor, chờ completion), `acquiresleep`.
- Quy tắc: interrupt **không** sleep; không release sleeplock của caller trong IRQ.



