# Kickoff tuần 1 — biên bản (cập nhật trạng thái thật)

> **Owner:** Hiếu (ghi biên bản). **Reviewer:** Hoàng. **Cập nhật:** 2026-10-30
> (W2-G01). Trạng thái: ✅ đã cập nhật theo bằng chứng merge của tuần 1 — nhóm
> **không tổ chức họp kickoff riêng**; các quyết định chốt qua trao đổi nhóm +
> PR/review trên repo. Mục nào chưa có bằng chứng vẫn để `PENDING (owner, hạn)`,
> không ghi như đã hoàn tất.

## 1. Thông tin

| Mục | Giá trị |
| --- | --- |
| Hình thức | Trao đổi nhóm + PR trên GitHub; không họp kickoff riêng (không có biên bản họp) |
| Thời gian tuần 1 | 19–25/10/2026; biên bản này cập nhật 30/10/2026 |
| Thành viên | Nguyễn Văn Hoàng (20233413), Phạm Quý Lợi (20233501), Phạm Trung Hiếu (20233402) |
| Base hiện tại | `origin/main` = `e8095001b2e64f361cd80b25e98a1bea5fd60888` (3 PR tuần 1 đã merge) |
| Pin xv6 | `f780d7850765d74cbdcd1fff4b822d8829f7c9bd` — **tạm thời**, GV chưa xác nhận tag chính thức |
| Contract tuần 2 | [`docs/week02/interface.md`](../week02/interface.md) (W2-G01, 30/10/2026) |

## 2. Phạm vi chốt trong tuần 1

**Làm:**

- Chốt tag/commit xv6 + câu hỏi GV; repo/tracker/design; ba máy build/boot.
- Baseline stock (CPUS=1/4, usertests -q, grind) + protocol đo.
- Bản đồ I/O/lock, buffer ownership/async API đề xuất, test plan ≥ 30 case.

**Chưa làm (để tuần 2 trở đi):**

- Chưa sửa kernel; chưa làm FCFS/SCAN/deadline/merging; chưa có số liệu benchmark chính thức.

## 3. Lịch làm việc

| Mốc | Ngày dự kiến | Trạng thái thật |
| --- | --- | --- |
| Kickoff | 19/10/2026 | ✅ chốt qua PR/kênh nhóm — không họp riêng |
| Check-in tuần 1 | 25/10/2026 | ✅ báo cáo tuần 1 đã xuất 25/10 (theo kế hoạch tuần 2, trang 1) |
| Proposal (tuần học phần 3) | PENDING | `PENDING` — cần GV xác nhận quy đổi tuần (owner: Lợi) |
| Midterm (tuần học phần 5) | PENDING | `PENDING` — chờ lịch học phần (owner: Lợi) |
| Code freeze (tuần học phần 8) | PENDING | `PENDING` — chờ lịch học phần (owner: Hoàng) |
| Final demo + nộp (tuần 9–10) | PENDING | `PENDING` — chờ lịch học phần (owner: Hiếu) |

## 4. Câu hỏi cần GV trả lời (T1-01 + câu hỏi phát sinh tuần 2)

| # | Câu hỏi | Người hỏi | Trạng thái | Trả lời / ghi chú |
| ---: | --- | --- | --- | --- |
| 1 | Tag/commit xv6-riscv chính thức của học phần? | Hoàng | PENDING (hạn hỏi 20/10, chưa trả lời) | Đang dùng pin tạm `f780d785`; API sleep mới khác sách cũ |
| 2 | Quy đổi tuần học phần ↔ tuần làm việc; ngày/giờ nộp tuần 10; lịch demo? | Lợi | PENDING (hạn hỏi 20/10) | Chưa có trả lời |
| 3 | API đọc bất đồng bộ: syscall user-space hay API kernel + chương trình minh hoạ? | Hiếu | PENDING (hạn 28/10 — chặn phạm vi W2) | Contract W2-G01 tạm chốt kernel API; Q3 quyết định có thêm syscall hay không |
| 4 | Định nghĩa SCAN giảng viên mong đợi (SCAN vs LOOK)? | Lợi | PENDING | Tuần 2 chỉ FCFS |
| 5 | Phạm vi merging được chấp nhận (chỉ read? có write fence?) | Hiếu | PENDING | Không merge trong tuần 2 |
| 6 | Trọng số rubric (Functionality/Testing/Measurement) — bảng rubric và spec lệch nhau | Hiếu | PENDING | Không tự suy ra trọng số |
| 7 | Có cần mở rộng virtqueue/NUM để chứng minh `max_inflight > 2`? | Hoàng | PENDING (mới, tuần 2) | Tuần 2 chỉ đo số thực tế, không hứa speedup |

