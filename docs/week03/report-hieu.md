# Báo cáo nhiệm vụ hoàn thành — Tuần 3 (Phạm Trung Hiếu)

---

## 1. Tóm tắt

Hiếu phụ trách 3 card trong kế hoạch tuần 3: **W3-G01** (contract SCAN + phạm vi
proposal), **W3-I01** (rà vòng đời request + thiết kế kill/cancel) và **W3-I02**
(proposal kỹ thuật 2–3 trang). Cả ba đã có đầu ra nằm trong repo, đúng base
revision `49557bf`, kèm log kiểm chứng trên build thật:

| Card | Đầu ra chính | Trạng thái card |
| :--- | :--- | :---: |
| **W3-G01** (PTO-20) | [`docs/week03/interface.md`](interface.md): contract D11–D20, phạm vi tuần 3, trace/oracle, bảng PTO-7, review; [`kernel/io_request.h`](../../kernel/io_request.h) thêm khai báo SCAN; [`docs/architecture.md`](../architecture.md) cập nhật §2.4/§2.9 | ✅ Đầu ra đủ |
| **W3-I01** | [`docs/week03/lifecycle-review.md`](lifecycle-review.md): rà soát K1–K10, bảng state/event/action/owner, thiết kế owner/orphan/cancel, ngân sách bộ nhớ, 6 test K1–K6 | ✅ Thiết kế/review; code **chưa** (đúng phạm vi card)|
| **W3-I02** | [`docs/week03/proposal.md`](proposal.md) + [`proposal.pdf`](proposal.pdf) **3 trang**; [`diagrams/`](diagrams/) (nguồn + SVG); [`tools/build_pdf.ps1`](tools/build_pdf.ps1) | ✅ Bản nháp v1.0|

**Không** tuyên bố trong báo cáo này:

- SCAN đã chạy/đạt (thuộc **L01/L02**, chưa có code SCAN trên nhánh này);

---

Log và môi trường:
[`results/week03/hieu-contract-lifecycle-2026-11-07/`](../../results/week03/hieu-contract-lifecycle-2026-11-07/summary.md)
(`logs/env.txt`, `build.log`, `test-fast.log`, `test-io.log`, `io-selftest.log`,
`restore-production-build.log`, `test-fast-post-restore.log`).

---

## 3. Chi tiết nhiệm vụ đã hoàn thành

### 3.1 W3-G01 — Chốt contract SCAN và phạm vi proposal tuần 3 (PTO-20)

**Mục tiêu:** chốt trước khi L01 sửa queue: SCAN hay LOOK, tọa độ block/miền hợp lệ,
head/direction và commit, biên logic, `EAGAIN`, trace/oracle, phạm vi proposal.

**Đã thực hiện (đối chiếu 6 bước của card):**

| Bước card | Việc đã làm | Đầu ra/đối chiếu |
| :---: | :--- | :--- |
| 1 | Đọc `main` `49557bf`, `io_request.h`, `docs/week02/interface.md`; xác nhận phạm vi kế thừa: READ 1 block, `ROOTDEV`, pool 16, `NUM=8`, staging buffer, một `io_lock` | `interface.md` §1–§2 (S1–S9) |
| 2 | Chốt **SCAN logic** tạm thời; giữ **LOOK** là phương án thay thế; ghi **Pending** câu trả lời GV (PTO-7/Q4); không coi giả định là xác nhận | D11; §8 Q4 |
| 3 | Chốt tọa độ `blockno` `0..FSSIZE-1`, head/direction khởi tạo, tie-break `enqueue_seq`, cập nhật head sau dispatch thành công, queue rỗng | D12–D14 |
| 4 | Chốt sự kiện biên logic + đảo chiều; **không phát READ giả**; ghi rõ là điều phối phần mềm trên QEMU, không đo seek vật lý | D15; §6.2 |
| 5 | Chốt `IO_EAGAIN` **không commit** head/direction/trace, giữ request/seq, không đổi `INFLIGHT`; snapshot counters dưới một khóa; cấm `printk/kalloc/sleep` trong IRQ | D16, D20, D18 |
| 6 | Gộp câu hỏi tag, READ-only, kernel API/syscall, SCAN/LOOK, merge vào bảng PTO-7 kèm owner/fallback/trạng thái; không tạo issue Jira trùng | §8 (Q1–Q8, toàn bộ **PENDING**) |

**Quyết định mới:** D11 (SCAN/LOOK), D12 (đơn vị/miền), D13 (trạng thái đầu),
D14 (chọn request), D15 (biên/đảo chiều), D16 (commit/EAGAIN), D17 (gỡ mọi vị trí),
D18 (trace/oracle), D19 (chọn policy/production), D20 (counters/bất biến).

