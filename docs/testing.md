# Kế hoạch kiểm thử

Mục tiêu môn học: **≥ 30 test case có assertion thực chất**, chạy bằng **một
lệnh**, in **PASS/FAIL từng ca**; ma trận concurrency/stress `CPUS=1` và
`CPUS=4` lặp **≥ 10 lần**; kiểm tra **free pages / free inodes** trước–sau;
mỗi điểm benchmark **≥ 5 lần đo**, báo trung bình + độ phân tán.

Tài liệu này là khung; case thật được thêm dần vào `tests/cases/` theo từng
tuần. Nguồn yêu cầu: kế hoạch 26128 (mục 2, 9) và spec học phần.

## 1. Nguyên tắc

1. **Đúng trước, nhanh sau.** Chứng minh data integrity, completion đúng một
   lần, không mất wakeup, không dùng lại buffer sớm, không rò tài nguyên —
   rồi mới so throughput/latency.
2. **Oracle độc lập.** Test scheduler so **thứ tự dispatch** theo trace đầu vào
   cố định và oracle viết tay, **không** dùng thứ tự completion của thiết bị
   làm oracle.
3. **Không "PASS vì chưa thấy panic".** Với test chạy dài (grind/stress), ghi
   thời lượng, seed, cách kết thúc; chỉ PASS khi có assertion/điều kiện dừng rõ.
4. **Lỗi phải để lại log.** Không rerun đến khi PASS rồi bỏ log lỗi.
5. **Tái lập được.** Mọi case ghi: commit, CPUS, seed, input, timeout.

## 2. Phân tầng test

| Tầng | Nội dung | Ví dụ case | Tag |
| --- | --- | --- | --- |
| T0 — smoke | boot, shell, fs cơ bản | `boot-smoke`, `shell-fs-cpus3` | `fast` |
| T1 — regression stock | usertests -q/đầy đủ, grind | `usertests-quick-*`, `grind-smoke-*` | `usertests`, `stress` |
| T2 — policy | FCFS/SCAN/deadline với trace cố định + oracle | `sched-fcfs-order`, `sched-scan-reversal`, ... | `scheduler` |
| T3 — lifecycle/async | submit trước completion, poll/wait, complete-before-wait, kill/exit | `aio-submit-wait`, `aio-complete-before-wait`, `aio-kill` | `async` |
| T4 — merging | append/prepend, checksum, completion con, descriptor exhaustion | `merge-adjacent`, `merge-checksum`, `desc-exhaustion` | `merge` |
| T5 — chuyển policy | đổi khi QUEUED và INFLIGHT khác rỗng, không mất request | `policy-switch-loaded` | `policy-switch` |
| T6 — stress | ≥ 30 phút/phối hợp; CPUS=1/4 | `stress-30m-*` | `stress` |

Mục tiêu ≥ 30 case có assertion thật: khoảng T2 9–12, T3 6–8, T4 6–8,
T5 2–3, T6 2–4, còn lại T1.

### Thời gian chạy thực tế (máy dev WSL2, QEMU TCG — số baseline tuần 1)

| Lệnh | Case | Thời gian | Ghi chú |
| --- | ---: | ---: | --- |
| `make test-fast` | 2 | ~8 giây | smoke boot/shell, dùng khi code hằng ngày |
| `make test` | 5 | ~18 phút | gồm `usertests -q` CPUS=1/4 (~9 + ~8 phút) |
| `make baseline` | 6 | ~19,4 phút | build sạch + usertests -q + grind 60s ×2 |
| `make test-slow` | +2 | ~30–40 phút | `usertests` đầy đủ, chạy có chủ đích |

Số liệu chi tiết: `results/baseline/2026-10-19_222935/summary.md`. Nếu QEMU có
KVM (Linux VM), thời gian giảm đáng kể; phải ghi lại khi đổi môi trường đo.

## 3. Case bắt buộc theo yêu cầu R01–R09

| Mã | Bằng chứng cần có | Case đề xuất |
| --- | --- | --- |
| R01 | ≥ 2 request INFLIGHT cùng lúc + dữ liệu đúng | `inflight-at-least-2` (đọc counter `max_inflight`) |
| R02 | FCFS dispatch đúng thứ tự đến | `sched-fcfs-order` |
| R03 | SCAN: đầu đọc đến biên rồi đảo chiều, khác LOOK | `sched-scan-reversal`, `sched-scan-vs-look` |
| R04 | deadline ưu tiên quá hạn + chống starvation | `sched-deadline-expired`, `sched-deadline-starvation` |
| R05 | merge thành một lệnh thiết bị + checksum + completion con | `merge-adjacent`, `merge-checksum`, `merge-prepend` |
| R06 | submit trả trước completion; caller làm việc khác rồi wait/poll | `aio-submit-first`, `aio-poll-loop` |
| R07 | chuyển FCFS/SCAN/deadline lúc chạy + đồ thị | `policy-switch-loaded` + benchmark |
| R08 | cấu trúc request/state/lock/error path được review | (review + test error path) |
| R09 | stress ≥ 30 phút có log thời lượng, seed, cấu hình | `stress-30m-cpus1`, `stress-30m-cpus4` |

