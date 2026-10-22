# Version log & môi trường tái lập — tuần 1 (T1-05)

> **Owner:** Hiếu (điều phối). Mỗi người **điền dòng của máy mình** ngay sau khi
> chạy `make env-check`; không copy số của máy khác. Giữ commit giống nhau để
> so sánh được.

## 1. Bảng version 3 máy

| Máy | Người | OS | project commit | xv6 pin | gcc RISC-V | QEMU | gdb | python | Ngày | `make env-check` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev-WSL2 (máy mẫu) | base | Ubuntu 24.04 (WSL2) | `3e7b2bb` | `f780d785` | 13.3.0 | 8.2.2 | 15.1 | 3.12.3 | 21/10/2026 | **PASS** |
| laptop-Hiếu | Hiếu | Ubuntu 26.04.1 | TODO (`git rev-parse --short HEAD`) | `f780d785` | 15.2.0 | 10.2.1 *(cài `qemu-system-riscv`)* | 17.1 | 3.14.4 | TODO | PASS sau khi cài QEMU |
| laptop-Hoàng | Hoàng | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| laptop-Lợi | Lợi | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

Ghi chú: máy Hiếu (26.04) — `qemu-system-misc` đã cài nhưng **không có**
`qemu-system-riscv64`; phải cài thêm gói `qemu-system-riscv` (xem
`docs/run-on-ubuntu.md` mục 9). Các version khác đều mới hơn máy mẫu 24.04:
GCC 15.2.0 so với 13.3.0, QEMU 10.2.1 so với 8.2.2, python 3.14.4 so với 3.12.3 —
không ảnh hưởng tính đúng, nhưng **không trộn số baseline giữa hai máy**.

## 2. Cách lấy thông tin

```bash
git rev-parse --short HEAD      # project commit
cat .xv6-commit                 # xv6 pin
make env-check                  # in toàn bộ version + build + boot smoke
```

Copy đúng các dòng `[ OK ]` từ output `make env-check` (gcc, QEMU, gdb,
python). Nếu máy thiếu gì, ghi `THIẾU` + lý do.

## 3. Quy tắc tái lập

1. Clone repo, checkout **đúng commit** trong bảng; `git status` phải sạch khi đo.
2. Cài toolchain: `sudo bash scripts/setup-env.sh` (Ubuntu 24.04/26.04).
3. `make env-check` phải PASS trước khi chạy baseline/test.
4. Ghi lại version + ngày + người chạy vào bảng trên; commit ngay.
5. Khi so sánh baseline giữa các máy: chỉ so **cùng commit**; nêu rõ khác Biệt
   OS/QEMU; không trộn số liệu giữa 24.04 và 26.04 khi kết luận.
6. Baseline của từng máy lưu riêng trong `results/baseline/<timestamp>/` —
   không ghi đè lần chạy của máy khác.

## 4. Bằng chứng kèm theo (đường dẫn)

| Máy | Baseline | Ghi chú |
| --- | --- | --- |
| dev-WSL2 | `results/baseline/2026-10-19_222935/` (6/6 PASS) | máy mẫu của nhóm |
| laptop-Hiếu | TODO | chạy `make baseline` ngày 24/10 |
| laptop-Hoàng | TODO | |
| laptop-Lợi | TODO | |