**Kết quả bàn giao:**

- [`docs/week03/interface.md`](interface.md) — contract đầy đủ, có bảng 9 kịch bản
  review trên giấy (queue rỗng, ngược chiều, cùng block, `EAGAIN`, request tại head,
  biên, EAGAIN sau biên, queue/descriptor đầy, INFLIGHT) và ma trận test 8 nhóm.
- [`kernel/io_request.h`](../../kernel/io_request.h) — thêm (contract, chưa hiện thực):
  `enum io_policy`, `enum io_dir`, `IOQ_TRACE_N = 64`, `struct ioq_trace_ev`,
  `struct ioq_scan_state`, `io_queue_remove_locked`, `io_queue_get_scan_state_locked`,
  `io_queue_trace_snapshot_locked`, `io_queue_set_policy` (chỉ build test).
- [`docs/architecture.md`](../architecture.md) — cập nhật §2.4 (SCAN) và thêm §2.9
  (trạng thái tuần 3: contract SCAN + lifecycle design, chưa hiện thực).

**Đối chiếu tiêu chí nghiệm thu card:**

| # | Tiêu chí | Kết quả |
| :---: | :--- | :--- |
| 1 | Bảng quyết định tạm/chốt, owner từng câu hỏi, review cả ba trên cùng revision | ✅ D11–D20 + §8 (owner) + §10.1 (bảng review 3 người) |
| 2 | Không còn mâu thuẫn SCAN/LOOK, block/sector, head/direction, EAGAIN | ✅ D11–D16 |
| 3 | Quyết định chưa có trả lời GV ghi Pending | ✅ Q1–Q8 **PENDING**, không ghi "đã duyệt" |
| 4 | Hoàng/Lợi review cùng revision | ⏳ **PENDING** — chưa được ghi Done |

### 3.2 W3-I01 — Rà vòng đời request và thiết kế kill/cancel

**Mục tiêu:** trả lời điều gì xảy ra với request async khi caller bị kill/exit; xác
định ai thao tác handle, ai sở hữu dữ liệu, con trỏ data hết hạn khi nào; đề xuất
owner/ref + orphan reclaim; đánh giá ngân sách bộ nhớ; nêu test cần viết.

**Đã thực hiện:**

1. **Rà code tại base revision:** `io_request.c` (submit/alloc/lookup/release/
   poll/wait/data/completion), `io_queue.c` (enqueue/dispatch), `virtio_disk.c`
   (try-submit/reap/IRQ), `proc.c` (`kkill`, `kexit`, `sleep_prepare`, `sleep`,
   `wakeup`), `trap.c` (kiểm `killed` trước/sau syscall). Đối chiếu từng trạng thái
   với từng sự kiện kill/exit.
2. **Phát hiện và phân loại K1–K10**, trong đó 3 kết luận chính:
   - **Không có use-after-free DMA khi kill**: staging buffer/request nằm trong BSS,
     kill không free gì; IRQ vẫn reap chain đúng một lần.
   - **Rò rỉ slot là hệ quả chính**: request không được release sau khi chủ chết;
     16 slot rò rỉ ⇒ async I/O trả `EAGAIN` vĩnh viễn (stock vẫn chạy).
   - **Kill không "cắt" được `aio_wait` hiện tại**: vòng lặp không kiểm tra `killed`,
     nên kill chỉ có hiệu lực sau khi I/O hoàn tất (hoặc có thể treo nếu thiết bị
     không hoàn tất); thêm vào đó, handle không có owner nên không thể thu hồi chính xác.
3. **Thiết kế đề xuất (chưa triển khai):**
   - Phương án A (khuyến nghị): thêm `owner_pid` (+ `flags` ORPHAN) ⇒ +8 B/slot,
     pool 17 408 B (+128 B, +0,74%), không động `kalloc`; cleanup O(IO_NREQ) ở `kexit`.
   - API: `aio_cancel` (chỉ `QUEUED`), `aio_abandon`, `io_owner_exit(pid)`;
     `aio_wait` kill-aware trả `IO_EINTR`; owner check trên mọi API (`IO_EPERM`).
   - Bảng state × event × action × owner cho `QUEUED/INFLIGHT/DONE/ERROR` khi
     kill/cancel/exit/abandon; quy tắc "không free slot `INFLIGHT`", "IRQ free slot
     chỉ sau completion", "`released++` trên mọi đường auto-free".
   - Nêu rõ **khe hở còn lại** giữa kiểm tra `killed` và `sleep()`; đề xuất hướng
     xử lý ở tuần 4 (wakeup kênh trong `kkill` hoặc timeout) nhưng **không** làm
     trong tuần 3.
