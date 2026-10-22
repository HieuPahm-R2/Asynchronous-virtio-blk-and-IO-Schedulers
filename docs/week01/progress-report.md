# Báo cáo tiến độ tuần 1 — mẫu

> **Owner:** Hiếu (tổng hợp) + cả nhóm điền phần của mình.
> Xuất sang `Spec/Progress Report template.docx` để nộp nếu GV yêu cầu; giữ bản
> .md này trong repo làm bản gốc có thể so sánh diff.
>
> Quy tắc: **summary 200–300 từ**; mỗi mục Completed phải kèm bằng chứng
> (commit/PR/file/log); không lấy tỷ lệ trong báo cáo mẫu làm tỷ lệ của nhóm.

## 1. Thông tin

| | |
| --- | --- |
| Tuần | Tuần 1 (19–25/10/2026) |
| Đề tài | 26128 — Asynchronous virtio-blk and I/O schedulers on xv6-riscv |
| Nhóm | Hoàng (20233413), Lợi (20233501), Hiếu (20233402) |
| Project commit | TODO (ghi hash cuối tuần) |
| xv6 pin | TODO (`.xv6-commit`) |

## 2. Summary (200–300 từ)

TODO — viết sau khi xong các mục dưới. Gợi ý nội dung: đã chốt phạm vi gì; môi
trường 3 máy; baseline stock; bản đồ I/O/ownership; test plan; vấn đề còn chờ GV;
kế hoạch tuần 2.

## 3. Completed (có bằng chứng)

| Việc | Người | Bằng chứng (commit/PR/file) |
| --- | --- | --- |
| Môi trường WSL2 + toolchain + QEMU, `make env-check` PASS | Hoàng/Base | `docs/environment.md`, commit TODO |
| Baseline stock 6/6 PASS (usertests -q CPUS=1/4, grind 60s ×2) | Hoàng (máy 1) | `results/baseline/2026-10-19_222935/` |
| Harness test QEMU + case stock | Base | `tests/`, commit TODO |
| Bản đồ I/O + thiết kế async/policy (bản nháp) | Hoàng/Lợi/Hiếu | `docs/architecture.md` |
| Test plan khung ≥ 30 case | Hiếu | `docs/week01/test-plan.md` |
| Version log máy Hiếu/Hoàng/Lợi | Hiếu | `docs/week01/environment.md` |
| FigJam 3 trang + quyền GV | Hiếu | `docs/week01/kickoff.md` mục URL |
| Baseline tái lập trên máy thứ 2 | Hiếu | `results/baseline/<ts>/` |
| TODO | | |

## 4. In progress

| Việc | Người | Trạng thái | Dự kiến xong |
| --- | --- | --- | --- |
| Tag xv6 chính thức + câu hỏi GV | Hoàng | PENDING trả lời | trước 20/10 |
| Jira backlog/estimate/DoD | Lợi | TODO | 20/10 |
| Bản đồ descriptor/interrupt chi tiết | Hoàng | TODO | 21/10 |
| Định nghĩa policy + lock order | Lợi | TODO | 21/10 |
| API async đề xuất (chi tiết buffer lifetime) | Hiếu | TODO | 22/10 |

## 5. Blocked

| Việc | Lý do | Owner | Cần gì |
| --- | --- | --- | --- |
| Chốt tag/API/SCAN với GV | chưa có phản hồi | Hoàng | GV trả lời |
| Quyền đọc repo/tracker/design của GV | chưa mời/quyền | Hoàng/Lợi/Hiếu | xác nhận GV mở được |

## 6. TODO tuần 1: kế hoạch vs thực tế

| Task (checklist 02) | Kế hoạch | Thực tế | Ghi chú |
| --- | --- | --- | --- |
| T1-01 kickoff/biên bản/câu hỏi GV | 19/10 | TODO | |
| T1-02 repo private + quyền | 20/10 | TODO | |
| T1-03 Jira backlog | 20/10 | TODO | |
| T1-04 FigJam | 20/10 | TODO | |
| T1-05 version log 3 máy | 20/10 | TODO | |
| T1-06 map virtio/interrupt | 21/10 | TODO | |
| T1-07 NUM/chain/lock/policy | 21/10 | TODO | |
| T1-08 buffer/async ownership | 22/10 | TODO | |
| T1-09 baseline CPUS=1/4 | 23–24/10 | TODO | |
| T1-10 test plan ≥ 30 case | 23/10 | TODO | |
| T1-11 sprint tuần 2 | 24/10 | TODO | |
| T1-12 báo cáo tuần | 25/10 | TODO | |

## 7. Kế hoạch tuần 2 (3 phần kernel + dependency)

| Phần | Owner | Reviewer | Giờ dự kiến | Phụ thuộc |
| --- | --- | --- | ---: | --- |
| Request pool + submit/wait + FCFS | Lợi | Hiếu | TODO | chốt request struct/lock |
| Descriptor lifecycle + interrupt/completion | Hoàng | Lợi | TODO | chốt tag/API sleep |
| Async API + buffer lifetime + counters | Hiếu | Hoàng | TODO | chốt API với GV |
| Harness: case async/policy đầu tiên | Hiếu | Lợi | TODO | có code |

## 8. Đóng góp cá nhân

| Thành viên | Việc đã làm | Bằng chứng |
| --- | --- | --- |
| Hoàng | TODO | TODO |
| Lợi | TODO | TODO |
| Hiếu | TODO | TODO |

## 9. Commit / PR / issue links

- Commit: TODO
- PR: TODO
- Issue: TODO

## 10. Tự đánh giá theo DoD tuần 1

- [ ] Công cụ + quyền đọc đủ
- [ ] Cả ba build/boot
- [ ] Baseline + issue cho lỗi (nếu có)
- [ ] Bản đồ I/O/lock
- [ ] Design sơ bộ + câu hỏi chưa chốt
- [ ] Backlog tuần 2 có owner/reviewer
- [ ] Báo cáo tuần từ bằng chứng
