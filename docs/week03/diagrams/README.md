# Sơ đồ tuần 3 (W3-I02)

Thư mục này chứa **nguồn sửa được** và **ảnh sinh ra** cho proposal/spec tuần 3.
Không dùng ảnh chụp màn hình hay SVG xuất tay từ công cụ ngoài.

| File | Vai trò |
| :--- | :--- |
| [`make_diagrams.py`](make_diagrams.py) | **Nguồn sự thật** của cả hai sơ đồ (matplotlib); sửa script rồi sinh lại |
| [`architecture-pipeline.svg`](architecture-pipeline.svg) | Pipeline `aio_read_submit → pool → queue → dispatcher → try_submit → virtqueue → IRQ → completion → wait/release` (Hình 1 trong proposal) |
| [`scan-boundary.svg`](scan-boundary.svg) | Ví dụ SCAN logic: `head=40`, tăng; dispatch `50,70,90`; biên logic `1999`; đảo chiều; `20,10` |

## Sinh lại

```bash
python3 docs/week03/diagrams/make_diagrams.py
```

Yêu cầu: Python 3.10+ và `matplotlib`. Script ghi đè hai file `.svg` cùng thư mục.
Sơ đồ chỉ là hình minh hoạ cấu trúc/điều phối phần mềm; **không** phải bằng chứng
đo hiệu năng hay chuyển đầu từ vật lý.

## Quy ước nội dung

- Một miền khóa `io_lock` (= `disk.vdisk_lock`); IRQ không `printk`/`kalloc`/`sleep`.
- Staging buffer thuộc pool (BSS), không thuộc caller.
- SCAN logic ghi **sự kiện biên logic** rồi đảo chiều; không phát READ giả tới biên.
