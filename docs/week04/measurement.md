# W4-I01 — Snapshot, counters và đo lường (schema + kết quả mẫu)

Tài liệu này là phần đo lường của contract tuần 4 (xem
[`interface.md`](interface.md) D23/D24). Nó trả lời ba câu:

1. Snapshot gồm **những trường nào**, loại **counter tích luỹ** hay **gauge hiện
   tại**, đọc dưới khoá nào?
2. Latency được định nghĩa và tính bằng đơn vị gì, độ phân giải bao nhiêu?
3. Với revision `360b4df`, đo được **con số nào** và **được/không được kết luận gì**?

Code: `struct io_snapshot`/`struct io_latency_stats` trong
[`kernel/io_request.h`](../../kernel/io_request.h);
`io_snapshot_locked()`/`io_get_snapshot()`/`io_latency_record_locked()` trong
[`kernel/io_request.c`](../../kernel/io_request.c);
`virtio_disk_get_stats_locked()` trong [`kernel/virtio_disk.c`](../../kernel/virtio_disk.c).
Header là nguồn sự thật; file này chỉ diễn giải.

---

## 1. Snapshot một khoá

`io_get_snapshot(struct io_snapshot *out)` là entry point process-context: acquire
`io_lock` (= `virtio_disk_io_lock()` = `&disk.vdisk_lock`) **một lần**, gọi các
helper `*_locked` rồi release. Vì vậy mọi trường trong một snapshot thuộc **cùng
một thời điểm**; không được ghép `io_get_stats()` với `virtio_disk_get_stats()`
(hai lần khoá khác nhau).

Quy ước: **S/C/E/R** là counter **tích luỹ** (không bao giờ giảm); **Q/I/D/X/F**
là gauge **hiện tại**; `desc.free_desc` là gauge descriptor hiện tại.

| Nhóm | Trường | Loại | Ý nghĩa / nguồn |
| :--- | :--- | :---: | :--- |
| Request | `submitted` (S) | tích luỹ | `aio_read_submit()` thành công (handle đã cấp) |
| Request | `completed` (C) | tích luỹ | request vào `DONE` |
| Request | `errors` (E) | tích luỹ | request vào `ERROR` (device status != 0) |
| Request | `released` (R) | tích luỹ | slot terminal được `aio_release`/auto-free; **không** phải gauge |
| Request | `queued` (Q), `inflight` (I), `done` (D), `error` (X) | gauge | suy ra từ state của 16 slot, không thể lệch pool |
| Request | `free_req` (F) | gauge | `IO_NREQ - (Q+I+D+X)` |
| Request | `max_inflight` | tích luỹ (max) | số chain đã publish mà phần mềm chưa reap — **không** phải song song thiết bị |
| Request | `eagain_pool`, `stale_handle` | tích luỹ | submit bị từ chối vì pool đầy / handle stale |
| Queue | `enqueued`, `dispatched`, `eagain` | tích luỹ | request vào queue / driver đã nhận / vòng dispatch dừng vì EAGAIN |
| Queue | `boundary_events` | tích luỹ | số event biên SCAN đã commit |
| Queue | `policy_switches` | tích luỹ | số lần đổi policy đã commit (no-op/invalid không tính) |
| Queue | `dl_expired`, `dl_fifo` | tích luỹ | dispatch DEADLINE vì expired / vì chạm batch limit |
| Queue | `trace_overflow` | tích luỹ | event đã commit nhưng không ghi được vì trace 64 đầy |
| Policy | `policy`, `epoch`, `batch_count`, `last_block`, `has_last` | trạng thái | D21/D22; `epoch == policy_switches` trong MVP |
| Driver | `desc.free_desc`, `desc.eagain_desc`, `desc.completed_stock/async`, `desc.head_reuse` | gauge/tích luỹ | descriptor còn trống (0..8), owner STOCK/ASYNC, head reuse |
| Timing | `ticks_now` | mốc | `ticks` tại thời điểm snapshot (đơn vị tick) |
| Timing | `latency.samples`, `wait_*`, `service_*`, `total_*`, `zero_total` | tổng hợp | xem §2 |

### 1.1 Bất biến kiểm trong kernel và oracle

```
S = Q + I + C + E
C + E = R + D + X
IO_NREQ = F + Q + I + D + X
epoch = policy_switches                       (MVP: 1 switch = 1 epoch)
desc.free_desc <= NUM (8)
samples == 0  =>  wait_sum/service_sum/total_sum == 0
Sau drain: S = C + E = R; Q = I = D = X = 0; F = 16; free_desc = 8
```

Kernel tự kiểm các bất biến này trong self-test (`snapshot_invariants()` ở
`kernel/io_queue_test.c`); oracle Python kiểm lại **độc lập** từ model contract và
đối chiếu từng counter (`dl_expired`, `dl_fifo`, `policy_switches`, `eagain`,
`boundary_events`, `batch_count`, `last_block`, ...) với expected tính từ fixture.

---

