# Báo cáo công việc cá nhân Tuần 03 — Nguyễn Văn Hoàng (`20233413`)

- **Đề tài:** `26128` — *Asynchronous `virtio-blk` and I/O schedulers on `xv6-riscv`*
- **Học phần:** `ET4290` — Hệ điều hành (Học kỳ `2026.1`)
- **Nhóm:** Nhóm 3 (`Phạm Trung Hiếu — 20233402`, `Nguyễn Văn Hoàng — 20233413`, `Phạm Quý Lợi — 20233501`)
- **Phạm vi công việc cá nhân Tuần 03 của Nguyễn Văn Hoàng:**
  1. **Task chính (1 mình Hoàng phụ trách — Owner):**
     - `W3-H01` (`PTO-21`): Sửa harness toolchain (`NM = $(TOOLPREFIX)nm`, kiểm tra công cụ trước khi tạo thư mục log) và xác minh lại nhánh `main` sau merge.
     - `W3-H02`: Bổ sung stress READ nhiều producer thực (`fork()`) có kiểm tra dữ liệu đầy đủ `1024 B` trên `virtio-blk` thật.
  2. **Các mục thuộc `PTO-7` do Hoàng phụ trách chính:**
     - `PTO-7 / Q1`: Chốt commit/tag chuẩn của `xv6-riscv` và toolchain cho học kỳ `2026.1`.
     - `PTO-7 / Q7`: Đánh giá khả năng mở rộng kích thước virtqueue (`#define NUM 8` trong `kernel/virtio.h`) để tăng `max_inflight > 2` ở giai đoạn đo hiệu năng.
  3. **Phần đóng góp / phản biện kỹ thuật bắt buộc của Hoàng trong các task dùng chung Tuần 03:**
     - `W3-G01`: Kiểm chứng qui ước rollback `IO_EAGAIN` và qui ước chỉ commit `logical_head` / `direction` / trace sau khi `virtio_disk_try_submit_read() == 0`.
     - `W3-I01`: Kiểm tra §10 (danh mục rà soát vùng nhớ DMA và vòng đời slot `io_req`) trong `docs/week03/lifecycle-review.md`.
     - `W3-I02`: Rà soát phần mô tả pipeline driver, qui ước `max_inflight = 2` (`NUM = 8`, 3 descriptor/request) và phạm vi bằng chứng Tuần 2 trong `docs/week03/proposal.md`.

---

## 1. Tổng quan trạng thái Repository, Jira và các tab làm việc