4. **6 kịch bản test K1–K6** (kill trước dispatch, khi `INFLIGHT`, sau `DONE`,
   cleanup đúng một lần, kill waiter, rò rỉ 16 slot) kèm negative control — ghi
   **NOT RUN** vì chưa có code.

**Kết quả bàn giao:** [`docs/week03/lifecycle-review.md`](lifecycle-review.md)
(gồm §7 đối chiếu 3 tiêu chí nghiệm thu, §8 bảng "code nào đã có / thiết kế nào
chưa", §10 checklist review lifetime DMA cho Hoàng).

**Đối chiếu tiêu chí nghiệm thu card:**

| # | Tiêu chí | Kết quả |
| :---: | :--- | :--- |
| 1 | Bảng state/event/action + owner cho mọi trường hợp | ✅ §3, §5.4 (K1–K10 + thiết kế) |
| 2 | Nêu rõ code nào đã có, thiết kế nào chưa triển khai/test | ✅ §8 |
| 3 | Hoàng review lifetime DMA; không thêm early-free vào INFLIGHT | ⏳ **PENDING**; thiết kế giữ nguyên "không free khi INFLIGHT" |

### 3.3 W3-I02 — Hoàn thiện proposal

**Mục tiêu:** proposal 2–3 trang phản ánh đúng READ-FCFS đã có trên `main` và lộ
trình SCAN/deadline/merge còn lại.

**Đã thực hiện:**

- Soạn [`docs/week03/proposal.md`](proposal.md) theo 10 mục: bài toán/mục tiêu;
  phạm vi/non-goals; kiến trúc hiện tại (pipeline, component, lifecycle, ownership/
  lock); FCFS + SCAN logic (D11–D20, ví dụ `head=40`); kết quả tuần 2 **có revision
  và phân loại bằng chứng**; đo lường/kiểm thử; rủi ro/giới hạn; lộ trình tuần 4–7;
  PTO-7; tham chiếu.
- Nêu rõ: kernel C API hiện có, chưa có syscall user, không thay `bread/bwrite`,
  **chưa** giải quyết coherence, WRITE/log giữ đồng bộ; `max_inflight = 2` là số
  chain đã publish, **không** phải bằng chứng DMA song song; kiểm nhanh sau merge
  ngày 07/11 báo **riêng**, không thay bộ nghiệm thu G02.
- Vẽ pipeline `submit → pool → queue → scheduler → try_submit → virtqueue →
  IRQ completion → wait/release`, đánh dấu một `io_lock`, ai free descriptor, ai
  release slot; thêm sơ đồ ví dụ SCAN logic (nguồn + SVG).
- Xuất **PDF 3 trang** từ nguồn Markdown bằng pandoc + Chrome headless; lưu script
  sinh + CSS trong repo để tái lập.

**Kết quả bàn giao:**

| Đầu ra | Ghi chú |
| :--- | :--- |
| [`proposal.md`](proposal.md) | Nguồn sự thật, chỉnh sửa được |
| [`proposal.pdf`](proposal.pdf) | **3 trang A4**, có nhúng Hình 1; đã kiểm page count + text |
| [`diagrams/make_diagrams.py`](diagrams/make_diagrams.py) | Sinh `architecture-pipeline.svg` + `scan-boundary.svg` |
| [`diagrams/architecture-pipeline.svg`](diagrams/architecture-pipeline.svg) | Hình 1 trong proposal (nguồn sửa được) |
| [`tools/build_pdf.ps1`](tools/build_pdf.ps1), [`tools/print.css`](tools/print.css) | Tái lập PDF từ Markdown |

**Đối chiếu tiêu chí nghiệm thu card:**

| # | Tiêu chí | Kết quả |
| :---: | :--- | :--- |
| 1 | Proposal 2–3 trang, đủ kiến trúc/giới hạn/test/lộ trình | ✅ **3 trang** (pypdf); đủ 10 mục bắt buộc |
| 2 | Đủ review cả ba; không khẳng định hiệu năng/phê duyệt GV thiếu bằng chứng | ⏳ Review **PENDING**; proposal chỉ ghi Pending, không có claim hiệu năng/GV |
| 3 | Nguồn sơ đồ + source chỉnh sửa được lưu cùng PDF | ✅ `.md` + `make_diagrams.py` + `.svg` + `build_pdf.ps1` cùng repo |

---

## 4. Bằng chứng kiểm chứng

### 4.1 Kết quả đã chạy (PASS)

| # | Kiểm tra | Kết quả | Log |
| ---: | :--- | :---: | :--- |
| 1 | Build production `make -j4 kernel/kernel fs.img` | **PASS** (exit 0) | [`logs/build.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/build.log) |
| 2 | `make test-fast` (boot CPUS=1 + shell/fs CPUS=3) | **PASS 2/2** | [`logs/test-fast.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/test-fast.log) |
| 3 | `make test-io` — kernel selftest pool/handle T02/T03/T04/T11 | **PASS** | [`logs/test-io.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/test-io.log) |
| 4 | `make test-io` — process-context T05/T04/T06a/T06b/T03/T11 | **PASS** | [`logs/io-selftest.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/io-selftest.log) |
| 5 | Restore production build sau test-io | **PASS** | [`logs/restore-production-build.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/restore-production-build.log) |
| 6 | `make test-fast` trên production đã restore | **PASS 2/2** | [`logs/test-fast-post-restore.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/test-fast-post-restore.log) |
| 7 | `make check-text` (UTF-8/mojibake/CRLF) | **PASS** — toàn repo sạch | [`logs/check-text.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/check-text.log) |
| 8 | `git diff --check` | **PASS** | [`logs/diff-check.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/diff-check.log) |
| 9 | Link tương đối trong `docs/week03/` + README | **PASS** | [`logs/link-check.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/link-check.log) |
| 10 | PDF proposal: số trang + text + nhúng Hình 1 | **3 trang**, PASS | [`logs/pdf-check.log`](../../results/week03/hieu-contract-lifecycle-2026-11-07/logs/pdf-check.log) |

Ghi chú: `make test-fast` 2/2 là **smoke** sau merge/restore, không thay bộ nghiệm
thu 6 case của G02. Dòng `IO-SELFTEST: PASS` + `IO-USER-TEST: PASS` nằm trong
`io-selftest.log` (log serial của QEMU), không nằm trong output make.

### 4.2 NOT RUN (ghi đúng trạng thái)

| Hạng mục | Lý do | Chuyển tiếp |
| :--- | :--- | :--- |
| SCAN mock/oracle 8 nhóm, 2 mutant | SCAN code thuộc **L01/L02**, chưa có trên nhánh | L02, rồi G02 |
| SCAN READ thật FCFS/SCAN CPU1/4 | Cần code L01 + tích hợp driver | G02 |
| Kill/cancel K1–K6 | W3-I01 **chỉ thiết kế**, chưa triển khai code | Tuần 4+ (backlog) |
| Production regression 6 case (`usertests -q`, `grind 60s` CPU1/4) | Thuộc G02; card cá nhân không chạy | G02 |
| Review Hoàng (G01/I01) + Lợi (G01/I02) | Chưa có xác nhận trên revision này | Trước khi đóng card |
| Câu trả lời GV Q1–Q8 (PTO-7) | Chưa được GV trả lời | Giữ **PENDING** |

---

## 5. Thời gian: kế hoạch và thực tế

| Card | Ước lượng trong kế hoạch tuần 3 | Phần của Hiếu | Thực tế ghi nhận |
| :--- | :---: | :---: | :--- |
| W3-G01 | 3h tổng (chia đều 3 người) | 1h | **Chưa ghi worklog giờ thực tế** |
| W3-I01 | 2h | 2h | **Chưa ghi worklog giờ thực tế** |
| W3-I02 | 3h | 3h | **Chưa ghi worklog giờ thực tế** |
| Phần chung G01/G02/G03 | 1h/card/người | 3h | **Chưa ghi worklog giờ thực tế** |

Theo quy định của kế hoạch tuần 3 (§04 mục 4): **không** lấy giờ ước lượng gán thành
worklog; actual hours phải cập nhật đến 08/11. Báo cáo này chỉ ghi trạng thái đầu
ra, không tự nhận số giờ chưa được ghi nhận. Ước lượng 6h phần riêng + 3h phần chung
là **để planning**, không phải thời gian đã làm.

---

## 6. Đóng góp, phối hợp và việc tiếp theo

| Nội dung | Người phụ trách | Trạng thái/ghi chú |
| :--- | :---: | :--- |
| Contract SCAN D11–D20 làm nền cho L01 (queue/policy) và L02 (oracle) | Hiếu | ✅ Đã ban hành; L01/L02 dùng cùng revision |
| Khai báo kiểu/prototype SCAN trong header để L01 hiện thực | Hiếu | ✅ Contract-only; build production không đổi hành vi |
| Rà soát driver/lock/`EAGAIN` của contract | Hoàng | ⏳ **PENDING** (reviewer G01) |
| Rà soát policy/unlink/trace/oracle mapping | Lợi | ⏳ **PENDING** (reviewer G01) |
| Review lifetime DMA của thiết kế kill/cancel | Hoàng | ⏳ **PENDING** (reviewer I01) |
| Review kiến trúc/giới hạn/test của proposal | Hoàng + Lợi | ⏳ **PENDING** (reviewer I02) |
| Hiện thực SCAN + oracle, trace đúng contract | Lợi (L01/L02) | Chưa bắt đầu trên nhánh này |
| Tích hợp SCAN + READ thật, regression 6 case, hai máy | Hoàng (G02) | Phụ thuộc L01/L02 |
| Đồng bộ README/report tuần 3 | Lợi (G03) | Sau khi có kết quả G02 |
| **Việc Hiếu tiếp theo** | Hiếu | Review L01 theo D14–D19; kiểm oracle L02 độc lập; review counters/ownership ở G02; chuyển thiết kế owner/cancel thành PR tuần 4 nếu đủ thời gian |

---

## 7. Giới hạn và rủi ro

| Giới hạn/rủi ro | Ảnh hưởng | Xử lý |
| :--- | :--- | :--- |
| Chưa có review Hoàng/Lợi | Card chưa được đóng; có thể phải sửa contract | Giữ **PENDING**, không ghi Done; review trước merge tuần 3 |
| SCAN chưa hiện thực/kiểm chứng | Chưa có bằng chứng SCAN; đề tài mới có FCFS thật | L01/L02/G02; proposal ghi rõ Pending |
| Kill/cancel chưa triển khai | Slot có thể rò rỉ khi process chết | Backlog tuần 4+; đã có thiết kế + test cần viết |
| `NUM=8` giới hạn 2 chain | Không chứng minh được song song sâu | PTO-7/Q7; không tự tăng `NUM` |
| Chưa có câu trả lời GV | SCAN/LOOK, API, merge, rubric đều tạm | Giữ Pending; không tự chốt thay GV |
| CI đang comment | Không có CI làm bằng chứng | Chỉ dùng log local; đề xuất bật CI tuần 4 |
| Toolchain khác nhau giữa máy | Có thể lệch cấu hình | H01 chuẩn hóa prefix; ghi môi trường trong mọi log |

---


## 9. Commit, file và cách tái lập

### 9.1 Phạm vi thay đổi

Không thay đổi: `kernel/io_request.c`, `kernel/io_queue.c`, `kernel/virtio_disk.c`,
`kernel/proc.c`, `kernel/trap.c`, `Makefile` — tức **không** đổi hành vi runtime,
không thêm code SCAN/kill/cancel.

### 9.2 Lệnh tái lập

```bash
git fetch origin
git switch -c week3/repro origin/main
git rev-parse HEAD                     # phải là 49557bf...
make clean && make -j"$(nproc)" kernel/kernel fs.img
make test-fast
make test-io                           # build selftest + boot QEMU; xem results/local/io-selftest.log
make clean && make -j"$(nproc)" kernel/kernel fs.img   # restore production
make test-fast
make check-text && git diff --check


## 10. Kết luận

Trong phạm vi 3 card được giao đã hoàn thành:

1. **Chốt contract SCAN + phạm vi tuần 3** với 10 quyết định D11–D20, header khai
   báo contract, ma trận test/oracle và danh sách câu hỏi GV — đủ điều kiện để L01
   và L02 làm song song mà không hiểu khác contract.
2. **Rà soát vòng đời request** và chỉ ra chính xác các rủi ro kill/exit (rò rỉ slot,
   kill không cắt được `aio_wait`, không có owner), kèm thiết kế owner/orphan/cancel,
   ngân sách bộ nhớ và 6 kịch bản test cần viết.
3. **Hoàn thiện proposal kỹ thuật 3 trang** có kiến trúc, giới hạn, bằng chứng tuần 2
   được phân loại đúng, test/đo lường, rủi ro và lộ trình tuần 4–7, cùng nguồn sơ đồ
   và script tái lập PDF.

Các phần **chưa đạt** được ghi rõ: SCAN chưa hiện thực/kiểm chứng, kill/cancel chưa
triển khai, review chéo và câu trả lời GV còn Pending. Đây là các mục chuyển tiếp
sang L01/L02/G02 và tuần 4, không được tính là Done trong báo cáo này.