## 2. Latency: định nghĩa, đơn vị, độ phân giải

| Đại lượng | Công thức | Nghĩa |
| :--- | :--- | :--- |
| Queue wait | `t_dispatch - t_enqueue` | thời gian nằm `QUEUED` trước khi driver publish |
| Service | `t_complete - t_dispatch` | thời gian `INFLIGHT` tới terminal (gồm DMA + IRQ + reap) |
| Total | `t_complete - t_enqueue` | end-to-end của một READ async |
| Tổng hợp | `*_sum`, `*_max`, `samples` | cộng/max trên mọi request terminal; `uint` wrap-safe |

- **Đơn vị:** tick của xv6. Timer pin `TIMER_INTERVAL = 1e6` cycles ≈ **10 tick/s**,
  tức **1 tick ≈ 100 ms**.
- **Độ phân giải = 1 tick.** Mẫu có `total == 0` nghĩa là request xong **trong cùng
  tick** (dưới 100 ms), **không** phải 0 ms. Vì vậy luôn báo kèm `zero_total` và
  `samples`; không dựng p99 từ mẫu 0.
- `t_dispatch` do `io_started_locked()` gán khi driver publish; `t_complete` do
  `io_async_completed_locked()` gán; `t_enqueue` do `io_queue_enqueue_locked()` gán
  (không reset khi switch/EAGAIN). Cả ba ghi dưới `io_lock`.
- Không đọc `ticks` qua `tickslock` trong đường này (tránh thứ tự khoá mới); chấp
  nhận đọc một word không khoá giống tuần 2.

### 2.1 Kết quả mẫu trên revision `360b4df`

Nguồn: `results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/`
(máy WSL2, `riscv64-linux-gnu-gcc` 13.3.0, QEMU 8.2.2, CPUS=1).

| Lượt | Nguồn log | `samples` | `wait_sum/max` | `service_sum/max` | `total_sum/max` | `zero_total` | Diễn giải |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| READ thật cơ bản (FCFS, `IO_HW_SELFTEST`) | `hw-cpus1-snap.log` | **83** | 0 / 0 | 0 / 0 | 0 / 0 | **83** | mọi READ xong trong cùng tick → dưới 100 ms; tick quá thô để kết luận latency |
| Mock deadline/switch (`IOQ_SELFTEST`) | `policy-cpus1.log` | 0 | 0 | 0 | 0 | 0 | mock driver không đi qua request layer thật (không phải lỗi) |

Snapshot tương ứng của lượt READ thật: `S=83, C=81, E=2, R=83, Q=I=D=X=0, F=16,
free_desc=8, ticks=4, trace_overflow=19`. Hai `ERROR` là **cố ý** của suite hardware
(status lỗi tiêm sau DMA cho error-path), không phải lỗi dữ liệu ngoài dự kiến;
`S = C + E = R = 83` và tài nguyên cân bằng sau drain.

**Kết luận được:** snapshot/kế toán đúng, drain sạch, latency **đo được** (83 mẫu).
**Không được kết luận:** "latency trung bình 0 ms", "deadline nhanh hơn FCFS",
"QEMU seek nhanh/chậm". Muốn có phân bố latency cần: (a) workload đủ lớn để vượt
1 tick, (b) hoặc tăng độ phân giải (đổi nguồn thời gian, phải review), (c) hoặc
benchmark ≥ 5 lần/điểm ở tuần sau. Tick 100 ms không đủ cho p50/p99.

---

## 3. Trace và giới hạn xuất log

- Trace 64 event (`IOQ_TRACE_N = 64`) chỉ ghi sự kiện **đã commit**, dưới `io_lock`.
  Tràn: `trace_overflow++`, **không** ghi đè vòng. Lượt READ thật dài ở trên có
  `trace_overflow = 19` ⇒ **trace không đủ event** để chấm thứ tự toàn bộ; dùng
  counters/checksum cho stress dài, chỉ dùng trace cho test ngắn.
- Không `printk` trong IRQ; copy snapshot/trace ra buffer hữu hạn dưới khoá rồi in ở
  process context, ngoài khoá.
- Oracle phải phát hiện **thiếu marker/END/timeout** là FAIL, không chỉ tìm chuỗi
  `PASS`.

---

## 4. Cách dùng / tái lập

```bash
# E8: READ thật cơ bản + IO-SNAP (1 boot CPU1, không thay H01/H02)
TOOLPREFIX=riscv64-linux-gnu- python3 scripts/check-week04-oracle-hieu.py
# Log + snapshot:
#   results/week04/oracle-hieu/<host>-<stamp>/hw-cpus1-snap.log
#   grep '^IO-SNAP:' results/week04/oracle-hieu/<host>-<stamp>/hw-cpus1-snap.log
```

Với benchmark sau này, mỗi điểm đo phải ghi: commit, policy, expiry/batch, CPU,
seed/fixture, số boot/READ, `samples`, `zero_total`, `trace_overflow`, và **không**
trộn trung bình giữa các workload khác nhau.
