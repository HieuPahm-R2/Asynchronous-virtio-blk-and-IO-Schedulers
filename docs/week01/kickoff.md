# Kickoff tuần 1 — biên bản

> **Owner:** Hiếu (ghi biên bản). **Trạng thái:** 📝 CHƯA HỌP — cập nhật ngay sau
> buổi kickoff. Thay mọi `PENDING` bằng thông tin thật hoặc `PENDING (owner, hạn)`.

## 1. Thông tin buổi họp

| | |
| --- | --- |
| Thời gian | PENDING (dự kiến 19/10/2026) |
| Hình thức | PENDING (offline / Discord / Google Meet) |
| Tham dự | Nguyễn Văn Hoàng (20233413), Phạm Qúy Lợi (20233501), Phạm Trung Hiếu (20233402) |
| Người ghi biên bản | Hiếu |
| Tài liệu dùng | `01_Bao_cao_ke_hoach_26128.pdf`, `02_Checklist_tuan_1.pdf` |

## 2. Phạm vi chốt trong tuần 1

**Làm:**

- Chốt tag/commit xv6 + câu hỏi GV; repo/tracker/design; ba máy build/boot.
- Baseline stock (CPUS=1/4, usertests -q, grind) + protocol đo.
- Bản đồ I/O/lock, buffer ownership/async API đề xuất, test plan ≥ 30 case.

**Chưa làm (để tuần 2 trở đi):**

- Chưa sửa kernel; chưa làm FCFS/SCAN/deadline/merging; chưa có số liệu benchmark chính thức.

## 3. Lịch làm việc

| Mốc | Ngày dự kiến | Ghi chú |
| --- | --- | --- |
| Kickoff | 19/10/2026 | PENDING |
| Check-in tuần 1 | 25/10/2026 | 10 phút, theo `docs/demo.md` mục 2 |
| Proposal (tuần học phần 3) | PENDING | cần GV xác nhận quy đổi tuần |
| Midterm (tuần học phần 5) | PENDING | |
| Code freeze (tuần học phần 8) | PENDING | |
| Final demo + nộp (tuần 9–10) | PENDING | |

## 4. Câu hỏi cần GV trả lời (T1-01)

| # | Câu hỏi | Người hỏi | Trạng thái | Trả lời / ghi chú |
| ---: | --- | --- | --- | --- |
| 1 | Tag/commit xv6-riscv chính thức của học phần? | Hoàng | PENDING | |
| 2 | Quy đổi tuần học phần ↔ tuần làm việc; ngày/giờ nộp tuần 10; lịch demo? | Lợi | PENDING | |
| 3 | API đọc bất đồng bộ: syscall user-space hay API kernel + chương trình minh hoạ? | Hiếu | PENDING | |
| 4 | Định nghĩa SCAN giảng viên mong đợi (SCAN vs LOOK)? | Lợi | PENDING | |
| 5 | Phạm vi merging được chấp nhận (chỉ read? có write fence?) | Hiếu | PENDING | |
| 6 | Trọng số rubric (Functionality/Testing/Measurement) — bảng rubric và spec lệch nhau | Hiếu | PENDING | |
| 7 | Công cụ tracker: Jira mặc định; Trello/GitHub Projects có được chấp thuận? | Lợi | PENDING | |

> Chưa có câu trả lời: giữ `PENDING` + ghi hạn hỏi (dự kiến 20/10). Không tự suy đoán.

## 5. URL công cụ (T1-02/T1-03/T1-04)

| Công cụ | URL | Quyền của GV | Trạng thái |
| --- | --- | --- | --- |
| Repo GitHub (private) | PENDING | Cần mời GV (`admin`) | PENDING |
| Jira / board | PENDING | Cần mời GV | PENDING |
| FigJam / Figma | PENDING | Cần share "Anyone with link can view" | PENDING |

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

## 7. Quyết định sơ bộ của nhóm

- Nhánh làm việc: `week1/<tên>`; mọi thay đổi qua **PR có reviewer**, không push thẳng `main`.
- Commit message: `<type>(scope): mô tả` (vd `docs(week01): ...`); mỗi commit gắn issue khi có.
- Tuần 1 **không sửa kernel**; mọi thay đổi source kernel phải chờ chốt tag + design review.
- Lệnh chuẩn: `make env-check`, `make test-fast`, `make test`, `make check-text`.
- Không commit build artifact; không đưa thông tin mật (token) vào repo/log.

## 8. Rủi ro & hành động

| Rủi ro | Tín hiệu | Hành động | Owner |
| --- | --- | --- | --- |
| Chưa có tag GV | quá 20/10 chưa trả lời | tiếp tục pin tạm, ghi PENDING, nhắc GV | Hoàng |
| Máy thứ 2/3 build lỗi | `make env-check` FAIL | gửi output, cùng sửa môi trường | Hiếu |
| Không có quyền đọc GV | GV chưa mở được repo | kiểm tra lại invite + link | Hoàng |
| Dồn việc cuối tuần | ngày 24–25/10 còn nhiều task | cắt phần stretch FigJam, ưu tiên baseline/report | cả nhóm |

## 9. Hành động sau họp

| Việc | Owner | Hạn | Trạng thái |
| --- | --- | --- | --- |
| Ghi biên bản + tạo issue T1-01..T1-12 | Hiếu | 19/10 | PENDING |
| Tạo repo/Jira/FigJam + mời GV | Hoàng/Lợi/Hiếu | 20/10 | PENDING |
| PENDING | | | |
