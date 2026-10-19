# Thư mục kết quả đo

| Thư mục | Nội dung | Commit vào git? |
| --- | --- | --- |
| `results/baseline/<timestamp>/` | Baseline stock xv6 (bằng chứng tuần 1) | ✅ có |
| `results/bench/<timestamp>/` | Benchmark scheduler/async (tuần 7+) | ✅ có (dữ liệu thô + tổng hợp) |
| `results/stress/<timestamp>/` | Log stress ≥ 30 phút | ✅ có (log nén nếu lớn) |
| `results/local/` | Chạy thử hằng ngày, log tạm | ❌ gitignore |

## Format một lần chạy

`make baseline` sinh ra:

```
results/baseline/2026-10-19_220000/
├── build.log          # log build sạch (make clean + make -j)
├── meta.json          # schema 1: commit, xv6 pin, host, toolchain, từng case
├── summary.md         # bảng PASS/FAIL + thời gian
├── NOTES.md           # ghi chú lần chạy
└── logs/
    ├── boot-smoke.log
    ├── usertests-quick-cpus1.log
    └── ...
```

`meta.json` (rút gọn):

```json
{
  "schema": 1,
  "started_at": "2026-10-19T22:00:00+07:00",
  "git": { "commit": "…", "branch": "main", "dirty": false },
  "xv6_pin": "f780d785…",
  "host": { "platform": "Linux-5.15…", "wsl": true, "cpus": 6, "mem_total_mb": 8000 },
  "toolchain": { "riscv_gcc": ["…"], "qemu": ["…"], "make": ["…"], "python": "3.12.3" },
  "selection": { "cases": ["…"], "cpus": [1, 4] },
  "results": [
    { "name": "usertests-quick-cpus1", "cpus": 1, "status": "PASS",
      "duration_s": 123.4, "reason": "", "log": "logs/usertests-quick-cpus1.log" }
  ]
}
```

## Quy ước

- Mỗi lần chạy **một thư mục riêng**, tên `YYYY-MM-DD_HHMMSS` (giờ local).
- Không sửa lại log đã nộp; nếu chạy lại cho kết quả khác, tạo thư mục mới và
  ghi chú (đừng ghi đè bằng chứng).
- Log lớn (> 5 MB) nén `.gz` trước khi commit; giữ `summary.md`/`meta.json` plain.
- Mọi số liệu trong báo cáo phải trỏ tới thư mục cụ thể ở đây.
- Không commit log chứa dữ liệu ngoài phạm vi môn học.
