# W3-G01/I01/I02 — bằng chứng kiểm chứng phần việc của Hiếu (2026-11-07)

**Card:** W3-G01 (PTO-20) chốt contract SCAN + phạm vi proposal · W3-I01 rà lifecycle
+ thiết kế kill/cancel · W3-I02 proposal kỹ thuật.
**Owner:** Phạm Trung Hiếu (20233402). **Reviewer:** Nguyễn Văn Hoàng, Phạm Quý Lợi
(**chưa review — PENDING**).
**Base chạy:** `49557bf671edb5ee4ccf6a2c3c452d32fd1f411e` (origin/main, 2026-11-04).
**Commit nội dung được kiểm chứng:** `9790ded08492af9bad03ddbff8d025d820dd2e95`.
**Pin xv6:** `f780d7850765d74cbdcd1fff4b822d8829f7c9bd` (tạm, GV chưa xác nhận — PTO-7/Q1).
**Nhánh:** `week3/hieu-contract-lifecycle-proposal`.
**Máy:** Windows 11 + WSL2 Ubuntu 24.04, 6 CPU, 7,9 GB RAM; QEMU 8.2.2;
riscv64-linux-gnu-gcc 13.3.0; Python 3.12.3; GNU Make 4.3. Thời điểm: 2026-11-07T16:30+07:00.

## Đầu ra của card

| File | Nội dung |
| --- | --- |
| [`docs/week03/interface.md`](../../../docs/week03/interface.md) | Contract SCAN D11–D20, phạm vi tuần 3, trace/oracle, PTO-7, bảng review |
| [`docs/week03/lifecycle-review.md`](../../../docs/week03/lifecycle-review.md) | Rà soát kill/exit K1–K10, thiết kế owner/orphan/cancel, test K1–K6 |
| [`docs/week03/proposal.md`](../../../docs/week03/proposal.md) + `proposal.pdf` | Proposal 3 trang + nguồn + sơ đồ + script sinh PDF |
| [`docs/week03/report-hieu.md`](../../../docs/week03/report-hieu.md) + `report-hieu.pdf` | Báo cáo nhiệm vụ hoàn thành của Hiếu |
| [`kernel/io_request.h`](../../../kernel/io_request.h) | Khai báo kiểu/prototype SCAN (contract-only, chưa hiện thực) |
| [`docs/architecture.md`](../../../docs/architecture.md) | Cập nhật §2.4/§2.9 theo contract tuần 3 |

## Kết quả kiểm tra

| # | Kiểm tra | Kết quả | Log |
| ---: | :--- | :---: | :--- |
| 1 | Build production `make -j4 kernel/kernel fs.img` | **PASS** (exit 0) | [build.log](logs/build.log) |
| 2 | `make test-fast` (boot CPUS=1 + shell/fs CPUS=3) | **PASS 2/2** | [test-fast.log](logs/test-fast.log) |
| 3 | `make test-io`: kernel selftest pool/handle T02/T03/T04/T11 | **PASS** | [test-io.log](logs/test-io.log) |
| 4 | `make test-io`: process-context T05/T04/T06a/T06b/T03/T11 | **PASS** | [io-selftest.log](logs/io-selftest.log) |
| 5 | Restore production build sau test-io | **PASS** | [restore-production-build.log](logs/restore-production-build.log) |
| 6 | `make test-fast` trên production đã restore | **PASS 2/2** | [test-fast-post-restore.log](logs/test-fast-post-restore.log) |
| 7 | `make check-text` (UTF-8/mojibake/CRLF) | **PASS** — toàn repo sạch | [check-text.log](logs/check-text.log) |
| 8 | `git diff --cached --check` (whitespace) | **PASS** (sau khi loại trừ log bằng `.gitattributes`) | [diff-check.log](logs/diff-check.log) |
| 9 | Link tương đối trong `docs/week03/` | **PASS** | [link-check.log](logs/link-check.log) |
| 10 | `proposal.pdf`: 2–3 trang + marker + nhúng Hình 1 | **PASS — 3 trang** | [pdf-check.log](logs/pdf-check.log) |
| 11 | `report-hieu.pdf` sinh từ Markdown | **PASS — 6 trang** | [pdf-check.log](logs/pdf-check.log) |

Artifact hash: `kernel/kernel` sha256 `A3AC643E3E2E19F53E02BBB07682A6EC9404EAE45EECD952B0F9F9F510C3914E`;
`fs.img` sha256 `E4182B6A43B71DC7CCD2B917389701750CA50967F2FE23CE4795E8814013280B`
(xem [env.txt](logs/env.txt)).

Dòng `IO-SELFTEST: PASS` + `IO-USER-TEST: PASS` là log serial QEMU trong
`results/local/io-selftest.log`, được sao chép nguyên văn vào
[`logs/io-selftest.log`](logs/io-selftest.log), không nằm trong output make.

## NOT RUN (ghi đúng trạng thái)

- **SCAN mock/oracle 8 nhóm + 2 mutant**: thuộc W3-L01/L02; chưa có code SCAN trên nhánh.
- **SCAN READ thật FCFS/SCAN CPU1/4**: thuộc G02; phụ thuộc L01/L02.
- **Kill/cancel K1–K6**: W3-I01 chỉ thiết kế, chưa triển khai code.
- **Production regression 6 case** (`usertests -q`, `grind 60s` CPU1/4): thuộc G02;
  `make test-fast` 2/2 chỉ là smoke, **không** thay bộ nghiệm thu G02.
- **Review Hoàng/Lợi**: PENDING trên revision này.
- **Câu trả lời GV Q1–Q8 (PTO-7)**: PENDING.
- **Hiệu năng/seek vật lý**: không đo; QEMU không mô phỏng chuyển đầu từ.

## Ghi chú về revision

Các log trên chạy trên cây làm việc sạch tại commit `9790ded` (sau commit này chỉ bổ
sung báo cáo/PDF/evidence; `kernel/`, header và các tài liệu contract không đổi).
Sau khi commit cuối cùng của nhánh được tạo, có thể xác nhận không đổi code bằng:

```bash
git diff --stat 9790ded..HEAD -- kernel/ docs/week03/interface.md docs/week03/lifecycle-review.md
```

## Cách tái lập

```bash
git fetch origin
git switch -c week3/repro origin/main
git rev-parse HEAD                     # 49557bf...
make clean && make -j"$(nproc)" kernel/kernel fs.img
make test-fast
make test-io                           # xem thêm results/local/io-selftest.log
make clean && make -j"$(nproc)" kernel/kernel fs.img
make test-fast
make check-text && git diff --check
python3 docs/week03/diagrams/make_diagrams.py
```

```powershell
powershell -ExecutionPolicy Bypass -File docs\week03\tools\build_pdf.ps1
```

## Giới hạn

Đây là bằng chứng cho **base build + contract/header + tài liệu**, không phải bằng chứng
SCAN/kill-cancel đã chạy. Không cộng dồn các lượt boot thành số test độc lập; mock/timer
không phải READ thật; `max_inflight = 2` là số chain đã publish, không phải bằng chứng
DMA song song. Card chỉ được đóng khi reviewer xác nhận trên cùng revision.
