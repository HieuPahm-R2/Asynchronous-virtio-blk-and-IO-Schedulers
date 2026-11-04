# W2-I02 — bằng chứng poll/wait/release (2026-10-30)

**Card:** W2-I02 (CARD 3/9) — Bổ sung poll, wait và release tối thiểu an toàn.
**Owner:** Phạm Trung Hiếu. **Reviewer:** Nguyễn Văn Hoàng (**chưa review —
PENDING**).

**Base chạy:** `5296c92` (nhánh `week2/hieu-request`, cây làm việc có thay đổi
chưa commit của I02) · **Pin xv6:** `f780d785…` (tạm) · **Máy:** Windows 11 +
WSL2 Ubuntu-24.04, 6 CPU, QEMU 8.2.2, riscv gcc 13.3.0.

## Đầu ra

| File | Nội dung |
| --- | --- |
| [`kernel/io_request.c`](../../../kernel/io_request.c) | `aio_poll`, `aio_wait` (sleep_prepare/release/sleep/acquire, single consumer), `aio_data`, `io_async_completed_locked`; test hooks dưới `-DIO_SELFTEST` |
| [`kernel/io_request_test.c`](../../../kernel/io_request_test.c) | Process-context selftest T05/T04/T06a/T06b/T03/T11; `sys_io_selftest` |
| [`kernel/io_request.h`](../../../kernel/io_request.h) | Test-only hook declarations (`#ifdef IO_SELFTEST`) |
| [scripts/io-selftest.sh](../../../scripts/io-selftest.sh) | Boot QEMU thẳng kernel test, không qua make (tránh relink thiếu `-DIO_SELFTEST`) |
| `kernel/syscall.{h,c}`, `kernel/trap.c`, `user/usys.pl`, `user/init.c`, `mk/project.mk` | Harness test-only: `SYS_io_selftest` (production trả -1), init gọi test khi flag, timer hook trong `clockintr`, `make test-io` kiểm 3 dấu PASS |
| [`docs/week02/progress-i02.md`](../../../docs/week02/progress-i02.md) | Mô tả, đối chiếu card, NOT RUN, cách tái lập |

## Kết quả

| # | Kiểm tra | Kết quả | Log |
| ---: | --- | --- | --- |
| 1 | Header compile production + `-DIO_SELFTEST` | **PASS** | [header-check.log](logs/header-check.log) |
| 2 | `make clean && make -j6` (production) | **PASS** | [production-build.log](logs/production-build.log) |
| 3 | `make test-fast` (production boot/shell) | **PASS 2/2** | [test-fast.log](logs/test-fast.log) |
| 4 | `make test-io` — boot pool + process poll/wait | **PASS** | [selftest-serial.log](logs/selftest-serial.log) · [test-io.log](logs/test-io.log) |
| 5 | Negative control: bỏ `wakeup(req)` ⇒ T06a treo/FAIL; restore ⇒ PASS | **PASS** | [negative](logs/negative-control-selftest.log) · [positive](logs/positive-control-selftest.log) |
| 6 | Restore production build | **PASS** | [restore-production-build.log](logs/restore-production-build.log) |

Serial (process-context slice):

```
IO-SELFTEST: USER begin (process context, W2-I02)
IO-SELFTEST: USER T05 complete-before-wait PASS
IO-SELFTEST: USER T04 release-active PASS
IO-SELFTEST: USER T06a gap-completion PASS
IO-SELFTEST: USER T06b slept >= 3 tick(s) before wakeup
IO-SELFTEST: USER T06b sleep-wakeup PASS
IO-SELFTEST: USER T03 stale-handle-invalid-forms PASS
IO-SELFTEST: USER T11 accounting-drain-user PASS
IO-SELFTEST: USER PASS (T03/T04/T05/T06, failures=0)
IO-USER-TEST: PASS (rc=0)
```

Negative control (bỏ wakeup): serial dừng sau `T04 PASS`, thiếu
`T06a gap-completion PASS` và `IO-USER-TEST: PASS`; QEMU bị watchdog kill nên
`make test-io` exit ≠ 0. Đây là bằng chứng T06 thật sự bắt được lost wakeup.

## NOT RUN / phần chuyển tiếp

- **Completion IRQ thật (H02)**: used ring, descriptor mapping/reclaim chưa có;
  I02 test bằng fake completion hook + timer IRQ (chỉ build `-DIO_SELFTEST`).
- **T06 CPUS=4 / multi-waiter / kill-exit / cancel**: K04 đầy đủ kỳ sau; hiện
  chỉ 1 waiter và không free buffer vì timeout.
- **`aio_read_submit`**: cần queue L01 + try-submit H01/G02.
- **T01, T07–T10, T12–T13**: cần queue/driver.
- **Review Hoàng**: PENDING — card chưa đóng.

## Tái lập

```bash
make clean && make -j"$(nproc)"   # production
make test-fast
make test-io                      # -DIO_SELFTEST + QEMU + grep PASS/FAIL
# sau đó: make clean && make        # về production
```

Harness `make test-io` yêu cầu đồng thời: `IO-SELFTEST: PASS` (boot pool),
`IO-SELFTEST: USER PASS` (process context) và `IO-USER-TEST: PASS` (init).
