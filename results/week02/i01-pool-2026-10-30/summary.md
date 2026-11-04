# W2-I01 — bằng chứng request pool + generation handle (2026-10-30)

**Card:** W2-I01 (CARD 2/9) — Triển khai request pool hữu hạn và handle có
generation. **Owner:** Phạm Trung Hiếu. **Reviewer:** Nguyễn Văn Hoàng
(**chưa review — PENDING**).

**Base chạy:** `c5adc4f` (nhánh `week2/hieu-request`, cây làm việc có thay đổi
chưa commit của I01) · **Pin xv6:** `f780d785…` (tạm, GV chưa xác nhận) ·
**Máy:** Windows 11 + WSL2 Ubuntu-24.04, 6 CPU, QEMU 8.2.2, riscv gcc 13.3.0.

## Đầu ra

| File | Nội dung |
| --- | --- |
| [`kernel/io_request.c`](../../../kernel/io_request.c) | Pool BSS 16 slot, `io_init`, `io_alloc_slot_locked`, `io_lookup_handle_locked`, `io_release_locked`, `aio_release`, `io_get_stats` |
| [`kernel/io_request_test.c`](../../../kernel/io_request_test.c) | Kernel selftest T02/T03/T04/T11 (chỉ khi `-DIO_SELFTEST`) |
| [`docs/week02/progress-i01.md`](../../../docs/week02/progress-i01.md) | Mô tả triển khai, đối chiếu 5 bước card, NOT RUN, cách tái lập |
| `kernel/io_request.h`, `kernel/virtio_disk.c`, `kernel/defs.h`, `kernel/main.c`, `Makefile`, `mk/project.mk` | Helper API, lock accessor (slice H01), khai báo/khởi tạo, object + flag, target `make test-io` |

## Kết quả

| # | Kiểm tra | Kết quả | Log |
| ---: | --- | --- | --- |
| 1 | Header contract + helper prototypes compile `-Wall -Werror` | **PASS** | [header-check.log](logs/header-check.log) |
| 2 | `make clean && make -j6` (production, không selftest) | **PASS** | [production-build.log](logs/production-build.log) |
| 3 | `make test-fast` — boot-smoke CPUS=1, shell-fs-cpus3 CPUS=3 | **PASS 2/2** | [test-fast.log](logs/test-fast.log) |
| 4 | `make test-io` — kernel selftest T02/T03/T04/T11 | **PASS** | [selftest-serial.log](logs/selftest-serial.log) · [test-io.log](logs/test-io.log) |
| 5 | Negative control: bỏ check generation ⇒ T03 FAIL, restore ⇒ PASS | **PASS** | [negative](logs/negative-control-selftest.log) · [positive](logs/positive-control-selftest.log) |
| 6 | Restore production build sau test-io | **PASS** | [restore-production-build.log](logs/restore-production-build.log) |

Serial selftest (trích):

```
IO-SELFTEST: begin (NREQ=16, BSIZE=1024)
IO-SELFTEST: T02 pool-exhaustion PASS
IO-SELFTEST: T03 stale-handle PASS
IO-SELFTEST: T04 release-active PASS
IO-SELFTEST: T11 accounting-drain PASS
IO-SELFTEST: PASS (T02/T03/T04/T11, failures=0)
```

Negative control (bug cố ý — bỏ `gen` trong validate):

```
IO-SELFTEST: T03 FAIL: stale handle rejected by lookup
IO-SELFTEST: T03 FAIL: stale release returns IO_ENOENT
IO-SELFTEST: T03 FAIL: stale handle rejected after new data written
IO-SELFTEST: T03 FAIL: stale_handle counter incremented
IO-SELFTEST: FAIL (failures=4)
```

## NOT RUN

- **T01, T05–T10, T12–T13**: cần driver try-submit/IRQ (H01/H02), queue (L01),
  poll/wait (I02) — chưa có implementation; ghi NOT RUN, không đổi thành PASS.
- **Concurrent/IRQ thật cho release-active (T04)**: selftest chạy trên boot CPU
  trước scheduler; bản hook + QEMU thuộc I02/H02.
- `make test`, `make test-slow`, `make baseline`: không cần cho card này.
- **Review Hoàng**: PENDING — card chưa đóng.

## Tái lập

```bash
make clean && make -j"$(nproc)"    # production build
make test-fast                     # smoke
make test-io                       # build -DIO_SELFTEST + QEMU + grep PASS/FAIL
# sau đó: make clean && make        # về production
```

Lưu ý: `make test-io` để lại kernel build bằng `-DIO_SELFTEST`; chạy lại
`make clean && make` trước khi dùng cho việc khác.
