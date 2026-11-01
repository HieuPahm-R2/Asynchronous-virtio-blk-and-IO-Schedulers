# W2-I01 — Request pool hữu hạn và handle có generation (tiến độ)

> **Card:** W2-I01 (CARD 2/9) · **Owner:** Phạm Trung Hiếu (20233402) ·
> **Reviewer:** Nguyễn Văn Hoàng · **Estimate:** 6h · **Hạn nội bộ:** 2026-10-29 ·
> **Bản này:** 2026-10-30.
>
> **Trạng thái:** ✅ implementation + kernel selftest PASS trên nhánh
> `week2/hieu-request`; ⬜ **chờ Hoàng review** (chưa đóng card). T01/T05–T10,
> T12–T13 **NOT RUN** — thuộc card driver/queue/wait, chưa có implementation.
>
> **Hợp đồng tham chiếu:** [`interface.md`](interface.md) (D2, D4, D5, D6, D10)
> · header [`kernel/io_request.h`](../../kernel/io_request.h).

## 1. Đã triển khai

| File | Thay đổi |
| --- | --- |
| `kernel/io_request.c` (mới) | Pool BSS `io_pool[IO_NREQ]`, `io_init()`, `io_alloc_slot_locked()` (chỉ FREE, full ⇒ NULL + `eagain_pool++`, không ngủ/panic), `io_lookup_handle_locked()` (id range + state in-use + gen, không dereference index sai), `io_release_locked()` (chỉ DONE/ERROR, `waiters==0`, bump generation khỏi 0, reset FREE), `aio_release()`, `io_get_stats()` (queued/inflight/free_req suy từ state để không lệch counter) |
| `kernel/io_request_test.c` (mới) | Kernel selftest (chỉ build khi `-DIO_SELFTEST`): T02/T03/T04/T11 + buffer-address stability; production build là stub rỗng |
| `kernel/io_request.h` | Thêm nhóm **helper nội bộ** `io_alloc_slot_locked/io_lookup_handle_locked/io_release_locked` cho I02 + test; bỏ include chéo trong header theo quy ước xv6 (include `types.h, param.h, fs.h, spinlock.h` trước) |
| `kernel/virtio_disk.c` | Slice sớm của W2-H01: `virtio_disk_io_lock()` trả `&disk.vdisk_lock` — một lock domain duy nhất (D6), cần cho pool test khi H01 chưa merge |
| `kernel/defs.h` | Khai báo `io_init`, `io_selftest`, `virtio_disk_io_lock` |
| `kernel/main.c` | Gọi `io_init()` sau `virtio_disk_init()`, trước `userinit()`; gọi `io_selftest()` chỉ khi `-DIO_SELFTEST` |
| `Makefile` | Thêm `kernel/io_request.o`, `kernel/io_request_test.o`; `IO_SELFTEST=1` ⇒ `-DIO_SELFTEST` |
| `mk/project.mk` | Target một lệnh **`make test-io`**: clean → build `-DIO_SELFTEST` → boot QEMU CPUS=1 → grep PASS/FAIL; kèm help |

### Đối chiếu 5 bước của card

| Bước card | Cách đáp ứng |
| --- | --- |
| 1. Header/state enum + pool khởi tạo lúc boot | `io_request.h` (đã có từ G01) + `io_init()` từ `main()`; slot có id/gen/state/op/status/dev/blockno/queue link/head/timestamps/waiters |
| 2. `try_alloc`: chỉ FREE, khởi tạo mọi trường, trả handle; full ⇒ EAGAIN, không ngủ/panic | `io_alloc_slot_locked()` + `io_handle_of()`; test T02 |
| 3. Validate handle trước mọi dereference; generation khi tái sử dụng; chống tràn | `io_lookup_handle_locked()`; `io_next_gen()` skip 0; test T03 |
| 4. Địa chỉ header/status/buffer ổn định suốt QUEUED/INFLIGHT; không kalloc ở IRQ | Pool BSS, `uchar data[BSIZE]` trong slot; test T11 kiểm địa chỉ buffer qua các state; không có kalloc/copyout trong code mới |
| 5. Test cấp hết pool, cấp vượt giới hạn, release rồi cấp lại; counters free/active | `make test-io` (T02/T03/T04/T11); `io_get_stats()`; negative control chứng minh test bắt được bug |

## 2. Bằng chứng chạy (máy dev: WSL2 Ubuntu-24.04, QEMU 8.2.2, riscv gcc 13.3.0)

