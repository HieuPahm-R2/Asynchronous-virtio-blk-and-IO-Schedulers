# Tuần 1 — chuẩn bị nền tảng

Nguồn: kế hoạch 26128 (mục 8). Tuần 1 tính từ thứ Hai **19/10/2026**; mục
tiêu **30 giờ làm việc của cả nhóm** (kể cả họp/review). Đây là checklist của
nhóm — trạng thái ghi theo thực tế, không lấy kế hoạch làm thành tích.

## Việc theo ngày

| Ngày | Việc | Đầu ra kiểm chứng được | Trạng thái |
| --- | --- | --- | --- |
| 1 · 19/10 | Kickoff, chốt phạm vi/owner; xác nhận lịch/tag/API | Biên bản, bảng câu hỏi, task tuần 1 | ⏳ chưa có biên bản |
| 2 · 20/10 | Cài môi trường, clone tag, tạo công cụ nhóm | Version log; ba máy boot; URL repo/Jira/FigJam | 🟡 máy dev đã sẵn sàng (`make env-check`) |
| 3 · 21/10 | Đọc đường I/O và khóa, thử baseline | Bản đồ file/hàm; request outstanding & giới hạn descriptor | 🟡 có bản đồ ban đầu (`docs/architecture.md`), baseline đã chạy |
| 4 · 22/10 | Thiết kế lifecycle, policy, ownership | Sơ đồ kiến trúc/state/sequence; quyết định lock/API sơ bộ | 🟡 có bản nháp (`docs/architecture.md`) |
| 5 · 23/10 | Baseline regression, chuẩn bị phép đo | Log CPUS=1/4; test matrix; format dữ liệu thô | ✅ baseline sạch 6/6 PASS tại `results/baseline/2026-10-19_222935/` |
| 6 · 24/10 | Review thiết kế, chia nhỏ sprint 2 | Backlog assignee/estimate/DoD; PR ghi chú; rủi ro | ⏳ cần họp nhóm |
| 7 · 25/10 | Review, retrospective, báo cáo tuần | Báo cáo thực tế, commit/log/issue links, TODO tuần 2 | ⏳ |

## Checklist nghiệm thu cuối tuần (từ kế hoạch)

1. Cả ba dùng đúng commit gốc, build/boot được; môi trường mô tả để tái lập.
   - Repo có `.xv6-commit`, `docs/environment.md`, script cài + `make env-check`.
   - ⏳ Chờ tag chính thức của giảng viên để chốt (đang dùng pin tạm).
2. Có repo private, tracker và design; kiểm tra giảng viên đọc được trước mốc
   tuần học phần 2. ⏳ (cần URL Jira/FigJam thật)
3. Có bản đồ bread/bwrite → driver → interrupt → wakeup, mô tả cả đường
   descriptor hết. 🟡 `docs/architecture.md` mục 1.
4. Có baseline stock usertests và grind theo protocol đã ghi; lỗi phải có
   issue + log. ✅ `results/baseline/2026-10-19_222935/` (6/6 PASS, `dirty: false`),
   tổng hợp `docs/baseline.md`; `grind` mới 60 giây ×2 (smoke), R09 vẫn còn nợ.
5. Có request lifecycle, ownership, chính sách ordering và quyết định
   async kernel/user cần chốt. 🟡 lifecycle + ownership trong
   `docs/architecture.md`; async kernel/user ⏳ chờ GV.
6. Có backlog toàn dự án; task tuần 2 vừa sức; mỗi người có phần kernel cụ thể.
   ⏳ cần tạo task trên tracker (xem phân công trong README).
7. Có kế hoạch ≥ 30 ca test, ma trận CPU, stress 30 phút, protocol benchmark.
   🟡 `docs/testing.md`.
8. Có báo cáo tuần 1 phân biệt Completed/In progress/Blocked, không lấy tỷ lệ
   trong báo cáo mẫu làm tỷ lệ của nhóm. ⏳

## Câu hỏi phải chốt với giảng viên (ghi pending nếu chưa trả lời)

- [ ] Tag/commit xv6 chính thức của học phần
- [ ] Quy đổi tuần học phần ↔ tuần làm việc; ngày/giờ nộp tuần 10; lịch demo
- [ ] API đọc bất đồng bộ: syscall user-space hay API kernel + chương trình minh hoạ?
- [ ] Định nghĩa SCAN giảng viên mong đợi (SCAN vs LOOK); phạm vi merging
- [ ] Trọng số rubric (spec ghi Functionality 30 + Testing 20 nhưng bảng rubric
      ghi Testing 5 + Measurement 5) — không tự suy ra
