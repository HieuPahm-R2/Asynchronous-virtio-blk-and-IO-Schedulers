# Ghi chú lần chạy — W2-G01 contract (2026-10-30)

- Đây là bằng chứng cho **card contract**, không phải kết quả test kernel async.
  Không có implementation async nào được merge ở revision `e809500`.
- `kernel/io_request.h` **chưa** được include vào build kernel (chủ ý: G01 chỉ
  chốt contract; I01 sẽ thêm khai báo/object). Vì vậy `make` chỉ chứng minh base
  vẫn build; header được kiểm riêng bằng `-fsyntax-only` + `_Static_assert`.
- File kiểm header [`io_hdr_check.c`](io_hdr_check.c) nằm ngay trong thư mục bằng
  chứng này để reviewer chạy lại được (lệnh ghi trong
  [`logs/header-check.log`](logs/header-check.log) và ở đầu file).
- `test-fast` chạy lại với `LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8`
  để log tiếng Việt UTF-8 hợp lệ (lần chạy đầu bị mojibake do locale WSL).
- Máy chạy: Windows 11 + WSL2 Ubuntu-24.04; repo ở `/mnt/e/ET4290`. Số liệu thời
  gian QEMU TCG chỉ mang tính tham khảo, không dùng làm benchmark.
- `make clean` xoá build artifact và `fs.img`; `make` tạo lại — không ảnh hưởng
  file nguồn. Không sửa `kernel/*.c` trong card này.
- Bằng chứng review (comment/approve của Hoàng và Lợi) phải được bổ sung vào PR
  khi có; chưa có thì card giữ trạng thái "chờ review", không đánh dấu Done.
