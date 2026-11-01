# Báo cáo kỹ thuật cá nhân — Tuần 2 (26/10 – 01/11/2026)

> **Người thực hiện:** Phạm Quý Lợi (MSSV: 20233501)

> **Trạng thái tổng quan:** Hai card kỹ thuật W2-L01 và W2-L02 đã có mã nguồn kernel, bộ self-test MOCK và oracle trên nhánh `week2/loi` (4 commit, chưa merge). Self-test MOCK **PASS 9/9** trên commit sạch `657e1b5`; hai mutant M1/M2 đều bị test bắt. **Cả hai card đang chờ review** (Hoàng review L01, Hiếu review L02). Các ca cần driver thật (T07/T13 trên QEMU, T11 ×10, CPUS=4) là **NOT RUN**; build thường và `make test-fast` **BLOCKED** chờ H01.

---

## 1. Tóm tắt

### Phần của Lợi nằm ở đâu trong hệ thống (đọc trước)

Một lệnh đọc bất đồng bộ đi qua 4 phần do 3 người làm:

```
aio_read_submit (Hiếu, I01/I02)
   │  cấp 1 slot trong request pool
   ▼
io_queue_enqueue_locked  ──►  HÀNG ĐỢI CHỜ (Lợi, L01)
                                    │ io_dispatch_locked: lấy request đến trước nhất
                                    ▼
                     virtio_disk_try_submit_read (Hoàng, H01)
                        │ trả 0 = đã gửi xuống đĩa
                        │ trả IO_EAGAIN = đĩa đang đầy, request ở lại hàng đợi
                        ▼
                     ngắt hoàn tất virtio_disk_intr (Hoàng, H02)
                        │ trả descriptor, báo DONE cho Hiếu
                        └──► gọi lại io_dispatch_locked để đẩy request kế tiếp
```

Vì sao cần hàng đợi: virtio-blk của xv6 chỉ có 8 descriptor, mỗi lệnh đọc tốn 3 cái, nên **cùng lúc chỉ 2 lệnh nằm trong đĩa**. Pool của Hiếu cho tới 16 request. 14 request còn lại phải xếp hàng chờ, và hàng đợi của Lợi quyết định **ai được vào đĩa tiếp theo**. Tuần 2 dùng quy tắc đơn giản nhất là **FCFS (đến trước phục vụ trước)**. Các tuần sau sẽ thay bằng SCAN/deadline mà không phải sửa phần của Hiếu và Hoàng.

### Hai card đã làm

1. **W2-L01 (Pending queue và dispatcher FCFS):** viết `kernel/io_queue.c` đúng các hàm đã chốt trong contract G01. Request mới vào cuối hàng, dispatcher lấy ở đầu hàng. Khi đĩa báo đầy (`IO_EAGAIN`) thì dừng, không làm mất request. Khi một lệnh hoàn tất thì dispatcher được gọi lại để đẩy tiếp.
2. **W2-L02 (Oracle FCFS và test khi thiếu tài nguyên):** vì driver thật của Hoàng chưa xong, Lợi viết một **driver giả có đúng 2 chỗ** để ép tình huống đĩa đầy, kèm một oracle Python biết trước thứ tự đúng. Test chỉ được build khi bật cờ `-DIOQ_SELFTEST`, nên kernel bình thường không bị ảnh hưởng.

---

## 2. Chi tiết công việc đã thực hiện

### 2.1 W2-L01 — Pending queue và dispatcher FCFS (PTO-14)

#### Bối cảnh và bài toán kỹ thuật

Contract G01 của Hiếu đã chốt hàng đợi phải có 4 hàm và chạy dưới một khoá chung `io_lock` (D6). Bài toán: giữ đúng thứ tự đến, không mất request khi đĩa đầy, và tự đẩy request kế tiếp khi có chỗ trống mà không cần ai chờ.

#### Nội dung kỹ thuật đã triển khai

| Hàm | Ai gọi | Làm gì |
| :-- | :-- | :-- |
| `io_queue_init()` | `main()` lúc khởi động | Đưa hàng đợi về rỗng, bộ đếm về 0 |
| `io_queue_enqueue_locked(req)` | `aio_read_submit` (Hiếu), đang giữ `io_lock` | Chỉ nhận request ở `IO_ALLOCATED` (sai thì panic). Gán số thứ tự `enqueue_seq` tăng dần, chuyển sang `IO_QUEUED`, nối vào **cuối** hàng qua trường `next` |
| `io_dispatch_locked()` | sau enqueue; trong ngắt `virtio_disk_intr` (Hoàng); trong đường stock `virtio_disk_rw` | Lặp: lấy request ở **đầu** hàng, gọi `virtio_disk_try_submit_read`. Trả 0 thì bỏ khỏi hàng. Trả `IO_EAGAIN` thì dừng và để nguyên request. Mã lỗi khác thì panic |
| `io_queue_count_locked()` | test, thống kê | Số request đang chờ |

