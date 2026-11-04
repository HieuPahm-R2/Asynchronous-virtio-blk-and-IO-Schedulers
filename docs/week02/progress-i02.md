# W2-I02 — Poll, wait và release tối thiểu an toàn (tiến độ)

> **Card:** W2-I02 (CARD 3/9) · **Owner:** Phạm Trung Hiếu (20233402) ·
> **Reviewer:** Nguyễn Văn Hoàng · **Estimate:** 2h · **Hạn nội bộ:** 2026-10-30 ·
> **Bản này:** 2026-10-30.
>
> **Trạng thái:** ✅ implementation + kernel selftest PASS trên nhánh
> `week2/hieu-request` (nối tiếp W2-I01); ⬜ **chờ Hoàng review** (chưa đóng card).
> Completion qua IRQ thật (H02) và test CPUS=4/kill/cancel vẫn **NOT RUN**.
>
> **Hợp đồng:** [`interface.md`](interface.md) D5/D6/D8/D9 · header
> [`kernel/io_request.h`](../../kernel/io_request.h) · nền tảng W2-I01
> ([`progress-i01.md`](progress-i01.md)).

## 1. Đã triển khai

| File | Thay đổi |
| --- | --- |
| `kernel/io_request.c` | `aio_poll()` (1/0/`-EIO`/`-ENOENT`, không ngủ, không free); `aio_wait()` (chỉ process context, `waiters` single-consumer, vòng `sleep_prepare→release→sleep→acquire`, fast-path khi đã terminal, không giữ spinlock khi ngủ); `aio_data()`; `io_async_completed_locked()` (chuyển DONE/ERROR + status + `t_complete` + counter + `wakeup(req)`); test hooks trong `#ifdef IO_SELFTEST` (gap hook, timer completion, slept flag) |
| `kernel/io_request_test.c` | Thêm selftest **process context**: T05 complete-before-wait (DONE + ERROR + stale), T04 release-active, T06a completion trong khe `sleep_prepare→sleep`, T06b waiter ngủ thật được timer IRQ đánh thức, T03 handle sai, T11 drain. Entry `sys_io_selftest()` cho `SYS_io_selftest` |
| `kernel/io_request.h` | Khai báo nhóm test-only hook dưới `#ifdef IO_SELFTEST` (gap hook/timer/slept flag) — không tồn tại trong production |
| Test harness (mới) | `SYS_io_selftest` (kernel/syscall.h/c) chỉ hành động ở build `-DIO_SELFTEST`; `user/init.c` gọi test trước khi chạy shell (guard `#ifdef IO_SELFTEST`); `kernel/trap.c` gọi timer hook trong `clockintr()` (guard flag); `user/usys.pl` thêm wrapper; `scripts/io-selftest.sh` boot thẳng kernel test bằng QEMU **không qua make** (tránh make relink thiếu `-DIO_SELFTEST` do không track CFLAGS); `mk/project.mk` `make test-io` yêu cầu cả 3 dấu PASS: boot pool, process-context, `IO-USER-TEST: PASS` |

### Đối chiếu 4 bước của card

| Bước card | Cách đáp ứng |
| --- | --- |
| 1. `aio_poll` đọc state/status dưới khóa, trả pending/done/error; không ngủ, không free | `aio_poll()`; T05/T04 |
| 2. `aio_wait` process context, validate handle, vòng lặp terminal + `sleep_prepare` khi còn giữ khóa rồi nhả → sleep → lấy lại | `aio_wait()` dùng đúng API pin `f780d785`; T06a/T06b |
| 3. `aio_release` chỉ terminal, hết DMA/ref, không còn waiter; single consumer | `io_release_locked()` (I01) + kiểm `waiters`; T04/T05 |
| 4. Test complete-before-wait + completion trong khe prepare/sleep có hook điều khiển; không dựa vào delay may rủi | T05 + **T06a hook deterministic** + T06b timer 2 tick (bằng chứng bổ sung, không phải bằng chứng duy nhất); negative control chứng minh test bắt lost-wakeup |

## 2. Bằng chứng (WSL2 Ubuntu-24.04, QEMU 8.2.2, riscv gcc 13.3.0)

