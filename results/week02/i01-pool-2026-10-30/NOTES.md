# Ghi chú lần chạy — W2-I01 pool/handle (2026-10-30)

- Đây là bằng chứng cho **card pool + handle**, không phải test đường I/O async
  hoàn chỉnh: chưa có queue (L01), driver try-submit/IRQ (H01/H02) hay
  poll/wait/submit (I02).
- Bằng chứng chạy trên cây làm việc **dirty** của nhánh `week2/hieu-request`,
  git base `c5adc4f`; commit của PR W2-I01 được tạo sau lần chạy này. Khi báo
  cáo phải trích hash commit, không trích base như hash của card.
- `make test-io` build với `-DIO_SELFTEST` rồi boot QEMU; serial được ghi vào
  `results/local/io-selftest.log` (gitignored) và được chép vào
  `logs/selftest-serial.log` trong thư mục bằng chứng này.
- Sau `make test-io`, kernel đang được build với selftest. Script evidence đã
  chạy `make clean && make` lần cuối; log ở
  `logs/restore-production-build.log`.
- **Negative control** (chạy bằng `results/local/i01_negative_control.sh`):
  - Bug cố ý: bỏ so sánh generation trong `io_lookup_handle_locked`.
  - `make test-io` khi có bug: make exit ≠ 0, 4 assertion T03 FAIL
    (`logs/negative-control-selftest.log`).
  - Restore source rồi chạy lại: PASS (`logs/positive-control-selftest.log`).
  - Chỉ log serial được lưu; `logs/negative-control-make.log` là log build/make
    đầy đủ (43 KB) để chứng minh exit code, không cần đọc như serial.
- **UTF-8:** các log có tiếng Việt phải chạy với
  `LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8`; nếu không, make/echo
  trong WSL tạo mojibake và `make check-text` sẽ FAIL (đã gặp và sửa một lần
  trong lúc làm card này).
- `make test-io` có timeout QEMU `IO_TEST_TIMEOUT` (mặc định 30s); QEMU bị
  kill bởi watchdog sau khi in `init: starting sh`, exit 143/137 được coi là
  bình thường, kết quả do dòng `IO-SELFTEST: PASS` quyết định.
- Không sửa `kernel/*` nào khác ngoài các file liệt kê ở
  `docs/week02/progress-i01.md`; `virtio_disk.c` chỉ thêm accessor 4 dòng
  (slice H01) — logic stock không đổi.
- Các file `docs/architecture.md`, `docs/baseline.md`, `docs/upstream.md` có
  thay đổi từ một tiến trình khác trong cùng workspace; **không** nằm trong
  commit của card I01.