Điểm cần Hoàng và Hiếu biết khi tích hợp:

- `io_dispatch_locked` có thể chạy trong **ngắt** (được gọi từ `virtio_disk_intr`), nên `virtio_disk_try_submit_read` không được ngủ.
- Queue không tự lấy khoá. Người gọi phải giữ `io_lock` (hậu tố `_locked`).
- Bất biến luôn đúng: `enqueued = dispatched + số đang chờ`.

#### Kết quả bàn giao

- `kernel/io_queue.c` (151 dòng), `kernel/io_queue_test.h` (23 dòng).
- `Makefile`: thêm `io_queue.o`, `io_queue_test.o` vào `OBJS` và dòng `CFLAGS += $(EXTRA_CFLAGS)` để bật cờ test khi cần.
- Commit `7a0f195` trên nhánh `week2/loi`.

**Giới hạn:** build thường chưa link được vì cần `virtio_disk_try_submit_read` của Hoàng (H01). Ba chỗ gọi dispatch thật nằm ở phần của Hiếu/Hoàng và sẽ nối ở G02.

---

### 2.2 W2-L02 — Oracle FCFS và test khi thiếu tài nguyên (PTO-15)

#### Nội dung kỹ thuật đã triển khai

- **Driver giả 2 chỗ** (`kernel/io_queue_test.c`): giống virtio thật chỉ nhận 2 lệnh. Chỗ thứ 3 trở đi trả `IO_EAGAIN`. Khi giả lập “hoàn tất”, nó gọi lại `io_dispatch_locked` y như ngắt thật sẽ làm.
- **Dữ liệu vào:** 5 request đọc block 7, 2, 9, 1, 4, cố ý không theo thứ tự số block để phân biệt FCFS với các cách sắp khác.
- **Oracle** (`tests/cases/ioq_fcfs.py`): kỳ vọng thứ tự vào đĩa `seq=1,2,3,4,5`, tức `blk=7,2,9,1,4`.
- **Hook chỉ cho test:** `io_queue_set_submit_for_test()` thay driver thật bằng driver giả; chỉ tồn tại khi build với `-DIOQ_SELFTEST`. `kernel/main.c` gọi `ioq_selftest()` trong `#ifdef IOQ_SELFTEST`.
- `tests/runner.py`: thêm tag `selftest` vào danh sách loại trừ mặc định, nên `make test` không chạy case này.

#### Bằng chứng thực nghiệm

- Lần chạy sạch `results/week02/laptop-Loi/mock-2026-11-01_151853/` (commit `657e1b5`): **9/9 PASS**, `fail=0`, `seq=1,2,3,4,5`.
- **Negative control:** M1 (thêm vào đầu hàng, thành LIFO) cho `seq=1,2,5,4,3`, `fail=1`. M2 (bỏ lời gọi dispatch khi hoàn tất) làm hàng đợi kẹt ở `seq=1,2`, `fail=4`. Hai mutant được hoàn lại, không commit code sửa.
- Commit `657e1b5` (test), `785e1ac` và `6526009` (kết quả).

**Tiêu chí nghiệm thu card:** ✅ Oracle FCFS có và khớp. ✅ EAGAIN giữ request, không mất, không gửi trùng. ✅ Mutant chứng minh test bắt được lỗi. ⬜ Chưa chạy với driver thật trên QEMU. ⬜ Chưa có review của Hiếu.

---

### 2.3 Đối chiếu Jira tuần 1 (PTO-4/7/9/10/11)

| Issue | Bằng chứng trong repo | Trạng thái |
| :-- | :-- | :-- |
| PTO-4 (virtio\_disk\_rw, descriptor) | `docs/week01/io-path.md`, commit `bfe5db8` | Done |
| PTO-9, PTO-10, PTO-11 (sequence diagram) | `docs/week01/diagrams/` (`.mmd`, `.svg`, `.drawio`), commit `bfe5db8` | Done |
| PTO-7 (câu hỏi GV) | `docs/week01/kickoff.md` vẫn PENDING | Giữ In Progress |

---

## 3. Tổng hợp kết quả kiểm thử và bằng chứng thực nghiệm

