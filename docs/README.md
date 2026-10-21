# Tài liệu dự án ET4290 — 26128

| File | Nội dung |
| --- | --- |
| [`plan/01_Bao_cao_ke_hoach_26128.pdf`](plan/01_Bao_cao_ke_hoach_26128.pdf) | Bản kế hoạch gốc 10 tuần (đề tài 26128) |
| [`plan/02_Checklist_tuan_1.pdf`](plan/02_Checklist_tuan_1.pdf) · [`bản text`](plan/02_Checklist_tuan_1.txt) | Checklist tuần 1, bộ bằng chứng và DoD tuần 1 |
| [`environment.md`](environment.md) | Môi trường chuẩn trên Windows (WSL2 Ubuntu), toolchain, GDB, sự cố |
| [`run-on-ubuntu.md`](run-on-ubuntu.md) | **Runbook laptop Ubuntu**: clone → cài → env-check → boot → test → baseline |
| [`demo.md`](demo.md) | **Kịch bản demo cho GV**: check-in tuần 1 (10') và final 20' |
| [`architecture.md`](architecture.md) | Đường I/O stock xv6, thiết kế async + scheduler + merging |
| [`testing.md`](testing.md) | Chiến lược test, ma trận CPUS, oracle, benchmark, stress |
| [`baseline.md`](baseline.md) | Giao thức và kết quả baseline stock |
| [`upstream.md`](upstream.md) | Pin xv6-riscv, manifest, cách cập nhật tag |
| [`week1.md`](week1.md) | Việc tuần 1: môi trường, baseline, thiết kế, phân công |

## Quy ước

- Tài liệu viết bằng tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh.
- Mọi số liệu phải dẫn tới file bằng chứng trong `results/`.
- Khi interface/kernel thay đổi: cập nhật `architecture.md` cùng PR.
- Sơ đồ dùng Mermaid (render trên GitHub/VS Code) hoặc ảnh trong `docs/diagrams/`.
- Ảnh FigJam: dán URL bản chỉnh sửa ở đầu `architecture.md` khi có.
