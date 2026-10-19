# Harness test

Chạy bằng một lệnh, in PASS/FAIL từng case, lưu log + metadata.

```bash
make test                 # suite mặc định (bỏ tag slow/stress)
make test-fast            # chỉ smoke (~10s)
make test-slow            # usertests đầy đủ (rất lâu)
make baseline             # build sạch + baseline stock
python3 tests/runner.py --list
python3 tests/runner.py --case 'sched-*' --verbose
python3 tests/runner.py --tag baseline --results-dir results/local/x
```

## Thành phần

| File | Vai trò |
| --- | --- |
| `qemu.py` | `QemuSession`: build, boot QEMU, `send`, `expect` (regex), `survive`, kill process group |
| `runner.py` | nạp case, chọn theo tag/tên, chạy, in PASS/FAIL, ghi kết quả |
| `cases/*.py` | danh sách `CASES` (dict); thêm file mới là tự được nạp |

## Kết quả

Mỗi lần chạy ghi vào `results/local/<timestamp>/` (hoặc `--results-dir`):

```
summary.md      bảng PASS/FAIL, thời gian, ghi chú
meta.json       commit, xv6 pin, host, toolchain, từng case
logs/<case>.log serial console đầy đủ (có header trạng thái)
```

## Viết case

Xem mục 7 trong [`docs/testing.md`](../docs/testing.md). Tóm tắt:

```python
CASES = [{
    "name": "ten-case",              # duy nhất, dùng --case để chọn
    "cpus": 1,                        # 1 hoặc 4 theo ma trận
    "tags": ["scheduler"],            # dùng --tag
    "timeout": 120,                   # tổng giây cho các bước
    "fresh_fs": True,                 # xoá fs.img và tạo mới mỗi case
    "steps": [
        {"send": "cmd", "expect": [r"^OK$"], "reject": [r"FAILED"], "timeout": 30},
    ],
    "expect": [],                     # regex phải khớp trên toàn serial
    "reject": [r"FAILED", r"^panic:"],
    "survive_s": 0,                   # >0: chạy thêm N giây, fail nếu panic
    "note": "mô tả ngắn",
}]
```

## Biến môi trường / tham số hữu ích

| Tham số | Việc |
| --- | --- |
| `--list` | liệt kê case, tag, timeout |
| `--case GLOB` | lọc theo tên (có thể lặp lại) |
| `--tag TAG` | lọc theo tag (có thể lặp lại; giao với tag khác) |
| `--all` | chạy cả tag slow/stress |
| `--cpus N` | chỉ case cấu hình CPUS đó |
| `--results-dir DIR` | nơi ghi kết quả |
| `--verbose` | in lệnh gửi vào shell |

## Tag đang dùng

`fast`, `baseline`, `usertests`, `stress`, `slow`, `ci` — ý nghĩa xem đầu file
`tests/cases/stock.py`. `make test` mặc định bỏ `slow` và `stress`.