### 3.1 Các ca kiểm thử đã đạt (PASS)

Môi trường: WSL2 Ubuntu-24.04, riscv64-linux-gnu-gcc 13.3.0, QEMU 8.2.2, Python 3.12.3, CPUS=1, xv6 pin `f780d785`.

| Nhóm kiểm thử | Nội dung | Kết quả | Bằng chứng |
| :-- | :-- | :-- | :-- |
| **T07 (MOCK)** — thiếu chỗ trong đĩa | `two-inflight`, `three-queued`, `eagain-seen`, `eagain-keeps-queued`, `progress-after-complete`, `each-dispatched-once` | PASS 6/6 | `mock-2026-11-01_151853` |
| **T11 (phần MOCK)** — xả hàng đợi | `drain-queue-empty`, `drain-no-inflight`, `counters` | PASS 3/3 | như trên |
| **T13 (nửa MOCK)** — thứ tự FCFS | `seq=1,2,3,4,5`, `blk=7,2,9,1,4`, khớp oracle | PASS | như trên |
| **Negative control** | M1 (LIFO) ⇒ FAIL `seq=1,2,5,4,3`; M2 (bỏ dispatch) ⇒ FAIL `seq=1,2`, `fail=4` | FAIL đúng dự kiến | `mutant-M1`, `mutant-M2` |

Tất cả nằm trong `results/week02/laptop-Loi/` trên nhánh `week2/loi`. Lần chạy `mock-2026-11-01_125516` (dirty, trước khi commit `main.c`) đã được thay bởi lần chạy sạch.

### 3.2 Các ca kiểm thử chưa chạy (NOT RUN)

| Ca kiểm thử | Lý do | Kế hoạch |
| :-- | :-- | :-: |
| **T07, T13 trên QEMU với driver thật** | Cần `virtio_disk_try_submit_read` (H01) và các chỗ gọi dispatch (I01/H02) | Mốc G02 |
| **T11 lặp 10 lần, đo `free_desc`/pool sau drain** | Driver giả không có descriptor thật | Mốc G02 |
| **CPUS=4** | Mới chạy CPUS=1 | Mốc G02 |
| **`make test-fast` trên nhánh `week2/loi`** | BLOCKED: build thường thiếu symbol của H01 | Sau khi H01 merge |

---

## 4. Trạng thái, Điểm nghẽn kỹ thuật và Công việc tồn đọng

| Nội dung công việc | Người phụ trách | Trạng thái hiện tại | Ghi chú |
| :-- | :-: | :-: | :-- |
| Review W2-L01 (queue/dispatcher) | Hoàng | ⬜ PENDING | Review trên nhánh `week2/loi`, commit `7a0f195` |
| Review W2-L02 (self-test/oracle) | Hiếu | ⬜ PENDING | Commit `657e1b5` và thư mục `results/week02/laptop-Loi/` |
| Review tích hợp W2-G02 | Lợi | ⏳ Chờ H01/H02/I01 | Chưa bắt đầu |
| Gửi GV câu #2 (lịch/hạn nộp) và #4 (SCAN hay LOOK) | Lợi | ⬜ CHƯA GỬI | Giữ tại PTO-7 |
| Đối chiếu PTO-4/7/9/10/11 | Lợi | ✅ Đã đối chiếu | Xem mục 2.3 |
| Điều phối báo cáo tuần 2 (W2-G03) | Lợi | ⏳ Đang làm |  |

**Phân tích điểm nghẽn:** hàng đợi của Lợi đã chạy đúng với driver giả, nhưng chỉ kiểm được với đĩa thật khi có `virtio_disk_try_submit_read` (H01) và ngắt gọi lại dispatcher (H02). Thứ tự merge đúng: **contract/pool của Hiếu → H01 → L01/L02 → tích hợp G02**. Nếu merge L01 trước H01 thì `main` không build được.

---

### A. Hướng dẫn lệnh tái lập

```bash
# 1. Lấy nhánh của Lợi
git fetch origin week2/loi && git checkout week2/loi

# 2. Chạy self-test MOCK qua runner (tự build với cờ test, ghi kết quả)
make clean
EXTRA_CFLAGS=-DIOQ_SELFTEST python3 tests/runner.py --tag selftest \
    --results-dir results/week02/laptop-Loi

# 3. Hoặc xem trực tiếp output serial
make clean && make EXTRA_CFLAGS=-DIOQ_SELFTEST qemu   # Ctrl-a x để thoát

# 4. Trở về build thường (cần H01 để link được)
make clean && make
```