### 1.1. Trạng thái Repository nhóm (`Asynchronous-virtio-blk-and-IO-Schedulers`)
- **URL:** `https://github.com/HieuPahm-R2/Asynchronous-virtio-blk-and-IO-Schedulers`
- **Thư mục clone tại workspace:** `/home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers`
- **Commit `origin/main` mới nhất khi bắt đầu:** `10de5a06842e329197f31d882b602dcc2c5300c2` (*Merge pull request #7 from `HieuPahm-R2/week3/hieu-contract-lifecycle-proposal`*).
- **Các nhánh trên remote đã kiểm tra (chỉ đọc, không chỉnh sửa remote):**
  - `origin/main` (`10de5a0`): đã merge đầy đủ baseline Tuần 1, Tuần 2 (`PR #1`..`PR #6`) và phần tài liệu/hợp đồng Tuần 3 của Hiếu (`PR #7`).
  - `origin/week3/hieu-contract-lifecycle-proposal` (`8d298c9`): có thêm bản cập nhật nhỏ sau PR #7 trong `docs/week03/`.
  - `origin/week1/hoang-env`, `origin/week2/hoang-pool-test`: các nhánh Tuần 1–2 của Hoàng đã được merge vào `main`.
- **Nhánh làm việc Tuần 3 của Hoàng:** `week3/hoang-toolchain-stress` (tạo từ `origin/main` `10de5a06842e329197f31d882b602dcc2c5300c2`).

### 1.2. Trạng thái bảng Jira (`project = PTO`) và `PTO-7`
- **Danh sách công việc Tuần 3 trên Jira & kế hoạch nhóm (`week03-plan/`):**
  - `PTO-20` (`W3-G01` + `W3-I01` + `W3-I02`): Phụ trách chính bởi Phạm Trung Hiếu — đã hoàn thành trên nhánh của Hiếu và merge qua `PR #7`.
  - `PTO-21` (`W3-H01`): Phụ trách 1 mình bởi **Nguyễn Văn Hoàng** — *Sửa harness toolchain và xác minh bản `main` sau merge*.
  - `W3-H02`: Phụ trách 1 mình bởi **Nguyễn Văn Hoàng** — *Bổ sung stress READ nhiều producer có kiểm dữ liệu*.
  - `W3-L01`, `W3-L02`: Phụ trách bởi Phạm Quý Lợi — *Thiết kế và cài đặt bộ lập lịch `SCAN` và bộ kiểm thử `SCAN`*.
  - `PTO-7` (*Chốt các câu hỏi thiết kế và phạm vi kỹ thuật với GVHD*, chú ý chuỗi phản hồi/cập nhật tại `focusedCommentId=10345`): Theo dõi 7 câu hỏi kỹ thuật (`Q1`..`Q7`), trong đó **Hoàng phụ trách chính `Q1` và `Q7`**.

---

## 2. Chi tiết thực hiện các Task 1 mình Hoàng phụ trách trong Tuần 3

### 2.1. Task `W3-H01` (`PTO-21`) — Sửa harness toolchain và xác minh bản `main` sau merge

#### A. Vấn đề tồn tại từ Tuần 2 cần giải quyết
1. Trong Tuần 2 (`scripts/check-week02-hoang.py` và `Makefile`), công cụ kiểm tra bảng ký hiệu nhị phân được gọi cứng bằng tên `riscv64-unknown-elf-nm` thay vì đi qua `$(TOOLPREFIX)nm`. Khi chạy trên máy Ubuntu/WSL chỉ cài gói `binutils-riscv64-linux-gnu` (`TOOLPREFIX = riscv64-linux-gnu-`), bước kiểm tra rò rỉ hook test trong `kernel/kernel` bị lỗi hoặc phải tạo symlink thủ công trong `~/bin`.
2. Nếu máy thiếu một công cụ trong chuỗi (`make`, `qemu-system-riscv64`, `${TOOLPREFIX}gcc`, `${TOOLPREFIX}nm`, `${TOOLPREFIX}objdump`, `${TOOLPREFIX}ld`), script cũ vẫn tạo thư mục `results/...` trước rồi mới dừng, để lại thư mục log dở dang dễ gây nhầm lẫn khi tổng hợp minh chứng.
3. Sau khi merge các nhánh Tuần 2 và hợp đồng Tuần 3 vào `main`, cần xác minh lại toàn bộ nhánh `main` trên phần cứng ảo `virtio-blk` thật với `repeat = 10` (`CPUS=1` và `CPUS=4`).

#### B. Các bước thực hiện và thay đổi mã nguồn
1. **Bước 1 — Ghi nhận baseline trước khi sửa code và chạy kiểm tra nhanh trên `main` nguyên bản:**
   - Lưu thông tin môi trường trước khi sửa tại [pre-edit-env.txt](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/results/week03/hoang-ubuntu/pre-edit-env.txt) (`HEAD = 10de5a06842e329197f31d882b602dcc2c5300c2`, `.xv6-commit = f780d7850765d74cbdcd1fff4b822d8829f7c9bd`, `riscv64-unknown-elf-gcc 13.2.0`, `QEMU 8.2.2`, `GNU Make 4.3`, `Python 3.12.3`).
   - Chạy kiểm tra nhanh trên `main` chưa chỉnh sửa:
     ```bash
     python3 scripts/check-week02-hoang.py --repeat 1 --hw-only \
       --results-dir results/week03/hoang-ubuntu/main-repeat1-hwonly
     ```
     Kết quả: **PASS** ([summary.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/results/week03/hoang-ubuntu/main-repeat1-hwonly/summary.md)).
2. **Bước 2 — Đồng bộ `TOOLPREFIX` và `NM` trong `Makefile` và `mk/project.mk`:**
   - Trong [Makefile](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/Makefile#L49-L56), bổ sung định nghĩa:
     ```makefile
     NM = $(TOOLPREFIX)nm
     ```
     ngay cạnh `CC`, `AS`, `LD`, `OBJCOPY`, `OBJDUMP`.
   - Trong [mk/project.mk](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/mk/project.mk#L17-L38), bổ sung target hỗ trợ script tự động lấy đúng `TOOLPREFIX` mà `Makefile` đã dò được:
     ```makefile
     print-toolprefix:
             @echo $(TOOLPREFIX)
     ```
     đồng thời cập nhật target `test-week02` dùng `$(PYTHON)`.
3. **Bước 3 — Cập nhật `scripts/check-week02-hoang.py`:**
   - Bổ sung tham số CLI `--toolprefix` và hàm [`resolve_toolprefix()`](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/scripts/check-week02-hoang.py#L46-L90) theo thứ tự ưu tiên:
     1. Tham số `--toolprefix` hoặc biến môi trường `TOOLPREFIX`;
     2. Kết quả `make -s print-toolprefix`;
     3. Tự động dò các tiền tố chuẩn (`riscv64-unknown-elf-`, `riscv64-linux-gnu-`, `riscv64-elf-`) có hỗ trợ `elf64-big`.
   - Bổ sung hàm [`validate_required_tools()`](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/scripts/check-week02-hoang.py#L93-L140) kiểm tra đầy đủ `make`, `qemu-system-riscv64`, `${prefix}gcc`, `${prefix}nm`, `${prefix}objdump`, `${prefix}ld` và khả năng sinh `elf64-big` **trước khi** gọi `outdir.mkdir(parents=True, exist_ok=True)`. Nếu thiếu bất kỳ công cụ nào, script in thông báo lỗi rõ ràng ra `stderr` và thoát ngay với mã lỗi `2`, **tuyệt đối không tạo thư mục kết quả dở dang**.
   - Thay thế lệnh gọi cứng `riscv64-unknown-elf-nm` bằng `${NM}` (`${TOOLPREFIX}nm`) và truyền `TOOLPREFIX=...` nhất quán vào mọi lệnh `make` trong script.
   - Bổ sung thông tin `toolprefix`, `nm_bin`, `gcc_version`, `qemu_version`, `make_version` vào `meta.json` và `summary.md`.
4. **Bước 4 — Xác minh thực nghiệm `W3-H01`:**
   - **Kiểm chứng trường hợp thiếu công cụ (Negative test cho pre-flight check):**
     ```bash
     python3 scripts/check-week02-hoang.py --toolprefix riscv64-nonexistent- \
       --results-dir /tmp/no-partial-dir
     ```
     Kết quả: Thoát với `exit code = 2`, báo thiếu `riscv64-nonexistent-gcc/nm/objdump/ld`, và thư mục `/tmp/no-partial-dir` **không được tạo**.
   - **Chạy xác minh đầy đủ `repeat = 10` trên nhánh `week3/hoang-toolchain-stress`:**
     ```bash
     python3 scripts/check-week02-hoang.py --repeat 10 \
       --results-dir results/week03/hoang-ubuntu/h01-repeat10
     ```
     Kết quả: **PASS tuyệt đối** ([summary.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/results/week03/hoang-ubuntu/h01-repeat10/summary.md), [meta.json](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/results/week03/hoang-ubuntu/h01-repeat10/meta.json)).

---

### 2.2. Task `W3-H02` — Bổ sung stress READ nhiều producer có kiểm dữ liệu

#### A. Mục tiêu kỹ thuật và yêu cầu cô lập
- Trong Tuần 2, bài kiểm thử phần cứng trong `kernel/io_request_test.c` sử dụng `4` tiến trình con gọi `sleep()` trên kênh giả chỉ cho bài test `kill()`/`ORPHAN`, còn bài đọc đa khối (`8` request) được phát tuần tự từ **một** tiến trình duy nhất.
- Yêu cầu của `W3-H02`:
  1. Xây dựng bài kiểm thử **stress READ đa producer thực sự**: dùng nhiều tiến trình user thật (`fork()` trong `user/init.c`) đồng thời gọi vào kernel để phát các yêu cầu `IO_OP_READ` qua `io_req_alloc() -> io_queue_enqueue() -> virtio_disk_try_submit_read() -> io_req_wait() -> io_req_release()`.
  2. Mỗi tiến trình thực hiện nhiều vòng lặp đọc thực tế trên đĩa `fs.img` qua `virtio-blk` DMA và **kiểm tra từng byte trên toàn bộ `1024 B`** của mỗi khối dữ liệu nhận về.
  3. Tạo áp lực thực sự lên `io_req` pool (`N_IO_REQ = 16`) và chuỗi descriptor của `virtio_disk` (`NUM = 8`, `max_inflight = 2`), ghi nhận các bộ đếm `eagain_pool`, `eagain_desc`, `head_reuse`, và kiểm chứng hệ thống thu hồi sạch toàn bộ tài nguyên khi kết thúc (`free_req = 16`, `free_desc = 8`, `queued = inflight = done = error = 0`, `submitted = completed = released`).
  4. Có **đối chứng âm (negative control)**: làm hỏng đúng `1 byte` của fixture trên `fs.img` và chứng minh bộ kiểm tra `1024 B` phát hiện ngay lỗi sai lệch dữ liệu (`EXPECTED_FAIL`).
  5. **Không sửa đổi** các tệp lõi dùng chung (`kernel/io_request.h`, `kernel/io_request.c`, `kernel/io_queue.c`, `kernel/virtio_disk.c`) để tránh xung đột với nhánh `SCAN` của Lợi; toàn bộ mã kiểm thử phải được bật/tắt bằng cờ biên dịch riêng `-DIO_STRESS_SELFTEST` và không để lại bất kỳ ký hiệu test nào trong bản build production.

#### B. Thiết kế và chi tiết cài đặt
1. **Mô-đun kiểm thử trong kernel — [kernel/io_stress_test.c](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/kernel/io_stress_test.c):**
   - Chỉ sinh mã khi biên dịch với cờ `-DIO_STRESS_SELFTEST`.
   - Sử dụng vùng đệm staging tĩnh trong BSS (`stress_worker_buf[4][8][1024]`, căn chỉnh 8 byte) để tuân thủ nghiêm ngặt hợp đồng vùng nhớ DMA (tránh đặt vùng đệm DMA trên kernel stack của tiến trình).
   - Chuẩn bị `8` khối dữ liệu kiểm thử trên đĩa (`blockno = 700..707`), mỗi khối `1024 B` chứa mẫu byte xác định theo hàm băm phụ thuộc cả chỉ số khối `slot` và vị trí byte `off` (`0..1023`):
     ```c
     expected_fixture_byte(slot, off) = ((slot * 53 + 19) ^ ((off * 97 + (off >> 3) * 13) & 0xff) ^ (slot << 4)) & 0xff
     ```
     Nếu bất kỳ byte nào trong `1024 B` bị đọc lệch, trộn chéo giữa các khối (`blockno` sai), hoặc DMA ghi thiếu, phép so sánh sẽ phát hiện tức thì kèm vị trí byte lỗi đầu tiên (`mismatch_off`, `mismatch_exp`, `mismatch_got`).
   - Hỗ trợ các chế độ gọi từ `sys_io_selftest(int op)` (khi bật `-DIO_STRESS_SELFTEST`):
     - `op == -1`: Chuẩn bị `8` khối fixture `700..707` và kiểm tra đọc xác nhận ban đầu (`1024 B`/khối).
     - `op == 0..3`: Tiến trình worker `w` thực thi `15` vòng × `8` request/vòng = **`120` yêu cầu DMA READ thực tế** (`4` worker × `120` = **`480` DMA READs** mỗi lần boot).
       - Trong mỗi vòng, cả `4` worker đồng bộ tại một rào chắn quay vòng (`stress_round_barrier`) để cùng lúc đẩy `4 × 8 = 32` yêu cầu vào hệ thống (vượt gấp đôi `N_IO_REQ = 16` và gấp `16` lần `max_inflight = 2`).
       - Từ vòng `0..13`, worker giữ các slot `IO_REQ_DONE` cho tới cuối đợt rồi mới thu hồi (`io_req_release`), ép hệ thống rơi vào trạng thái cạn pool (`io_req_alloc() == 0`, tăng `eagain_pool`) và phải xử lý thoái lui an toàn + thử lại.
       - Ở vòng `14` (vòng cuối), mỗi worker giải phóng slot ngay sau khi `io_req_wait()` hoàn tất để chứng minh đường chạy bình thường không cần giữ slot lâu.
     - `op == -2`: Sau khi cả `4` tiến trình worker kết thúc (`wait()`), tiến trình cha kiểm tra toàn cục:
       - Toàn bộ `4` worker đều hoàn thành đủ `120/120` khối, `verified_bytes == 491520` (`480 × 1024 B`), `mismatch == 0`.
       - Cả `16/16` slot trong `io_req` pool về trạng thái `IO_REQ_FREE`, `queued == inflight == done == error == 0`.
       - Toàn bộ `8/8` descriptor trong `virtio_disk` được trả về `free_desc == 8`.
       - Bất biến vòng đời: `submitted == completed == released == 480`, `head_reuse > 0`.
2. **Điểm nối điều phối — [kernel/io_request_test.c](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/kernel/io_request_test.c#L1069-L1086) và [user/init.c](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/user/init.c#L26-L56):**
   - Trong `kernel/io_request_test.c`, hàm `sys_io_selftest()` giữ nguyên nhánh `#ifdef IO_SELFTEST` cho bộ test Tuần 2 và thêm nhánh `#elif defined(IO_STRESS_SELFTEST)` chuyển tiếp tham số `op` sang `io_stress_selftest(op)`.
   - Trong `user/init.c`, nhánh `#elif defined(IO_STRESS_SELFTEST)` gọi `io_selftest(-1)`, sau đó `fork()` 4 tiến trình con thực sự gọi `io_selftest(w)` (`w = 0..3`), chờ đủ 4 tiến trình bằng `wait()`, rồi gọi `io_selftest(-2)`.
3. **Script tự động hóa kiểm thử — [scripts/check-week03-stress.py](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/scripts/check-week03-stress.py) và target `make test-week03-stress`:**
   - Tự động kiểm tra đầy đủ công cụ (`make`, `qemu-system-riscv64`, `${TOOLPREFIX}gcc`, `${TOOLPREFIX}nm`, `${TOOLPREFIX}objdump`, `${TOOLPREFIX}ld`) **trước khi** tạo thư mục `results/...`.
   - Build image với `CFLAGS_EXTRA="-DIO_STRESS_SELFTEST"` và chạy lặp `repeat` lần trên `CPUS=1` và `CPUS=4`.
   - Phân tích log từng lần boot để kiểm chứng:
     - Có đủ 4 worker `w=0..3` với 4 `pid` khác nhau cùng chạy và báo `PASS`;
     - `verified_bytes == 491520`, `mismatch == 0`;
     - `free_req == 16`, `free_desc == 8`, `queued == inflight == done == error == 0`, `submitted == completed == released == 480`;
     - `eagain_pool > 0`, `head_reuse > 0`, và trên `CPUS=4` có `eagain_desc > 0`.
   - Chạy **đối chứng âm (`negative-corrupt-stress-fixture`)**: lật `1 byte` tại offset `511` của khối `703` trên bản sao `fs.img` và xác nhận kernel báo `[IO_STRESS:FAIL] ... 1024-byte fixture pattern` (`EXPECTED_FAIL`).
   - Cuối cùng khôi phục bản build production (`make clean && make kernel/kernel fs.img`), dùng `${TOOLPREFIX}nm` kiểm tra không còn bất kỳ ký hiệu `io_stress_*` hay `io_selftest_*` nào trong `kernel/kernel`, và chạy smoke boot xác nhận máy ảo lên tới `init: starting sh`.

---

## 3. Thực hiện và Rà soát các mục trong `PTO-7` và các Task phối hợp Tuần 3

### 3.1. Các mục thuộc `PTO-7` do Hoàng phụ trách chính (`Q1` và `Q7`)

| Mã câu hỏi | Nội dung kỹ thuật trong `PTO-7` | Kết quả rà soát & thực trạng trong mã nguồn | Trạng thái & Quyết định thực thi Tuần 3 |
| :--- | :--- | :--- | :--- |
| **`PTO-7 / Q1`** | Chốt commit/tag chuẩn của `xv6-riscv` và phiên bản toolchain chuẩn cho học kỳ `2026.1`. | - File [.xv6-commit](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/.xv6-commit) đang ghim tại commit `f780d7850765d74cbdcd1fff4b822d8829f7c9bd` (ngày `2026-10-15` của upstream `mit-pdos/xv6-riscv`), đã bao gồm `sleep_prepare()` trong `kernel/proc.c` và cờ `-fno-delete-null-pointer-checks`.<br>- Cả hai họ toolchain `riscv64-unknown-elf-` (`GCC 13.2.0`) và `riscv64-linux-gnu-` đều đã được hỗ trợ tự động trong `Makefile` và các script kiểm thử (`W3-H01`). | **`PENDING` phản hồi GVHD.**<br>Theo đúng ràng buộc của `W3-H01`, nhóm **giữ nguyên** `.xv6-commit = f780d7850765d74cbdcd1fff4b822d8829f7c9bd` trong Tuần 3 để bảo toàn tính tái lập. |
| **`PTO-7 / Q7`** | Có được phép tăng `#define NUM 8` trong `kernel/virtio.h` (ví dụ lên `16` hoặc `32`) để mở rộng `max_inflight > 2` ở giai đoạn đo hiệu năng không? | - Trong [kernel/virtio.h](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/kernel/virtio.h#L47), `#define NUM 8` là kích thước virtqueue mặc định của xv6.<br>- Mỗi yêu cầu khối trong [kernel/virtio_disk.c](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/kernel/virtio_disk.c#L140-L157) cấp phát chuỗi **3 descriptor** (`alloc3_desc`: header 16B + data 1024B + status 1B). Do đó số chuỗi tối đa đồng thời trên thiết bị là $\lfloor 8 / 3 \rfloor = 2$ (`max_inflight = 2`), dư 2 descriptor lẻ.<br>- Toàn bộ mảng trạng thái trong `virtio_disk.c` (`desc`, `avail`, `used`, `free[NUM]`, `info[NUM]`, `last_async[NUM]`, `ops[NUM]`) đều tham số hóa theo `NUM`. Về mặt kỹ thuật MMIO legacy của QEMU, nâng `NUM` lên lũy thừa của 2 (`16` $\rightarrow$ `max_inflight = 5`, hoặc `32` $\rightarrow$ `max_inflight = 10`) vẫn nằm gọn trong 1 trang `4096 B` và không đổi giao thức.<br>- Tuy nhiên, với `NUM = 8` (`max_inflight = 2`) và `N_IO_REQ = 16`, khi có nhiều tiến trình phát I/O đồng thời (như trong bài stress `W3-H02`), luôn có tới `14` request nằm chờ trong `io_queue`, đủ để chứng minh khác biệt thứ tự phục vụ giữa `FIFO` và `SCAN`. | **`PENDING` phản hồi GVHD.**<br>Theo quyết định `S4`/`D20` trong `docs/week03/interface.md`, Tuần 3 **giữ nguyên `NUM = 8` (`max_inflight = 2`)**, không sửa `kernel/virtio.h`. |

### 3.2. Kết quả rà soát kỹ thuật của Hoàng đối với `W3-G01`, `W3-I01`, `W3-I02`

1. **Rà soát `W3-G01` ([docs/week03/interface.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/docs/week03/interface.md) & [kernel/io_request.h](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/kernel/io_request.h)):**
   - Đã kiểm chứng qui ước `IO_EAGAIN (-11)` khi `virtio_disk_try_submit_read(r)` không lấy đủ 3 descriptor: hàm giải phóng ngay các descriptor vừa cấp phát dở (nếu có), giữ nguyên `r->state == IO_REQ_QUEUED`, và trả `-11` dưới cùng `io_lock`.
   - Đã kiểm chứng yêu cầu thiết kế cho `SCAN`: `io_queue_select_next_locked()` chỉ chọn ứng viên và gỡ tạm khỏi danh sách chờ; nếu `try_submit` trả `IO_EAGAIN`, `io_queue_requeue_front_locked()` trả request về lại hàng đợi và **không được cập nhật `logical_head`, `direction` hay ghi nhận thứ tự dispatch** trước khi `try_submit == 0`.
2. **Rà soát `W3-I01` ([docs/week03/lifecycle-review.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/docs/week03/lifecycle-review.md) — Mục §10):**
   - Đã đối chiếu toàn bộ 7 mục trong bảng kiểm vùng nhớ DMA và vòng đời slot `io_req` (§10.1) với mã nguồn thực tế trong `kernel/io_request.c` và `kernel/virtio_disk.c`:
     1. `io_req_release()` panic ngay nếu gọi khi `state == IO_REQ_QUEUED` hoặc `IO_REQ_INFLIGHT`.
     2. Các bài selftest (`io_request_test.c` và `io_stress_test.c`) đều dùng vùng đệm tĩnh trong BSS, tuyệt đối không trỏ DMA vào biến cục bộ trên stack của tiến trình có thể bị `kill()`.
     3. Đường hoàn tất ngắt `virtio_disk_intr()` phân biệt rạch ròi `IO_HEAD_SYNC` và `IO_HEAD_ASYNC` qua `disk.last_async[id]` và xóa `disk.info[id].req = 0` trước khi gọi `io_req_complete()`.
     4. Khi tiến trình chờ bị `kill()` (`p->killed != 0`), `io_req_wait()` đánh dấu `r->flags |= IO_REQ_FLAG_ORPHAN` dưới `io_lock`: nếu đang `QUEUED` thì gỡ khỏi `io_queue` và giải phóng ngay; nếu đang `INFLIGHT` thì giữ nguyên slot cho tới khi IRQ hoàn tất mới tự thu hồi trong `io_req_complete()` và vẫn tăng `released++`.
     5. Thứ tự khóa `io_lock -> p->lock` được giữ đúng qua `sleep_prepare(r, &io_lock)` và `wakeup_RequestWaiters()`.
3. **Rà soát `W3-I02` ([docs/week03/proposal.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/docs/week03/proposal.md)):**
   - Xác nhận phần mô tả kiến trúc 3 tầng (`io_req` pool $\rightarrow$ `io_queue` scheduler $\rightarrow$ `virtio_disk` non-blocking submit / IRQ reap), giải thích `max_inflight = 2` (`NUM = 8`, 3 descriptor/request) và phạm vi bằng chứng thực nghiệm Tuần 2 được trình bày chính xác, trung thực, không phóng đại kết quả.

---

## 4. Tổng hợp các thay đổi trên mã nguồn chung của nhóm

### 4.1. Cam kết an toàn kiến trúc (Zero Core Runtime Touch)
Để bảo đảm không gây xung đột merge với nhánh cài đặt bộ lập lịch `SCAN` của Lợi (`W3-L01`/`W3-L02`) và giữ nguyên hợp đồng của Hiếu (`W3-G01`), **không có bất kỳ thay đổi nào** trên 4 tệp lõi thời gian chạy:
- `kernel/io_request.h`: **Không sửa** (`0` dòng thay đổi).
- `kernel/io_request.c`: **Không sửa** (`0` dòng thay đổi).
- `kernel/io_queue.c`: **Không sửa** (`0` dòng thay đổi).
- `kernel/virtio_disk.c`: **Không sửa** (`0` dòng thay đổi).

### 4.2. Bảng chi tiết các tệp đã sửa đổi / bổ sung trên nhánh `week3/hoang-toolchain-stress`

| Tệp | Loại thay đổi | Tóm tắt nội dung thay đổi |
| :--- | :---: | :--- |
| [Makefile](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/Makefile) | Sửa đổi (`+7` dòng) | Thêm `NM = $(TOOLPREFIX)nm`; nối thêm `$K/io_stress_test.o` vào `OBJS` khi `CFLAGS_EXTRA` có `-DIO_STRESS_SELFTEST`. |
| [mk/project.mk](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/mk/project.mk) | Sửa đổi (`+10/-2` dòng) | Thêm `.PHONY: print-toolprefix test-week03-stress`, target `print-toolprefix` in `$(TOOLPREFIX)`, dùng `$(PYTHON)` cho `test-week02`, và thêm target `test-week03-stress`. |
| [scripts/check-week02-hoang.py](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/scripts/check-week02-hoang.py) | Sửa đổi (`+198/-62` dòng) | Tự động dò `TOOLPREFIX` và `NM = $(TOOLPREFIX)nm`; kiểm tra toàn bộ binary (`make`, `qemu-system-riscv64`, `gcc`, `nm`, `objdump`, `ld` + `elf64-big`) **trước khi** tạo thư mục kết quả; truyền `TOOLPREFIX` nhất quán cho mọi lệnh build/test. |
| [kernel/io_stress_test.c](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/kernel/io_stress_test.c) | Thêm mới (`480` dòng) | Cài đặt bài kiểm thử stress READ 4 tiến trình producer đồng thời (`4 × 120 = 480` DMA READs/boot) dưới cờ `#ifdef IO_STRESS_SELFTEST`, kiểm tra từng byte `1024 B`/khối và kiểm tra thu hồi tài nguyên toàn cục. |
| [kernel/io_request_test.c](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/kernel/io_request_test.c) | Sửa đổi (`+8` dòng) | Khai báo `extern int io_stress_selftest(int op)` và điều phối `sys_io_selftest()` sang `io_stress_selftest(op)` khi biên dịch với `#elif defined(IO_STRESS_SELFTEST)`. |
| [user/init.c](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/user/init.c) | Sửa đổi (`+30` dòng) | Thêm nhánh `#elif defined(IO_STRESS_SELFTEST)`: gọi `io_selftest(-1)`, `fork()` 4 tiến trình con chạy `io_selftest(0..3)`, `wait()` cả 4 tiến trình và gọi `io_selftest(-2)`. |
| [scripts/check-week03-stress.py](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/scripts/check-week03-stress.py) | Thêm mới (`630` dòng) | Harness tự động cho `W3-H02`: kiểm tra toolchain trước khi tạo thư mục log, chạy lặp `CPUS=1` và `CPUS=4`, chạy đối chứng âm làm hỏng 1 byte trên `fs.img`, khôi phục bản build production và kiểm tra bảng ký hiệu `nm`. |
| [docs/testing.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/docs/testing.md) | Sửa đổi (`+24` dòng) | Bổ sung tài liệu hướng dẫn chạy và giải thích cơ chế kiểm thử của `W3-H01` và `W3-H02`. |

---

## 5. Kết quả kiểm thử và Minh chứng thực nghiệm

> **Qui ước báo cáo trung thực:**
> - Phân biệt rõ **số lần chạy lặp (`repeat` boots)** với **số nhóm kịch bản (`case groups`)** trong mỗi lần boot.
> - Phân biệt rõ **bài kiểm thử phần cứng `virtio-blk` thật trong QEMU** với **bài kiểm thử mock/timer mô phỏng trên host**.
> - Các bài đối chứng âm (cố tình làm hỏng `1 byte` dữ liệu trên đĩa để kiểm tra khả năng bắt lỗi của assertion) được ghi nhận riêng là **`EXPECTED_FAIL`**.

### 5.1. Tổng hợp các đợt chạy kiểm thử đã thực hiện

| Đợt kiểm thử | Lệnh thực thi | Cấu hình & Phạm vi | Kết quả | Thư mục lưu trữ minh chứng |
| :--- | :--- | :--- | :---: | :--- |
| **1. Baseline `main` trước khi sửa code** | `python3 scripts/check-week02-hoang.py --repeat 1 --hw-only --results-dir results/week03/hoang-ubuntu/main-repeat1-hwonly` | `1` boot `CPUS=1` + `1` boot `CPUS=4` (`15` nhóm kịch bản/boot) + `1` đối chứng âm + khôi phục production | **PASS** (`2/2` boots, `1` `EXPECTED_FAIL`) | [main-repeat1-hwonly/summary.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/results/week03/hoang-ubuntu/main-repeat1-hwonly/summary.md) |
| **2. Kiểm tra thiếu công cụ (`W3-H01` guard)** | `python3 scripts/check-week02-hoang.py --toolprefix riscv64-nonexistent- --results-dir /tmp/no-partial-dir` | Kiểm tra thoát sớm trước khi tạo thư mục log khi thiếu binary toolchain | **EXPECTED EXIT (`rc=2`)**, không tạo `/tmp/no-partial-dir` | Xác nhận trực tiếp trên CLI |
| **3. Xác minh đầy đủ `W3-H01` (`repeat = 10`)** | `python3 scripts/check-week02-hoang.py --repeat 10 --results-dir results/week03/hoang-ubuntu/h01-repeat10` | `10` boots `CPUS=1` + `10` boots `CPUS=4` (`20` boots phần cứng × `15` kịch bản/boot) + `1` đối chứng âm + `4` bộ test mock host + kiểm tra `nm` production | **PASS** (`20/20` boots, `4/4` mock, `1` `EXPECTED_FAIL`) | [h01-repeat10/summary.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/results/week03/hoang-ubuntu/h01-repeat10/summary.md) |
| **4. Xác minh đầy đủ `W3-H02` (`repeat = 5`)** | `python3 scripts/check-week03-stress.py --repeat 5 --results-dir results/week03/stress/hoang-ubuntu-repeat5` | `5` boots `CPUS=1` + `5` boots `CPUS=4` (`10` boots × `4` tiến trình producer × `120` DMA READs = **`4,800` DMA READs** kiểm đủ `1024 B`) + `1` đối chứng âm lật `1 byte` + kiểm tra `nm` & smoke boot production | **PASS** (`10/10` boots, `4,800/4,800` khối `1024 B`, `1` `EXPECTED_FAIL`) | [hoang-ubuntu-repeat5/summary.md](file:///home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers/results/week03/stress/hoang-ubuntu-repeat5/summary.md) |
| **5. Kiểm tra định dạng văn bản & smoke test chuẩn** | `git diff --check && make check-text && make test-fast` | `350` tệp UTF-8 sạch + `boot-smoke (CPUS=1)` + `shell-fs-cpus3 (CPUS=3)` trên bản build production | **PASS** (`2/2` cases) | `results/local/` |

### 5.2. Chi tiết số liệu thực nghiệm của bài kiểm thử `W3-H02` (`results/week03/stress/hoang-ubuntu-repeat5`)

| Chỉ số / Bất biến kiểm chứng | Kết quả trên `CPUS=1` (`5` lần boot) | Kết quả trên `CPUS=4` (`5` lần boot) | Ý nghĩa kỹ thuật |
| :--- | :---: | :---: | :--- |
| Số tiến trình producer thực (`fork()`) mỗi lần boot | `4` (`pid = 2, 3, 4, 5`) | `4` (`pid = 2, 3, 4, 5`) | 4 tiến trình user độc lập cùng phát yêu cầu đọc qua syscall vào kernel. |
| Số vòng × số yêu cầu mỗi worker | `15 × 8 = 120` READs/worker | `15 × 8 = 120` READs/worker | Tổng cộng `480` yêu cầu DMA READ thực tế mỗi lần boot (`2,400` READs mỗi cấu hình CPU). |
| Tổng số byte dữ liệu DMA được so khớp từng byte | `491,520 B` / boot (`100%` khớp) | `491,520 B` / boot (`100%` khớp) | Mỗi khối được kiểm đủ `1024/1024 B` theo mẫu phụ thuộc `(blockno, offset)`. |
| Số lỗi sai lệch dữ liệu (`mismatch`) | `0` | `0` | Không có hiện tượng trộn vùng đệm DMA, đọc nhầm block hoặc hoàn tất sớm trước khi DMA xong. |
| Số lần chạm ngưỡng cạn `io_req` pool (`eagain_pool`) | `116` lần / boot | `234` lần / boot | Khi 4 worker giữ slot qua các đợt, pool `16` slot cạn và cơ chế thoái lui + thử lại hoạt động đúng. |
| Số lần chạm ngưỡng hết chuỗi 3 descriptor (`eagain_desc`) | `0` lần / boot | `116` lần / boot | Trên `CPUS=4`, các hart đẩy song song vào `virtio_disk` làm chạm giới hạn `max_inflight = 2` (`IO_EAGAIN`) và rollback an toàn về `io_queue`. |
| Số lần tái sử dụng chỉ số `head` descriptor (`head_reuse`) | `451` lần / boot | `433..438` lần / boot | Chỉ số `head` của chuỗi 3 descriptor được giải phóng và tái sử dụng an toàn qua hàng trăm chu kỳ IRQ. |
| Trạng thái khi kết thúc (`global_drain`) | `free_req=16`, `free_desc=8`, `queued=inflight=done=error=0` | `free_req=16`, `free_desc=8`, `queued=inflight=done=error=0` | Không rò rỉ bất kỳ slot `io_req` hay descriptor `virtio` nào sau khi 4 tiến trình hoàn tất. |
| Bất biến vòng đời `submitted == completed == released` | `480 == 480 == 480` | `480 == 480 == 480` | Mọi request đã phát xuống thiết bị đều hoàn tất qua ngắt và được thu hồi đúng 1 lần. |
| Đối chứng âm (`negative-corrupt-stress-fixture`) | **`EXPECTED_FAIL`** (bắt đúng byte bị lật ở `slot=3, off=511`) | — | Chứng minh bộ kiểm tra `1024 B` thực sự đọc dữ liệu từ `fs.img` và phát hiện ngay sai lệch `1 byte`. |
| Kiểm tra bảng ký hiệu bản build production (`nm`) | `0` ký hiệu test (`PASS`) | `0` ký hiệu test (`PASS`) | Bản build mặc định hoàn toàn sạch, không chứa mã hay vùng đệm của `IO_STRESS_SELFTEST` / `IO_SELFTEST`. |

---

## 6. Các mục còn `PENDING` (Báo cáo trung thực theo qui ước nhóm)

1. **Chạy đối chiếu chéo với `TOOLPREFIX=riscv64-linux-gnu-` trên máy của Phạm Quý Lợi:**
   - Trên máy Ubuntu hiện tại của Hoàng, toolchain cài sẵn là `riscv64-unknown-elf-` (`GCC 13.2.0`); gộp kiểm tra `TOOLPREFIX` tự động và kiểm tra thoát sớm khi thiếu công cụ đã hoàn tất và PASS.
   - Việc chạy lại `python3 scripts/check-week02-hoang.py --repeat 1` và `python3 scripts/check-week03-stress.py --repeat 1` trên máy của Lợi (nơi cài `riscv64-linux-gnu-`) được ghi nhận trạng thái **`PENDING`** để Lợi chạy xác nhận khi đồng bộ nhánh Tuần 3.
2. **Phản hồi chính thức của GVHD trên `PTO-7` (`Q1`..`Q7`):**
   - Các câu hỏi trong `PTO-7` (bao gồm `Q1` về commit/tag chuẩn và `Q7` về mở rộng `NUM > 8`) đang ở trạng thái **`PENDING`** chờ ý kiến phản hồi của giảng viên hướng dẫn; trong toàn bộ Tuần 3, nhóm giữ nguyên `.xv6-commit = f780d7850765d74cbdcd1fff4b822d8829f7c9bd` và `NUM = 8` (`max_inflight = 2`).

---

## 7. Hướng dẫn tái lập nhanh

```bash
# 1. Di chuyển vào thư mục repository
cd /home/ubuntu/Documents/Codex/2026-10-23/t/outputs/Asynchronous-virtio-blk-and-IO-Schedulers

# 2. Chạy xác minh W3-H01 (repeat = 10, gồm cả CPUS=1, CPUS=4, negative control, mock tests và kiểm tra nm)
python3 scripts/check-week02-hoang.py --repeat 10 \
  --results-dir results/week03/hoang-ubuntu/h01-repeat10

# 3. Chạy xác minh W3-H02 (repeat = 5, 4 tiến trình producer × 120 DMA READs = 480 READs/boot, kiểm đủ 1024 B)
python3 scripts/check-week03-stress.py --repeat 5 \
  --results-dir results/week03/stress/hoang-ubuntu-repeat5
# Hoặc dùng target rút gọn:
make test-week03-stress

# 4. Kiểm tra định dạng văn bản và smoke test trên bản build production
git diff --check
make check-text
make test-fast
```
