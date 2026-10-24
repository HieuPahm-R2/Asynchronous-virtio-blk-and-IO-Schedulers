# Bằng chứng máy Hoàng ngày 23/10/2026

Đề tài 26128, Nguyễn Văn Hoàng 20233413. Đây là bản sao bằng chứng từ
results/local/hoang-week01-20261023 để có thể commit và chia sẻ trong repo.
Không có lượt test mới khi sao chép thư mục này.

- Project commit được chạy: a0cfa2e942fd7cf27040ec404b002e5a25c691d9.
- Xv6 pin: f780d7850765d74cbdcd1fff4b822d8829f7c9bd.
- Ubuntu 24.04.3, riscv64-unknown-elf-gcc 13.2.0, QEMU 8.2.2.
- env-check: exit 0; cảnh báo thiếu gdb-multiarch và clang-format.
- Rebuild: PASS; 4/4 smoke read/write + reboot CPUS=1/4: PASS.
- Stock-fast: 2/2 PASS (CPUS=1/3 theo case hiện có).
- Full usertests/grind, stress 30 phút, max_inflight và lỗi tiêm: NOT RUN.

checks.json ghi compiler thực tế (unknown-elf). Trường riscv_gcc trống trong
stock-fast/meta.json do stock runner chỉ tìm tên compiler linux-gnu; không
có nghĩa bản build thiếu compiler.

Reboot kiểm tra cùng fs.img sau sync, không phải kiểm tra mất điện host.
Xem docs/week01/hoang.md để chạy lại và trình bày kết quả.