> Chưa có câu trả lời: giữ `PENDING` + ghi hạn hỏi. Không tự suy đoán. Tổng hợp
> câu hỏi giữ tại PTO-7 (không tạo card hỏi GV trùng); xem
> [`docs/week02/interface.md`](../week02/interface.md) §9.1.

## 5. Trạng thái thật đầu tuần 2 (bằng chứng)

- `origin/main` = `e809500` sau 3 PR tuần 1 đã merge (`ad539ab`, `918d1d5`,
  `e809500`); base đã fetch ngày 30/10. Pin xv6 vẫn là `f780d785` tạm thời.
- Kernel **chưa** có module async/scheduler; các file mới `kernel/io_request.h`
  (contract) và module I01/H01/L01 **chưa** triển khai. Không có kết quả test
  async mới — mọi T01–T13 của tuần 2 là **NOT RUN** ở thời điểm này.
- Baseline: máy Lợi 6 PASS/0 FAIL tại `50e296a` (`results/baseline/2026-10-24_122154`),
  máy Hoàng 4/4 smoke + 2/2 test-fast tại `a0cfa2e`. Hồ sơ đã đọc **chưa có**
  baseline riêng của máy Hiếu — G02 phải bổ sung trên đúng base.
- Contract tuần 2 đã có bản đầu tiên: [`docs/week02/interface.md`](../week02/interface.md)
  + header [`kernel/io_request.h`](../../kernel/io_request.h); trạng thái
  **CHỜ Hoàng + Lợi review cùng revision** (chưa được duyệt).

## 6. Phân công tuần 1 (theo checklist 02)

| Việc (mã) | Owner | Reviewer | Deadline |
| --- | --- | --- | --- |
| T1-01 kickoff, biên bản, câu hỏi GV | Hiếu | Hoàng | 19/10 |
| T1-02 repo/private + quyền | Hoàng | Lợi | 20/10 |
| T1-03 Jira backlog/estimates/DoD | Lợi | Hiếu | 20/10 |
| T1-04 FigJam 3 trang + quyền GV | Hiếu | Hoàng | 20/10 |
| T1-05 version log 3 máy + README tái lập | Hiếu (điều phối) | Hoàng | 20/10 |
| T1-06 sơ đồ virtio/interrupt/descriptor | Hoàng | Hiếu | 21/10 |
| T1-07 NUM/chain, lock order, định nghĩa policy | Lợi | Hiếu | 21/10 |
| T1-08 buffer ownership, bread/bwrite/log, async API | Hiếu | Hoàng | 22/10 |
| T1-09 baseline CPUS=1/4 + protocol | Hoàng (dev), Hiếu (máy 2) | Lợi | 23–24/10 |
| T1-10 test plan ≥ 30 case + format kết quả | Hiếu | Lợi | 23/10 |
| T1-11 sprint tuần 2 (3 phần kernel, dependency, giờ) | Lợi | Hoàng | 24/10 |
| T1-12 báo cáo tuần 1 + review chéo | cả nhóm (Hiếu tổng hợp) | Hoàng | 25/10 |

> Tài liệu tương ứng từng việc: xem [`docs/week01/README.md`](README.md). Các
> mục đã có bằng chứng merge nằm trong 3 PR tuần 1; mục chưa có bằng chứng không
> được ghi `Done` chỉ vì có tài liệu.

## 7. Quyết định sơ bộ của nhóm

- Nhánh làm việc: `week1/<tên>` → tuần 2 đổi sang `week2/<tên>`; mọi thay đổi
  qua **PR có reviewer**, không push thẳng `main`.
- Commit message: `<type>(scope): mô tả` (vd `docs(week02): ...`); mỗi commit
  gắn issue khi có.
- Tuần 1 **không sửa kernel**; tuần 2 sửa kernel theo contract
  [`docs/week02/interface.md`](../week02/interface.md) sau khi contract được review.
- Lệnh chuẩn: `make env-check`, `make test-fast`, `make test`, `make check-text`.
- Không commit build artifact; không đưa thông tin mật (token) vào repo/log.

## 8. Việc còn mở sau biên bản này

| Việc | Owner | Hạn / trạng thái |
| --- | --- | --- |
| Review contract W2-G01 (buffer/lock/driver interface) | Hoàng, Lợi | trước khi merge module — PENDING |
| Đối chiếu PTO-4/7/9/10/11 trên Jira với bằng chứng repo, quyết định trạng thái thật | Lợi (có quyền tracker) | trước khi đóng W2-G01 — PENDING |
| Trả lời 7 câu hỏi GV (PTO-7) | theo owner ở §4 | PENDING |
| Bổ sung baseline máy Hiếu trên đúng base | Hiếu | W2-G02 |