- [ ] Jira/Trello + FigJam: URL và quyền đọc của giảng viên

## Nội dung check-in 10 phút (gợi ý)

1 phút mục tiêu/phạm vi · 2 phút baseline & môi trường · 3 phút sơ đồ
submit/completion + rủi ro · 2 phút phân công · 2 phút blocker/câu hỏi/kế hoạch
tuần sau. Mỗi người giải thích phần mình khảo sát và chỉ ra bằng chứng.

## Đã làm trong repo này (bằng chứng)

- Source xv6-riscv pin + manifest: `.xv6-commit`, `.xv6-files`.
- Môi trường WSL2 Ubuntu 24.04 + toolchain + QEMU; script tái lập:
  `scripts/setup-env.sh`, `scripts/wsl/`, kiểm tra: `make env-check`.
- Build một lệnh + boot: `make`, `make qemu`.
- Harness test một lệnh (PASS/FAIL từng case, lưu log/meta):
  `tests/runner.py`, `tests/cases/stock.py`.
- Baseline stock CPUS=1/4 + usertests -q + grind smoke:
  `results/baseline/<timestamp>/`, tổng hợp `docs/baseline.md`.
- Bản đồ kiến trúc + state machine + thiết kế đề xuất: `docs/architecture.md`.
- Khung test/benchmark/stress: `docs/testing.md`.
- Runbook máy Ubuntu: `docs/run-on-ubuntu.md`; kịch bản demo: `docs/demo.md`,
  lệnh `make demo`.
- Checklist tuần 1 gốc: `docs/plan/02_Checklist_tuan_1.pdf`.

## Đối chiếu bộ bằng chứng với checklist 02

Checklist 02 đề xuất cấu trúc `docs/week01/...` và `results/baseline/...`. Repo
hiện có **hub tuần 1 + template điền dần** tại [`week01/README.md`](week01/README.md),
kèm hướng dẫn riêng cho từng người (bắt đầu từ [`week01/hieu.md`](week01/hieu.md)):

| Checklist 02 (đề xuất) | File hiện tại | Trạng thái |
| --- | --- | --- |
| `docs/week01/kickoff.md` | [`week01/kickoff.md`](week01/kickoff.md) | 📝 template — họp xong điền |
| `docs/week01/environment.md` | [`week01/environment.md`](week01/environment.md) | 📝 có dòng máy dev, chờ 3 máy |
| `docs/week01/io-path.md` | [`week01/io-path.md`](week01/io-path.md) | 📝 Hoàng điền |
| `docs/week01/decisions.md` | [`week01/decisions.md`](week01/decisions.md) | 📝 Hiếu/Lợi điền |
| `docs/week01/test-plan.md` | [`week01/test-plan.md`](week01/test-plan.md) | 📝 Hiếu điền (T1-10) |
| `docs/week01/progress-report.docx` | [`week01/progress-report.md`](week01/progress-report.md) → xuất .docx | 📝 template |
| `results/baseline/<run-id>/metadata.json` | `results/baseline/2026-10-19_222935/meta.json` | ✅ (khác tên) |
| `results/baseline/<run-id>/serial.log` | `results/baseline/2026-10-19_222935/logs/<case>.log` | ✅ (tách theo case) |
| `results/baseline/<run-id>/summary.txt` | `results/baseline/2026-10-19_222935/summary.md` | ✅ (khác định dạng) |

T1-09 (log baseline CPUS=1/4, usertests, grind + protocol timeout/termination):
đã có trên máy dev — xem [`baseline.md`](baseline.md); máy thứ 2/3 tự chạy. T1-12
(báo cáo tuần theo mẫu) dùng template ở trên.

## Việc tiếp theo tuần 2

- [ ] Spike counter `max_inflight` để đo baseline chính xác (nhánh riêng, review).
- [ ] Chốt request struct + state machine + lock order (review chéo).
- [ ] Triển khai request pool + submit/wait + FCFS trước; giữ wrapper đồng bộ.
- [ ] Mỗi người bắt đầu module kernel của mình (xem bảng phân công README).
- [ ] Tạo task trên tracker với owner/reviewer/estimate/DoD.