Thư mục: [`results/week02/i01-pool-2026-10-30/`](../../results/week02/i01-pool-2026-10-30/summary.md)
(base `c5adc4f`, nhánh `week2/hieu-request`, dirty khi chạy).

| Kiểm tra | Lệnh | Kết quả | Log |
| --- | --- | --- | --- |
| Header contract + prototype helper | `riscv64-linux-gnu-gcc ... -fsyntax-only io_hdr_check.c` | **PASS** (3 `_Static_assert`: size 1080, NREQ 16, sector×2) | `logs/header-check.log` |
| Build production (không selftest) | `make clean && make -j6` | **PASS** | `logs/production-build.log` |
| Boot/shell smoke sau khi thêm `io_init()` | `make test-fast` | **PASS 2/2** | `logs/test-fast.log` |
| Kernel selftest | `make test-io` | **PASS** — T02/T03/T04/T11, 0 failure | `logs/selftest-serial.log`, `logs/test-io.log` |
| Negative control (tắt check generation) | patch tạm → `make test-io` → restore | **FAIL đúng như mong đợi**: 4 dòng T03 FAIL, make exit ≠ 0; restore ⇒ PASS | `logs/negative-control-selftest.log`, `logs/positive-control-selftest.log` |

Trích serial selftest:

```
IO-SELFTEST: begin (NREQ=16, BSIZE=1024)
IO-SELFTEST: T02 pool-exhaustion PASS
IO-SELFTEST: T03 stale-handle PASS
IO-SELFTEST: T04 release-active PASS
IO-SELFTEST: T11 accounting-drain PASS
IO-SELFTEST: PASS (T02/T03/T04/T11, failures=0)
```

Negative control (bug cố ý: bỏ so sánh `gen`) cho:

```
IO-SELFTEST: T03 FAIL: stale handle rejected by lookup
IO-SELFTEST: T03 FAIL: stale release returns IO_ENOENT
...
IO-SELFTEST: FAIL (failures=4)
```

## 3. NOT RUN và phần chuyển tiếp

- **T01, T05–T10, T12, T13**: cần driver try-submit/IRQ (H01/H02), queue (L01),
  wait/poll (I02) — chưa có implementation, ghi **NOT RUN**, không đổi thành PASS.
- **`aio_read_submit`/`aio_poll`/`aio_wait`/`aio_data`**: mới có khai báo +
  `aio_release`; phần còn lại thuộc I02/G02 (submit cần queue + driver).
- **`io_init()` chưa gọi `io_queue_init()`**: đã ghi TODO trong code; L01 sẽ thêm
  một dòng sau khi `kernel/io_queue.c` merge.
- **`virtio_disk_io_lock()`**: slice sớm của H01 (để I01 build/test được trước
  khi driver đầy đủ); Hoàng review như phần đầu của H01.
- **`aio_release` triển khai sớm ở I01** vì T03/T04/T11 cần thu hồi slot; I02
  giữ nguyên semantics và bổ sung wait/poll/submit wiring.
- **Chưa có concurrent test IRQ/CPUS=4** cho pool: selftest chạy boot CPU,
  trước scheduler; phần đồng thời thật thuộc T04 (hook + QEMU) và I02/H02.

## 4. Cách tái lập

```bash
make clean && make -j"$(nproc)"   # build production (không selftest)
make test-fast                    # smoke boot/shell
make test-io                      # build -DIO_SELFTEST + boot + grep PASS/FAIL
# sau test-io nên chạy lại: make clean && make   (về build production)
```

`make test-io` ghi serial vào `results/local/io-selftest.log`.

## 5. Nghiệm thu card (đối chiếu kế hoạch)

- [x] Cấp đúng `IO_NREQ` slot; slot thứ `IO_NREQ+1` bị từ chối, counter không
      đổi (trừ `eagain_pool`) — T02.
- [x] Sau release + tái sử dụng, handle cũ bị từ chối (`IO_ENOENT`), không trả
      kết quả của request mới — T03.
- [x] Không giải phóng slot còn ALLOCATED/QUEUED/INFLIGHT hoặc còn waiter —
      T04.
- [x] Không rò slot sau 10 vòng cấp/thu hồi; buffer address ổn định — T11.
- [x] Test kernel độc lập PASS/FAIL; negative control chứng minh test FAIL khi
      có bug.
- [x] Không `kalloc`/`copyout` trong code mới; buffer thuộc pool BSS.
- [ ] **Hoàng review** (pool/generation/lock/ownership, đặc biệt slice
      `virtio_disk_io_lock` + reset generation) — `PENDING`.
