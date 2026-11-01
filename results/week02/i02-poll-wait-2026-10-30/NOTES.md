# Ghi chú lần chạy — W2-I02 poll/wait/release (2026-10-30)

- Bằng chứng chạy trên cây làm việc **dirty** của nhánh `week2/hieu-request`,
  git base `5296c92` (commit W2-I01). Commit của PR W2-I02 tạo sau lần chạy;
  báo cáo phải trích hash commit, không trích base.
- **Test harness process-context**: aio_wait cần process context nên không thể
  test ở boot. Card này thêm `SYS_io_selftest` + hook trong `user/init.c`, chỉ
  hoạt động ở build `-DIO_SELFTEST`:
  - production: `sys_io_selftest()` trả -1, `init` không gọi, `clockintr()`
    không gọi hook (đã chứng minh bằng production build + test-fast).
  - test: init gọi syscall trước khi chạy shell; kết quả in qua printk và
    `IO-USER-TEST: PASS`.
- **`scripts/io-selftest.sh` boot QEMU trực tiếp, không gọi make.** Lý do: make
  không track thay đổi CFLAGS; nếu gọi `make qemu` sau khi build bằng
  `IO_SELFTEST=1`, make có thể relink một phần object **không có `-DIO_SELFTEST`**
  (đã gặp: undefined reference `io_test_timer_tick`). Script này tránh hẳn.
- **Negative control** (`results/local/i02_negative_control.sh`):
  - Bug cố ý: bỏ `wakeup(req)` trong `io_async_completed_locked`.
  - Kỳ vọng: completion rơi đúng khe `sleep_prepare→sleep` bị mất; T06a treo,
    QEMU bị watchdog kill; `make test-io` exit ≠ 0; serial không có
    `USER T06a ... PASS` / `IO-USER-TEST: PASS`
    (`logs/negative-control-selftest.log`).
  - Restore source và chạy lại: PASS (`logs/positive-control-selftest.log`).
  - `logs/negative-control-make.log` là log build/make đầy đủ (43 KB) — log
    serial là nguồn kiểm chính.
- Log tiếng Việt phải chạy với `LANG=C.UTF-8 LC_ALL=C.UTF-8
  PYTHONIOENCODING=utf-8`; nếu không make/echo trong WSL sinh mojibake và
  `make check-text` sẽ FAIL.
- T06b dùng timer IRQ hoàn tất sau ≥3 tick; serial in số tick để chứng minh
  waiter ngủ thật rồi được đánh thức. T06a mới là kiểm tra deterministic đúng
  khe race, không dựa vào delay.
- Các file `docs/architecture.md`, `docs/baseline.md`, `docs/upstream.md` có
  thay đổi từ tiến trình khác trong workspace; **không** thuộc commit W2-I02.
