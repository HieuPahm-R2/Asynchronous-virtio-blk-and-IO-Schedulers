# Tuần 1 — hướng dẫn thực hiện

Checklist gốc bạn cần bám: [`../plan/02_Checklist_tuan_1.pdf`](../plan/02_Checklist_tuan_1.pdf)
(hoặc [bản text](../plan/02_Checklist_tuan_1.txt)); bối cảnh: [kế hoạch 10 tuần](../plan/01_Bao_cao_ke_hoach_26128.pdf).

Repo base đã có sẵn môi trường + baseline + harness, nên tuần 1 chủ yếu là
**chạy lại trên máy từng người, ghi bằng chứng, vẽ sơ đồ và chốt câu hỏi GV** —
không phải code kernel.

## Hồ sơ tuần 1 trong repo (checklist 02 yêu cầu)

| Checklist 02 | File trong repo | Owner | Trạng thái |
| --- | --- | --- | --- |
| `docs/week01/kickoff.md` | [kickoff.md](kickoff.md) | **Hiếu** (ghi biên bản) | 📝 template — chờ họp |
| `docs/week01/environment.md` | [environment.md](environment.md) | **Hiếu** (điều phối 3 máy) | 📝 template + dòng máy dev |
| `docs/week01/io-path.md` | [io-path.md](io-path.md) | Hoàng | ✅ đã đối chiếu code + sequence; chờ Hiếu review (23/10) |
| `docs/week01/decisions.md` | [decisions.md](decisions.md) | **Hiếu** (T1-08) + Lợi | ✅ §1–§4 (Hiếu, 21/10) · 📝 §5 (Lợi) · 📝 §7 review (Hoàng) |
| `docs/week01/test-plan.md` | [test-plan.md](test-plan.md) | **Hiếu** (T1-10) | 📝 template |
| `docs/week01/progress-report.docx` | [progress-report.md](progress-report.md) → xuất .docx | cả nhóm | 📝 template |
| `results/baseline/<run-id>/metadata.json` | `results/baseline/2026-10-19_222935/meta.json` | máy dev | ✅ đã có |
| `results/baseline/<run-id>/serial.log` | `.../logs/<case>.log` | máy dev | ✅ đã có |
| `results/baseline/<run-id>/summary.txt` | `.../summary.md` | máy dev | ✅ đã có |

## Phân bổ 10 giờ/người (trích checklist 02) — phần của Hiếu

| Ngày | Giờ | Việc | Kết quả cuối ngày |
| --- | ---: | --- | --- |
| 19/10 | 1h | kickoff + **ghi biên bản** | [kickoff.md](kickoff.md) có phạm vi, câu hỏi GV, owner |
| 20/10 | 2h | môi trường + **FigJam** | [environment.md](environment.md) đủ 3 máy; 3 trang FigJam + URL |
| 21/10 | 2h | đọc `bread/bwrite/log` | [decisions.md](decisions.md) mục buffer ownership + write path |
| 22/10 | 1h | async API + ownership | decisions.md mục completion-before-wait + API |
| 23/10 | 1h | test matrix/protocol | [test-plan.md](test-plan.md) khung ≥ 30 case |
| 24/10 | 2h | **tái lập + protocol đo** | baseline máy Hiếu + protocol trong test-plan |
| 25/10 | 1h | review chéo + **báo cáo tuần** | [progress-report.md](progress-report.md) + PR |

Hướng dẫn chi tiết từng bước cho Hiếu: **[hieu.md](hieu.md)**.

## Definition of Done tuần 1 (từ checklist)

Đạt khi: có công cụ/quyền đọc; **cả ba build/boot**; có baseline + issue cho lỗi;
có bản đồ I/O/lock; có design sơ bộ và câu hỏi chưa chốt; backlog tuần 2 đã giao
owner/reviewer; có báo cáo tuần từ bằng chứng. Mục chưa đạt phải ghi owner,
nguyên nhân, ngày xử lý — **không đánh dấu Done cho đủ hình thức**.

## Quy ước nộp bằng chứng

- Mọi tuyên bố "đã xong" phải kèm: commit hash / PR / đường dẫn file / log.
- Việc chưa làm ghi **NOT RUN** hoặc **PENDING**, không điền số liệu giả.
- Báo cáo tuần dùng summary 200–300 từ; phân biệt Completed / In progress / Blocked.

## Phần việc Hoàng ngày 23/10/2026

[Hướng dẫn thao tác và báo cáo](hoang.md), [bản đồ I/O](io-path.md),
[thiết kế async](async-design.md). Máy Hoàng build/boot PASS, smoke đọc ghi
và reboot CPUS=1/4 4/4 PASS; stock-fast 2/2 PASS. Kernel chưa thay đổi;
async chỉ ở mức thiết kế; reviewer và tag GV còn pending; chưa commit.

Sơ đồ có bản draw.io chỉnh sửa được: [virtio-submit-complete.drawio](diagrams/virtio-submit-complete.drawio), gồm hai trang stock và async đề xuất.

Bản draw.io đã đồng bộ theo link của nhóm; xem [nguồn sơ đồ](diagrams/README.md),
[bằng chứng có thể commit](../../results/week01/hoang-2026-10-23/README.md),
[báo cáo PDF](reports/hoang-week01-2026-10-23.pdf) và
[hướng dẫn commit/push](git-workflow-hoang.md).