Thư mục: [`results/week02/i02-poll-wait-2026-10-30/`](../../results/week02/i02-poll-wait-2026-10-30/summary.md)
(base `5296c92`, nhánh `week2/hieu-request`, dirty khi chạy).

| Kiểm tra | Kết quả | Log |
| --- | --- | --- |
| Header contract compile (production + `-DIO_SELFTEST`) | **PASS** cả 2 mode | `logs/header-check.log` |
| Production build (không flag) | **PASS** | `logs/production-build.log` |
| `make test-fast` (boot/shell production, `init` không gọi test) | **PASS 2/2** | `logs/test-fast.log` |
| `make test-io` — boot pool T02/T03/T04/T11 + process T05/T04/T06a/T06b/T03/T11 | **PASS** | `logs/selftest-serial.log` |
| Negative control: bỏ `wakeup(req)` ⇒ T06a treo, không có PASS, `make test-io` FAIL; restore ⇒ PASS | **PASS** | `logs/negative-control-selftest.log`, `logs/positive-control-selftest.log` |
| Restore production build | **PASS** | `logs/restore-production-build.log` |

Trích serial (process-context slice):

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

Negative control (bỏ `wakeup`): serial dừng sau T04, không có `T06a ... PASS` và
không có `IO-USER-TEST: PASS`; QEMU bị watchdog kill ⇒ `make test-io` exit ≠ 0.

## 3. Ghi chú thiết kế / phần chuyển tiếp

- **`io_async_completed_locked()`** (request layer) là chuyển trạng thái chuẩn để
  H02 gọi từ `virtio_disk_intr()`. Card này chỉ test bằng **fake completion
  hook/timer**, chưa có IRQ thật: descriptor reclaim/mapping/used-ring thuộc H02.
- **Test harness process-context** chỉ tồn tại ở build `-DIO_SELFTEST`:
  `SYS_io_selftest` trả `-1` ở production; `user/init.c` không gọi; `clockintr()`
  không gọi hook. Các file upstream `kernel/syscall.{h,c}`, `kernel/trap.c`,
  `user/usys.pl`, `user/init.c` có thêm guard `#ifdef IO_SELFTEST` — khi
  `scripts/update-xv6.sh` đổi pin cần re-apply các mảnh này (ghi vào checklist
  tuần sau).
- **`aio_wait` không xử lý kill/exit/cancel/multi-waiter** (K04 đầy đủ để kỳ
  sau): process bị kill khi đang wait vẫn tiếp tục chờ completion; timeout
  không free DMA buffer. Đã ghi NOT RUN, không hứa.
- **`aio_read_submit` chưa có** (cần queue L01 + try-submit H01/G02); hiện test
  tạo request trực tiếp qua helper nội bộ và fake completion.
- **Không dùng delay may rủi làm bằng chứng duy nhất**: T06a dùng hook đúng khe
  `sleep_prepare→release→sleep`; T06b dùng timer IRQ hoàn tất sau ≥3 tick để
  chứng minh waiter ngủ thật rồi được wakeup (serial in số tick).
- Thư mục `results/local/` (script tạm, log local) bị gitignore; log bằng chứng
  đã chép vào `results/week02/i02-poll-wait-2026-10-30/logs/`.

## 4. Cách tái lập

```bash
make clean && make -j"$(nproc)"   # production (init không chạy test)
make test-fast                    # smoke production
make test-io                      # -DIO_SELFTEST: boot pool + process poll/wait
# sau test-io: make clean && make   # về production
```

## 5. Nghiệm thu card

- [x] Wait sau DONE/ERROR trả ngay đúng status; wait trước completion được đánh
      thức, không treo — T05, T06a, T06b (có số tick).
- [x] Release request đang bay trả `-EBUSY` — T04 (boot + process context).
- [x] Không giữ spinlock trong lúc ngủ; không gọi wait trong IRQ — `aio_wait`
      dùng đúng pattern, guard `myproc()==0 ⇒ -EINVAL`.
- [x] Lỗi handle trả lỗi hữu hạn, không panic/deref sai — T03 (id âm,
      `id==NREQ`, generation 0, stale sau release).
- [x] Test có negative control (bỏ wakeup ⇒ FAIL/treo, restore ⇒ PASS).
- [ ] **Hoàng review** (wait/wakeup pattern, single-consumer, test harness
      guard, tác động production) — `PENDING`.
