# Tuần 3 — Hồ sơ phần việc của Hiếu (W3-G01, W3-I01, W3-I02)

Thư mục này chứa các đầu ra tuần 3 do **Phạm Trung Hiếu (20233402)** thực hiện theo
kế hoạch tuần 3 (02–08/11/2026), nhánh `week3/hieu-contract-lifecycle-proposal`,
base `origin/main` `49557bf671edb5ee4ccf6a2c3c452d32fd1f411e` (2026-11-04).

## 1. Tài liệu

| File | Card | Nội dung | Trạng thái |
| :--- | :---: | :--- | :---: |
| [`interface.md`](interface.md) | **W3-G01** (PTO-20) | Contract SCAN (D11–D20), phạm vi tuần 3, trace/oracle, câu hỏi GV, review | ✅ Đã soạn, review **PENDING** |
| [`lifecycle-review.md`](lifecycle-review.md) | **W3-I01** | Rà vòng đời request; bảng kill/exit; thiết kế owner/orphan/cancel; test cần viết | ✅ Thiết kế, review **PENDING**, code **chưa** |
| [`proposal.md`](proposal.md) · [`proposal.pdf`](proposal.pdf) | **W3-I02** | Proposal kỹ thuật 2–3 trang: kiến trúc, FCFS/SCAN, bằng chứng, test, rủi ro, lộ trình | ✅ Bản nháp v1.0, review **PENDING** |
| [`report-hieu.md`](report-hieu.md) · [`report-hieu.pdf`](report-hieu.pdf) | Báo cáo | Báo cáo nhiệm vụ hoàn thành của Hiếu (G01/I01/I02) | ✅ Snapshot 2026-11-07 |
| [`diagrams/`](diagrams/) | W3-I02 | Nguồn + SVG pipeline/SCAN | ✅ |
| `results/week03/hieu-contract-lifecycle-2026-11-07/` | — | Log base build/test-fast/check-text/link-check | ✅ |

## 2. Base revision và môi trường

- Base: `49557bf671edb5ee4ccf6a2c3c452d32fd1f411e` — main sau PR #5 `83745b6`
  (READ thật tuần 2) và PR #6 `49557bf` (FCFS/Lợi), merge ngày 2026-11-04.
- Pin xv6: `f780d7850765d74cbdcd1fff4b822d8829f7c9bd` (tạm thời, PTO-7/Q1).
- Môi trường kiểm chứng: Windows 11 + WSL2 Ubuntu 24.04, 6 CPU; `riscv64-linux-gnu-gcc`
  13.3.0; QEMU 8.2.2; Python 3.12.3; GNU Make 4.3.
- Snapshot tài liệu: 2026-11-07 (kế hoạch tuần 3 lập 07/11, hạn chốt 08/11).

## 3. Sinh lại PDF

PDF được sinh từ Markdown bằng `pandoc` + Chrome headless (không sửa tay PDF):

```powershell
# Windows (máy dùng để nghiệm thu):
powershell -ExecutionPolicy Bypass -File docs\week03\tools\build_pdf.ps1 -All
```

- Script + CSS: [`tools/build_pdf.ps1`](tools/build_pdf.ps1), [`tools/print.css`](tools/print.css).
- Sinh lại sơ đồ trước khi build PDF nếu sửa `diagrams/make_diagrams.py`:
  `python3 docs/week03/diagrams/make_diagrams.py`.
- PDF là **đầu ra dẫn xuất**; nguồn sự thật là file `.md`/`.py` trong repo.

## 4. Phạm vi và giới hạn (đọc trước khi nghiệm thu)

- Tuần 3 **chưa** triển khai SCAN (thuộc W3-L01/L02) và **chưa** triển khai
  kill/cancel (W3-I01 chỉ thiết kế). Không có kết quả SCAN/kill-cancel nào được ghi PASS.
- Các tài liệu này **chưa** được Hoàng/Lợi review tại revision hiện tại; mọi bảng
  review ghi **PENDING**.
- Không có phê duyệt nào của giảng viên; các quyết định phụ thuộc GV giữ **PENDING**
  (PTO-7/Q1–Q8).
- Chi tiết bằng chứng/không bằng chứng: [`report-hieu.md`](report-hieu.md) §4–§6.