## 4. Ma trận chạy

| Trục | Giá trị |
| --- | --- |
| CPUS | 1 và 4 (bắt buộc), thêm 2/3 nếu cần |
| lặp | ≥ 10 lần cho ma trận concurrency/stress |
| policy | FCFS, SCAN, deadline (+ stock baseline) |
| merge | off / on |
| concurrency | 1 / 2 / 4 reader (và hỗn hợp đọc–ghi) |
| queue depth | 1 / 2 / 4 hoặc mức thiết bị/pool cho phép |

Kiểm tra tài nguyên trước/sau suite:
- `countfree()` của `usertests` (free pages) — case `usertests-*` đã bao gồm
  kiểm tra "lost some free pages".
- free inodes: thêm case đọc/ghi tạo–xoá file rồi so `free inodes` (kế hoạch
  tuần sau; hiện chưa có counter trong kernel — cần thêm hoặc suy từ `stat`).

## 5. Benchmark (tách khỏi test đúng)

- So sánh: stock ↔ async FCFS ↔ SCAN ↔ deadline; mỗi policy merge off/on.
- Cùng commit, dataset, CPU, seed, queue depth, **cùng QEMU command line**.
- Workload tối thiểu: đọc tuần tự, đọc ngẫu nhiên, nhiều reader đồng thời,
  đọc/ghi hỗn hợp.
- **Không** chỉ đọc lặp một file đã nóng trong buffer cache rồi gọi là disk
  benchmark: dùng tập nhiều file đủ gây cache miss, ghi rõ cold/warm, đếm I/O
  thiết bị thực.
- Mỗi điểm ≥ 5 lần: báo mean + stddev (hoặc min–max), p50/p95/p99 nếu đủ sample.
- Đơn vị: `throughput = bytes_completed / duration`; `latency = complete −
  enqueue`; `service = complete − dispatch`. Ghi timer resolution, sample count,
  lỗi, merge ratio, max_inflight.
- Kết quả thô + đồ thị lưu trong `results/baseline/` và `results/bench/`.

## 6. Stress

- Tối thiểu: **30 phút** cho mỗi policy trên CPUS=1 và 4 (mở rộng so với yêu
  cầu đề tài). Tối thiểu phải có case 30 phút bao phủ async/merge tích hợp.
- Ma trận concurrency `CPUS=1/4` lặp ≥ 10 lần (các lượt ngắn hơn, ghi riêng).
- FAIL nếu: checksum sai, panic, timeout không tiến triển, completion trùng/mất,
  descriptor/request không thu hồi, tài nguyên lệch sau drain/cleanup.
- Log: thời lượng, seed, cấu hình CPU, checksum, tài nguyên, kết luận.

## 7. Cách viết case trong repo này

Thêm vào `tests/cases/<module>.py`:

```python
CASES = [{
    "name": "sched-fcfs-order",          # duy nhất
    "cpus": 1,                            # 1 hoặc 4 theo ma trận
    "tags": ["scheduler", "baseline"],    # dùng cho --tag
    "timeout": 120,                       # giây, tổng cho các bước
    "fresh_fs": True,                     # fs.img sạch mỗi lần
    "steps": [
        # gửi lệnh, chờ output khớp regex (all patterns)
        {"send": "schedtest trace_fcfs.txt", "expect": [r"^DISPATCH 0 1 2 3$"], "timeout": 60},
    ],
    "expect": [r"^ALL DISPATCH OK$"],     # kiểm tra toàn bộ serial
    "reject": [r"FAILED", r"^panic:"],    # fail nếu khớp
    # "survive_s": 1800,                  # dùng cho stress: chạy thêm N giây không panic
    "note": "FCFS: trace 4 request, oracle độc lập",
}]
```

- Chạy: `python3 tests/runner.py --case sched-fcfs-order --verbose`
- Kết quả: `results/local/tests-<ts>/` (`summary.md`, `meta.json`, `logs/`).
- Case dài/stress đặt tag `slow`/`stress` để `make test` mặc định bỏ qua.
- Test cần chương trình user mới: thêm file vào `user/` và khai báo trong
  `UPROGS` của `Makefile`; nếu file user thuộc upstream thì nhớ khi
  `scripts/update-xv6.sh` sẽ không xoá file của dự án (chỉ xoá file trong
  `.xv6-files`), nhưng cần tự thêm vào `UPROGS` lại sau khi update.

## 8. Definition of Done cho một case test

- [ ] Có assertion thực chất (không chỉ "không panic") và oracle độc lập nếu
      liên quan thứ tự/đo đạc.
- [ ] Chạy được bằng `make test` (hoặc tag riêng có ghi chú).
- [ ] PASS/FAIL rõ ràng, log lưu lại khi FAIL.
- [ ] Đã chạy CPUS=1 và CPUS=4 nếu case liên quan đồng thời.
- [ ] Reviewer khác tác giả chạy lại độc lập.
