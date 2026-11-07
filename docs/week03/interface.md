# W3-G01 — Contract SCAN, phạm vi proposal và điều phối tuần 3

> **Mã công việc:** W3-G01 (Jira PTO-20) — *Chốt contract SCAN và phạm vi proposal tuần 3*.
> **Người thực hiện:** Phạm Trung Hiếu (MSSV: 20233402).
> **Nhánh làm việc:** `week3/hieu-contract-lifecycle-proposal`, tách từ `origin/main`.
> **Base revision:** `49557bf671edb5ee4ccf6a2c3c452d32fd1f411e` (2026-11-04, merge PR #6;
> PR #5 `83745b6` là bản tích hợp READ thật của tuần 2).
> **Pin xv6:** `f780d7850765d74cbdcd1fff4b822d8829f7c9bd` (tạm thời, chờ GV xác nhận tag — PTO-7/Q1).
> **Reviewers:** Nguyễn Văn Hoàng (20233413), Phạm Quý Lợi (20233501) — **PENDING** (chưa có xác nhận trên revision này).
> **Nguồn sự thật:** semantics trong tài liệu này + khai báo kiểu/prototype tại
> [`kernel/io_request.h`](../../kernel/io_request.h); contract tuần 2 tại
> [`docs/week02/interface.md`](../week02/interface.md) vẫn còn hiệu lực trừ các điểm được thay thế ở §3.
> **Snapshot:** 2026-11-07. Kế hoạch tuần 3 lập ngày 07/11/2026; hạn chốt 08/11/2026.

---

## 1. Mục tiêu card và quan hệ với tuần 2

Tuần 2 đã merge lên `main` một nguyên mẫu **READ một block, FCFS, kernel C API**:
request pool 16 slot trong BSS, handle `(id, gen)`, staging buffer do pool sở hữu,
một miền khóa `io_lock`, `aio_read_submit/poll/wait/data/release`, queue FCFS
theo `enqueue_seq`, driver `try-submit` 3 descriptor và ngắt `virtio_disk_intr`
thu hồi chain ASYNC
([`kernel/io_request.c`](../../kernel/io_request.c), [`kernel/io_queue.c`](../../kernel/io_queue.c),
[`kernel/virtio_disk.c`](../../kernel/virtio_disk.c), [`docs/week02/interface.md`](../week02/interface.md)).

Tuần 3 chuyển từ FCFS sang **SCAN logic có contract và oracle**. Ba module vẫn được
viết song song (Lợi: queue/policy; Hoàng: driver/harness/tích hợp; Hiếu: contract,
lifecycle, proposal), nên card này phải chốt trước khi L01 sửa queue:

1. **SCAN hay LOOK**, và câu trả lời nào của GV còn Pending;
2. **tọa độ block**, miền hợp lệ, đầu logic và chiều quét;
3. **thời điểm commit** head/direction và hành vi khi `IO_EAGAIN`;
4. **sự kiện biên logic**, đảo chiều, tie-break, queue rỗng, request tại head;
5. **trace/oracle** và cách xuất log ngoài `io_lock`/IRQ;
6. **phạm vi proposal** để I02 không mô tả quá mức phần đã có.

Không chốt contract trước thì L01 (queue), L02 (oracle) và I02 (proposal) sẽ hiểu
khác nhau về cùng một thuật toán, đúng loại mâu thuẫn đã xảy ra ở tuần 1
(buffer ownership) và được xử lý ở W2-G01.

## 2. Phạm vi tuần 3 (chốt)

### 2.1 Trong phạm vi

| Mã | Hạng mục | Giá trị chốt cho tuần 3 |
| :---: | :--- | :--- |
| S1 | Thao tác I/O | Chỉ **READ đúng 1 block**, `BSIZE = 1024` byte, trên **một thiết bị** `ROOTDEV`; WRITE và log giữ nguyên đường đồng bộ của xv6. |
| S2 | Đơn vị địa chỉ | API/scheduler dùng **`blockno`**; miền hợp lệ `0 .. FSSIZE-1` (`FSSIZE = 2000`). Chuyển sang sector (`blockno * 2`) chỉ một lần trong driver. |
| S3 | Tài nguyên phần mềm | Pool **16 slot** (`IO_NREQ = 16`), staging buffer 1024 B nằm trong `struct io_request`, không `kalloc` trên đường async. |
| S4 | Tài nguyên phần cứng | Virtqueue **`NUM = 8`** descriptor, mỗi request 3 descriptor (header + data + status) ⇒ tối đa **2 chain** cùng lúc. |
| S5 | Khóa | Đúng **một miền khóa** `io_lock` = `disk.vdisk_lock`; không khóa thứ hai, không acquire lồng, không ngủ khi giữ khóa. |
| S6 | Giao diện | **Kernel C API** như tuần 2 (`aio_read_submit`, `aio_poll`, `aio_wait`, `aio_data`, `aio_release`, `io_get_stats`). **Chưa** thêm syscall cho ứng dụng. |
| S7 | Policy | **FCFS là mặc định của production**; SCAN logic được chọn **ở boot/test config** (build test), chưa đổi policy khi đang có tải. |
| S8 | Trace/oracle | Trace dispatch + biên logic **hữu hạn**, sao chép dưới khóa rồi in ngoài `io_lock`/IRQ; oracle Python độc lập (L02); tối thiểu 8 nhóm test. |
| S9 | Kiểm chứng | FCFS regression giữ nguyên; SCAN mock CPU1/4; READ thật FCFS/SCAN CPU1/4 ở G02; production restore và smoke PASS. |

### 2.2 Ngoài phạm vi tuần 3 (không hứa, không tuyên bố đã làm)

| Hạng mục | Trạng thái tuần 3 |
| :--- | :--- |
| Syscall/user API, chương trình minh hoạ cho ứng dụng | **Chưa** — phụ thuộc PTO-7/Q3 của GV |
| Async WRITE, thay thế `bread()`/`bwrite()` | **Chưa** — WRITE/log giữ đồng bộ |
| Coherence với buffer cache khi cùng block vừa đọc vừa ghi | **Chưa giải quyết** — chỉ đọc fixture read-only đã xác nhận bất biến |
| Merge READ (gom block), deadline scheduler | **Chưa** — thiết kế/backlog tuần 4 trở đi |
| Đổi policy khi hệ thống đang có tải | **Chưa** — tuần 4 |
| Kill/cancel đầy đủ cho request async | **Chỉ thiết kế** ở W3-I01; **chưa** triển khai, **chưa** test |
| Đo seek vật lý, tăng tốc I/O, benchmark | **Không** — QEMU không mô phỏng chuyển đầu từ vật lý |
| CI tự động | **Không** — workflow đang bị comment; không coi là bằng chứng |
| Xác nhận của giảng viên cho SCAN/LOOK, merge, rubric | **Pending** — xem §8 |

## 3. Quyết định tuần 3 (D11 – D20)

Các quyết định D1–D10 của tuần 2 vẫn giữ nguyên. Dưới đây là phần bổ sung/thay thế
cho scheduler tuần 3.

### D11 — Dùng SCAN logic tạm thời; LOOK là phương án thay thế

- **Quyết định:** Tuần 3 triển khai **SCAN logic** trên miền `blockno` của filesystem
  MVP: chọn request gần `head` nhất theo chiều hiện tại; khi **không còn ứng viên
  theo chiều hiện tại** thì ghi **sự kiện biên logic** tại đầu mút của miền
  (`0` hoặc `FSSIZE-1`) rồi đảo chiều; **không phát READ giả** tới biên.
- **LOOK là phương án thay thế:** nếu GV yêu cầu LOOK thì thay bước "ghi sự kiện
  biên rồi đảo chiều" bằng "đảo chiều ngay tại request xa nhất trong chiều hiện tại".
  Phần chọn request, tie-break, commit, EAGAIN giữ nguyên.
- **Lý do chọn SCAN tạm:** plan tuần 3 yêu cầu kiểm chứng SCAN; oracle phải phân
  biệt SCAN/LOOK bằng **boundary event**, không chỉ bằng dãy block. Nhiều queue tĩnh
  cho cùng thứ tự block ở SCAN và LOOK, nên nếu chỉ so thứ tự block thì không chứng
  minh được thuật toán.
- **Trạng thái GV:** **PENDING** (PTO-7/Q4). Không coi giả định là xác nhận của GV;
  toàn bộ tài liệu/proposal ghi rõ "SCAN logic tạm thời, chờ xác nhận".
- **Không tuyên bố:** đây là điều phối **phần mềm trên QEMU**; không đo/khẳng định
  chuyển đầu từ vật lý của đĩa.

### D12 — Tọa độ `blockno`, biên logic theo miền filesystem MVP

- **Quyết định:** `head`, `direction`, candidate, trace đều dùng `blockno`.
  Miền hợp lệ `[0, FSSIZE-1] = [0, 1999]`. Biên logic trên = `FSSIZE-1`,
  biên logic dưới = `0`. Không lưu `sector` trong request/queue.
- **Quy ước:** `FSSIZE` là capacity của **filesystem MVP** trong `fs.img`, không
  phải capacity vật lý của mọi thiết bị. Nếu mở rộng thiết bị/ảnh đĩa, contract phải
  chốt lại nguồn capacity trước khi dùng SCAN.
- **Loại bỏ:** dùng sector làm đơn vị scheduler (dễ nhân đôi địa chỉ) hoặc dùng
  capacity vật lý không kiểm chứng được trong QEMU.

### D13 — Trạng thái đầu logic lúc khởi tạo

- **Quyết định:** `io_queue_init()` (gọi từ `io_init()` lúc boot) đặt:
  - `logical_head = 0`
  - `direction = IO_DIR_UP` (`+1`)
  - `policy = IO_POLICY_FCFS` (FCFS không dùng head/direction)
  - `boundary_events = 0`, `trace_count = 0`
- Queue rỗng **không** thay đổi `logical_head`/`direction`; request mới được chọn theo
  trạng thái đang lưu.
- **Lý do:** trạng thái khởi tạo tất định để oracle tái lập được; vị trí 0/chiều tăng
  là quy ước đơn giản, không phụ thuộc lịch sử I/O trước đó.

### D14 — Quy tắc chọn request (selection)

Với queue `QUEUED` khác rỗng và policy `SCAN`, dưới `io_lock`:

1. **Ưu tiên request tại head:** nếu tồn tại request có `blockno == logical_head`,
   chọn request đó; nếu nhiều request cùng block, chọn `enqueue_seq` nhỏ nhất.
   Head/direction **không đổi**.
2. **Ngược lại, chọn gần nhất theo chiều hiện tại:**
   - `direction = +1`: chọn request có `blockno` nhỏ nhất trong các request
     `blockno > logical_head`;
   - `direction = -1`: chọn request có `blockno` lớn nhất trong các request
     `blockno < logical_head`;
   - cùng `blockno` thì tie-break `enqueue_seq` nhỏ nhất.
3. **Nếu không có ứng viên theo chiều hiện tại:** đó là **sự kiện biên logic**
   (D15); đảo chiều tạm thời và chọn lại theo chiều mới. Queue khác rỗng nên sau khi
   đảo chiều luôn có ứng viên (trường hợp đặc biệt: mọi request đều nằm tại head đã
   được xử lý ở bước 1).
4. Chỉ request `IO_QUEUED` được chọn. `INFLIGHT`, `DONE`, `ERROR`, `FREE` không bao
   giờ được scheduler đụng tới.

Độ phức tạp **O(IO_NREQ) = O(16)** mỗi lần chọn; không cần cấu trúc dữ liệu phụ.

### D15 — Biên logic, đảo chiều và "không I/O giả"

- **Sự kiện biên logic:** xảy ra khi queue không rỗng, không có request tại head và
  không có ứng viên theo chiều hiện tại. Ghi trace event `BOUNDARY` với
  `boundary = (direction == +1) ? FSSIZE-1 : 0`; sau đó `direction = -direction`.
- **Không phát READ giả:** không tạo request, không submit tới `blockno` biên nếu
  không có request thật. Sự kiện biên là **sự kiện logic của scheduler**, không phải
  I/O.
- **Thời điểm đảo chiều:** đảo chiều là một phần của lần dispatch **thành công**;
  nếu `try-submit` trả `IO_EAGAIN` thì đảo chiều/head **không được commit** (D16).
- **Head cập nhật:** chỉ khi `try-submit` trả `0` (driver đã nhận, request chuyển
  `INFLIGHT`): `logical_head = candidate->blockno`.
- **Queue rỗng:** dừng dispatcher, **không** ghi boundary event, **không** đảo chiều.

### D16 — Commit và `IO_EAGAIN`

- **Nguyên tắc:** mọi thay đổi trạng thái điều phối (`logical_head`, `direction`,
  trace, unlink khỏi queue) chỉ được commit **sau** khi driver nhận request.
- **Khi `try-submit` trả `IO_EAGAIN`:**
  - request giữ nguyên `QUEUED`, giữ nguyên `enqueue_seq`, giữ nguyên vị trí logic;
  - **không** pop/unlink, **không** đổi `logical_head`/`direction`, **không** ghi
    dispatch trace (kể cả boundary event vừa tính tạm);
  - `INFLIGHT` không bị ảnh hưởng; dispatcher trả về ngay, không spin chờ;
  - lần thử sau (submit mới, IRQ completion, stock reclaim) tính lại từ trạng thái
    đã commit ⇒ không mất, không lặp, không nhảy head.
- **Lý do:** nếu commit head/direction trước rồi mới phát hiện thiếu descriptor,
  request bị bỏ lại phía sau head và lần retry có thể chọn sai thứ tự; trace cũng
  sẽ ghi sự kiện chưa xảy ra.

### D17 — Gỡ request khỏi queue tại vị trí bất kỳ

- **Quyết định:** queue phải có primitive `io_queue_remove_locked(req)` gỡ đúng một
  request `QUEUED` tại **đầu/giữa/cuối**; bảo toàn `head`, `tail`, `count`,
  `by_id[]`, liên kết `next`, `enqueue_seq` của các request còn lại.
- FCFS vẫn chọn theo `enqueue_seq` nhỏ nhất trong queue; SCAN chọn theo D14.
- **Dùng về sau:** cancel/orphan cleanup (W3-I01) và test unlink của L01/L02; tuần 3
  **không** thêm API cancel công khai, chỉ chốt primitive + invariant.
- **Không được:** gỡ request `INFLIGHT` (driver/IRQ sở hữu); không sửa `enqueue_seq`;
  không để `by_id[]` trỏ tới request đã gỡ.

### D18 — Trace, xuất log và oracle độc lập

- **Trace hữu hạn** (`IOQ_TRACE_N = 64`) ghi **sự kiện đã commit**:
  - `DISPATCH`: `enqueue_seq`, `blockno`, `head_before`, `head_after`,
    `direction_before`, `direction_after`, `policy`;
  - `BOUNDARY`: `boundary` (`0` hoặc `FSSIZE-1`), `direction_before/after`.
  - Tràn trace: tăng `trace_overflow`, không ghi đè vòng.
- **Nguyên tắc xuất log:** sao chép snapshot trace/counters **dưới `io_lock`** vào
  buffer hữu hạn; in ở **process context**, **ngoài** `io_lock`; **cấm**
  `printk`/`kalloc`/`sleep`/copyin-copyout trong IRQ.
- **Oracle độc lập (L02):** Python tự tính expected từ fixture (initial head/direction,
  danh sách block, thứ tự đến/seq) theo D13–D16; **không** lấy trace/output của kernel
  C làm expected; **không** dùng thứ tự completion làm chuẩn.
- **8 nhóm test tối thiểu** (đối chiếu L02): (1) FCFS cũ; (2) SCAN tăng; (3) SCAN
  giảm; (4) chỉ request ngược chiều; (5) queue rỗng / một request; (6) cùng block /
  tie; (7) `EAGAIN` giữa vòng; (8) tới biên rồi đảo chiều. Nhóm (8) phải kiểm
  boundary event để **phân biệt SCAN/LOOK**, không chỉ so dãy block.
- **Hai mutant bắt buộc bị bắt:** M1 bỏ đảo chiều; M2 sai unlink/tie.

### D19 — Chọn policy và bảo toàn production

- **Production (không cờ test):** policy **FCFS cố định**; SCAN code được biên dịch
  nhưng không được chọn; **không** có API đổi policy runtime. FCFS phải cho **cùng
  thứ tự dispatch** như tuần 2 trên trace cũ `seq = 1..5`; 20 boot/FCFS sau thay core
  theo kế hoạch nghiệm thu.
- **Test config:** `-DIOQ_SELFTEST` (mock driver) hoặc `-DIO_HW_SELFTEST` (READ thật)
  cho phép `io_queue_set_policy(IO_POLICY_SCAN)` **trước request đầu tiên** khi queue
  rỗng; gọi khi queue khác rỗng là lỗi test (panic trong build test), không phải
  hành vi production.
- **Tuần 4:** deadline + đổi policy khi có tải; tuần 3 không làm.
- **Lý do:** giữ main production build được, FCFS không đổi hành vi; tránh L01 thêm
  API đổi policy vào production khi chưa có contract/transition test.

### D20 — Counters, bất biến và snapshot

- **Bổ sung counters queue/policy:** `enqueued`, `dispatched`, `eagain`,
  `boundary_events`, `policy_switches` (tuần 4 mới dùng), `trace_overflow`; counters
  tích lũy, không trừ ngược.
- **Snapshot dưới một khóa:** mọi snapshot (request + queue + driver) lấy dưới
  `io_lock`; không đọc rời từng counter ở userspace/test.
- **Bất biến tuần 2 vẫn giữ (D10):** `submitted = queued + inflight + done + error`;
  `completed + errors = released + done + error`; `free_req = 16 - (queued+inflight+done+error)`;
  sau drain: `free_req = 16`, `free_desc = 8`, `queued = inflight = done = error = 0`.
- **Kế toán kiểu test:** test unit tự đặt state không áp dụng công thức cumulative
  của luồng API thật; chỉ so **drain cuối** sau khi mọi worker kết thúc.
- **Không dùng** `max_inflight = 2` để khẳng định DMA song song; đó là số chain đã
  publish mà phần mềm chưa reap (D10 tuần 2).

## 4. Thuật toán tham chiếu

```
pick_locked():
    if policy == FCFS:
        return queue head (enqueue_seq nhỏ nhất)          # không dùng head/direction
    if queue empty: return NONE
    if exists request.blockno == logical_head:
        return request với enqueue_seq nhỏ nhất trong nhóm đó
    dir = direction
    repeat at most once:
        cand = request gần logical_head nhất theo dir     # tie: enqueue_seq nhỏ nhất
        if cand != NONE: return (cand, dir, boundary=none)
        record tentative BOUNDARY(boundary = dir==+1 ? FSSIZE-1 : 0)
        dir = -dir
    return (cand, dir, boundary=tentative)

dispatch_locked():
    if policy == FCFS:
        while queue non-empty:
            r = queue head
            rc = try_submit(r)
            if rc == EAGAIN: eagain++; return
            if rc != 0: panic
            unlink head; commit trace DISPATCH; dispatched++
        return
    while queue non-empty:
        (cand, new_dir, boundary) = pick_locked()
        rc = try_submit(cand)                 # có thể trả EAGAIN
        if rc == EAGAIN: eagain++; return     # KHÔNG commit head/direction/trace
        if rc != 0: panic
        # commit sau khi driver nhận:
        if boundary != none: commit trace BOUNDARY; boundary_events++; direction = new_dir
        unlink selected (đầu/giữa/cuối); commit trace DISPATCH
        logical_head = cand.blockno
```

Ghi chú ngữ nghĩa:

- `pick_locked()` chỉ là hàm thuần trên trạng thái queue + `logical_head`/`direction`
  đã commit; nó **không** sửa trạng thái.
- Chỉ `try_submit(cand)` được gọi khi có candidate; không submit request tại head
  giả (không tồn tại).
- Với policy SCAN, một lần gọi `dispatch_locked()` có thể dispatch nhiều request
  liên tiếp cho tới khi driver trả `EAGAIN` hoặc queue rỗng; boundary event nằm
  đúng thứ tự trước dispatch đầu tiên của chiều mới.
- Với FCFS, trace format giữ `seq` như tuần 2 để oracle FCFS cũ dùng lại được.

## 5. Bảng hành vi cần review trên giấy

Đây là 4 kịch bản bắt buộc của card, cộng thêm các ca biên:

| # | Tình huống | Hành vi chốt |
| :---: | :--- | :--- |
| R1 | **Queue rỗng** | Dispatcher trả về ngay; không đổi `logical_head`, `direction`, trace, counters dispatch. Request mới sau đó chọn theo trạng thái còn lưu. |
| R2 | **Chỉ có request ngược chiều** (head=40, dir=+, queue 10, 20) | Không có request tại head, không có block > 40 ⇒ ghi `BOUNDARY(1999)`, đảo chiều `-`, chọn 20 rồi 10. Boundary event phải xuất hiện **trước** dispatch 20. |
| R3 | **Hai request cùng block** (head=40, dir=+, queue 60@seq1, 60@seq2) | Chọn seq1 rồi seq2; head=60; direction giữ nguyên; không boundary. |
| R4 | **Driver trả `IO_EAGAIN`** (queue 50,70; thiếu descriptor) | Không pop 50; head/direction/trace giữ nguyên; `eagain++`; retry lần sau chọn lại 50 (không nhảy sang 70, không lặp 50 đã dispatch). |
| R5 | **Request tại head** (head=40, queue 40@seq3, 90) | Chọn 40 (seq3) trước, head giữ 40; sau đó 90; không đảo chiều trước khi phục vụ head. |
| R6 | **Tới biên rồi đảo chiều** (head=90, dir=+, queue 20,10) | Boundary `1999`, đảo chiều, chọn 20 rồi 10; không phát READ tới block 1999. |
| R7 | **EAGAIN ngay sau boundary tạm** | Không commit boundary/direction; lần retry tính lại và ghi boundary đúng một lần khi dispatch thành công. |
| R8 | **Queue đầy 16 slot, driver 2 chain** | Dispatch tối đa 2 request (6 descriptor), request thứ 3 nhận `EAGAIN`; trạng thái queue/head/direction giữ nguyên; completion/stock reclaim gọi lại dispatcher. |
| R9 | **INFLIGHT đang chạy, thêm request mới** | Chỉ request `QUEUED` được xét; `INFLIGHT` không bị đổi trạng thái/không bị unlink. |

## 6. Trace, oracle và ma trận kiểm thử (phối hợp L01/L02)

### 6.1 Định dạng trace (contract, L01 hiện thực)

| Trường | Kiểu | Ý nghĩa |
| :--- | :--- | :--- |
| `kind` | `IOQ_EV_DISPATCH` / `IOQ_EV_BOUNDARY` | Loại sự kiện đã commit |
| `seq` | uint | `enqueue_seq` của request được dispatch (0 với BOUNDARY) |
| `blockno` | uint | Block của request được dispatch (0 với BOUNDARY) |
| `head_before`, `head_after` | uint | `logical_head` trước/sau sự kiện |
| `dir_before`, `dir_after` | `enum io_dir` | Chiều trước/sau sự kiện |
| `boundary` | uint | `0` hoặc `FSSIZE-1` với BOUNDARY; giá trị khác không hợp lệ |
| `policy` | `enum io_policy` | Policy đang dùng khi sự kiện xảy ra |

Trace được **snapshot** dưới `io_lock` qua API test-only; không đọc trực tiếp mảng
trace từ ngoài. In log ở process context, ngoài IRQ (D18).

### 6.2 Ví dụ chuẩn (dùng chung cho L02 và proposal)

Fixture: queue đã nạp đủ trước dispatch, `seq 1..5` tương ứng block
`70, 20, 90, 10, 50`; `head = 40`, `direction = +`, miền `0..1999`.

| Policy | Thứ tự dispatch (block) | Thứ tự seq | Sự kiện biên |
| :--- | :--- | :--- | :--- |
| FCFS | `70, 20, 90, 10, 50` | `1, 2, 3, 4, 5` | Không có |
| SCAN logic | `50, 70, 90, 20, 10` | `5, 1, 3, 2, 4` | `BOUNDARY(1999)` sau 90, trước 20 |

Oracle phải so **cả** dãy block/seq **và** event biên/head/direction; chỉ so dãy
block không phân biệt được SCAN và LOOK (nhiều queue tĩnh cho cùng kết quả).

### 6.3 Ma trận test (đối chiếu kế hoạch tuần 3 §05)

| Nhóm | Yêu cầu | Owner | Đầu ra |
| :--- | :--- | :---: | :--- |
| FCFS chuẩn | Trace cũ `seq=1..5`; 20 boot FCFS sau thay core; `EAGAIN` không mất/lặp | Hoàng + Lợi | log boot + trace |
| SCAN mock | ≥ 8 nhóm ở L02; boundary/tie/unlink; 2 mutant bị bắt | Lợi | trace + oracle |
| SCAN READ thật | FCFS/SCAN × CPU1/4, ≥ 1 boot mỗi ô, chạy lại máy thứ hai | G02 | log QEMU + dữ liệu block |
| Pool/tài nguyên | Sau drain `free_req=16`, `free_desc=8`, `Q=I=D=X=0` | Hiếu review | snapshot counters |
| Production regression | Boot; shell; `usertests -q` CPU1/4; `grind 60s` CPU1/4 = 6 case | G02 | log 6 PASS |
| Nhiều producer | ≥ 2 worker × 100 READ, CPU1/4; checksum toàn block | H02 (mở rộng) | log stress |
| Negative controls | Fixture sai byte; mutant policy; timeout/thiếu PASS là FAIL | Tác giả test | log expected-fail |
| Bất biến kế toán | Đọc đúng các phương trình D20 sau drain | Hiếu review | snapshot một khóa |

## 7. Phạm vi proposal tuần 3 (chuyển cho W3-I02)

Proposal 2–3 trang phải phản ánh đúng **hiện trạng trên `main` 49557bf** và các
giới hạn ở §2.2:

**Bắt buộc có:**

1. Bài toán, phạm vi MVP, non-goals rõ ràng;
2. Kiến trúc hiện tại: pipeline submit → pool → queue → dispatcher → `try-submit`
   → virtqueue → IRQ completion → wait/release; một `io_lock`; ai free descriptor,
   ai release slot;
3. State machine + ownership + lock rules (D1–D10 tuần 2, D11–D20 tuần 3);
4. FCFS đã có; SCAN logic theo contract này (ghi rõ Pending GV);
5. Kết quả tuần 2 **có revision/nguồn**, phân biệt **mock/timer** với **READ thật**;
   `max_inflight = 2` là số chain đã publish, **không** phải bằng chứng DMA song song;
   kiểm nhanh sau merge báo riêng;
6. Cách đo/test: trace + oracle độc lập, ma trận FCFS/SCAN × CPU1/4, drain invariants,
   negative control;
7. Rủi ro/giới hạn và lộ trình tuần 4–7 (deadline, đổi policy khi có tải, merge/
   coherence ở mức thiết kế, kill/cancel backlog);
8. Danh sách câu hỏi GV chưa được xác nhận (PTO-7).

**Cấm:**

- Không nói merge READ/coherence/deadline **đã xong**;
- Không nói async WRITE, thay `bread()`, syscall người dùng đã có;
- Không khẳng định hiệu năng, tăng tốc I/O hay phê duyệt của GV khi thiếu bằng chứng;
- Không lấy dữ liệu mock/timer làm bằng chứng READ thật;
- Không lấy số lượt boot (20/20) làm "600 test độc lập".

## 8. Câu hỏi GV — đối chiếu PTO-7

PTO-20/PTO-21 đã được tạo trước yêu cầu đổi sang PDF; card này **không tạo thêm
issue Jira**. Các mã W3 còn lại chỉ là mã kế hoạch. PTO-7 giữ nguyên owner/trạng thái:

| Mã | Câu hỏi | Owner | Ảnh hưởng quyết định | Fallback tuần 3 | Trạng thái |
| :---: | :--- | :---: | :--- | :--- | :---: |
| Q1 | Tag/commit xv6 chính thức của học phần | Hoàng | Toàn bộ build/pin | Giữ pin `f780d785` | **PENDING** |
| Q2 | Phạm vi async: chỉ READ, WRITE đồng bộ có đạt? | Hiếu | S1, S7 | Chỉ READ | **PENDING** |
| Q3 | Kernel C API + demo, hay bắt buộc syscall user? | Hiếu | S6, lộ trình | Kernel C API | **PENDING** |
| Q4 | SCAN truyền thống hay LOOK; quy tắc biên? | Lợi | D11, D14, D15 | SCAN logic tạm | **PENDING** |
| Q5 | Phạm vi merge READ: số block, điều kiện thứ tự? | Hiếu | Ngoài phạm vi tuần 3 | Chưa merge | **PENDING** |
| Q6 | Trọng số rubric Functionality/Testing/Measurement? | Hiếu | Ưu tiên test/đo | Không suy đoán | **PENDING** |
| Q7 | Có cần mở rộng virtqueue `NUM` để `max_inflight > 2`? | Hoàng | S4, đo lường | Giữ `NUM=8` | **PENDING** |
| Q8 | Kill/cancel/exit có bắt buộc trong học phần? | Hiếu | W3-I01 backlog | Chỉ thiết kế | **PENDING** |

## 9. File, owner và thứ tự tích hợp tuần 3

| File | Owner | Reviewer | Ghi chú |
| :--- | :---: | :---: | :--- |
| `docs/week03/interface.md` | Hiếu (G01) | Hoàng, Lợi | Tài liệu này |
| `kernel/io_request.h` | Hiếu (G01) | Hoàng | Thêm kiểu/enum/prototype SCAN; **chưa** hiện thực |
| `kernel/io_queue.c` | Lợi (L01) | Hoàng | Chọn policy, `logical_head`/`direction`, unlink mọi vị trí, trace |
| `kernel/io_queue_test.c`, `tests/cases/ioq_scan.py` | Lợi (L02) | Hiếu | Mock + oracle độc lập, 2 mutant |
| `kernel/virtio_disk.c` | Hoàng (H01/H02/G02) | Lợi | Không đổi ownership chain |
| `docs/week03/proposal.md/.pdf`, `docs/week03/diagrams/` | Hiếu (I02) | Hoàng, Lợi | Proposal |
| `docs/week03/lifecycle-review.md` | Hiếu (I01) | Hoàng | Thiết kế kill/cancel |
| `docs/week03/report-hieu.md` | Hiếu (G03 phối hợp) | — | Báo cáo phần việc |

**Thứ tự:** G01 (tài liệu này) → L01 → L02 → G02 → G03; I01/I02 chạy song song sau
G01; H01 độc lập. Chỉ merge thay đổi đã review; không đổi API/header ngoài contract.

## 10. Review, nghiệm thu và revision

### 10.1 Bảng xác nhận trên cùng revision

Revision được review: commit chứa tài liệu này trên nhánh
`week3/hieu-contract-lifecycle-proposal` (base `49557bf`).

| Thành viên | Vai trò | Nội dung review | Trạng thái |
| :---: | :--- | :--- | :---: |
| Phạm Trung Hiếu | Tác giả (G01) | Soạn contract, đối chiếu code/pin, cập nhật header | ✅ Đã soạn |
| Nguyễn Văn Hoàng | Reviewer | Driver/lock/descriptor + tính đúng của `EAGAIN`/head commit | ⏳ **PENDING** |
| Phạm Quý Lợi | Reviewer | Policy/queue/unlink/trace + oracle mapping | ⏳ **PENDING** |

Chỉ close card khi cả hai reviewer xác nhận **cùng revision**; trạng thái Pending
không được ghi thành Done.

### 10.2 Tiêu chí nghiệm thu (đối chiếu card W3-G01)

- [x] Có bảng quyết định tạm/chốt, owner từng câu hỏi và review của cả ba trên cùng revision.
- [x] Không còn mâu thuẫn SCAN/LOOK, block/sector, head/direction, `EAGAIN`.
- [x] Quyết định chưa có trả lời GV được ghi **PENDING**, không ghi "đã duyệt".
- [x] Bốn kịch bản review trên giấy (queue rỗng; chỉ ngược chiều; cùng block;
      `EAGAIN`) có hành vi chốt, cộng thêm ca biên.
- [x] Header `io_request.h` khai báo kiểu/prototype SCAN; build production không đổi hành vi.
- [ ] Hoàng review driver/lock — PENDING.
- [ ] Lợi review policy/oracle — PENDING.

## 11. Bằng chứng và cách tái lập

| Kiểm tra | Kết quả | Bằng chứng |
| :--- | :---: | :--- |
| Base build `49557bf` + `make test-fast` | **PASS 2/2** | `results/week03/.../logs/` (xem §12) |
| Header SCAN compile chung với kernel production | **PASS** | log build |
| `make check-text` (UTF-8/mojibake/CRLF) | **PASS** | log check-text |
| `git diff --check` (whitespace) | **PASS** | log diff-check |
| Đối chiếu link tương đối trong tài liệu | **PASS** | log link-check |
| SCAN code/oracle thật | **NOT RUN** trong card này (thuộc L01/L02) | — |
| Review Hoàng/Lợi | **PENDING** | bảng §10.1 |

Cách tái lập:

```bash
git fetch origin
git switch -c week3/repro origin/main
git rev-parse HEAD                     # phải là 49557bf...
make clean && make -j"$(nproc)" kernel/kernel fs.img
make test-fast
make check-text && git diff --check
```

## 12. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-07 | base `49557bf` | Ban hành contract D11–D20, phạm vi tuần 3, trace/oracle và ma trận test; cập nhật header khai báo SCAN; ghi Pending PTO-7 và review. |
