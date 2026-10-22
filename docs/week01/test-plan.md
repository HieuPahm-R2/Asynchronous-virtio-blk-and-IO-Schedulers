# Test plan — tuần 1 (T1-10)

> **Owner:** Hiếu. **Reviewer:** Lợi. Mục tiêu học phần: **≥ 30 case có assertion
> thực chất**, chạy bằng một lệnh, in PASS/FAIL từng case; CPUS=1/4 lặp ≥ 10;
> benchmark ≥ 5 lần/điểm; stress ≥ 30 phút/phối hợp.
>
> Khung lý thuyết: [`../testing.md`](../testing.md). Đừng điền số liệu khi chưa đo —
> ghi **NOT RUN**.

## 1. Phân tầng & số case dự kiến

| Tầng | Nội dung | Số case dự kiến | Tag |
| --- | --- | ---: | --- |
| T0 | smoke: boot, shell, fs | 2 | `fast` |
| T1 | regression stock (usertests, grind) | 4 | `usertests`, `stress` |
| T2 | policy FCFS/SCAN/deadline + oracle | 9–12 | `scheduler` |
| T3 | lifecycle/async (submit trước completion, poll/wait, complete-before-wait, kill/exit) | 6–8 | `async` |
| T4 | merging (adjacent, prepend/append, checksum, descriptor exhaustion) | 6–8 | `merge` |
| T5 | chuyển policy khi QUEUED/INFLIGHT khác rỗng | 2–3 | `policy-switch` |
| T6 | stress ≥ 30 phút CPUS=1/4 | 2–4 | `stress` |
| **Tổng** | | **≥ 30** | |

## 2. Danh sách case (điền dần; giữ tên ổn định)

| # | Case | Tầng | R | CPUS | Oracle (cách kiểm) | Tag | Trạng thái |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | `boot-smoke` | T0 | — | 1 | serial có `init: starting sh` + echo đúng | fast | ✅ có |
| 2 | `shell-fs-cpus3` | T0 | — | 3 | `ls` có README, `cat README` đúng | fast | ✅ có |
| 3 | `usertests-quick-cpus1` | T1 | — | 1 | `ALL TESTS PASSED`, không `FAILED` | baseline | ✅ có |
| 4 | `usertests-quick-cpus4` | T1 | — | 4 | như trên | baseline | ✅ có |
| 5 | `grind-smoke-cpus1` | T1 | R09 (một phần) | 1 | không panic trong 60s, ghi thời lượng | stress | ✅ có |
| 6 | `grind-smoke-cpus4` | T1 | R09 (một phần) | 4 | như trên | stress | ✅ có |
| 7 | `sched-fcfs-order` | T2 | R02 | 1 | trace dispatch khớp oracle thứ tự | scheduler | NOT RUN |
| 8 | `sched-scan-reversal` | T2 | R03 | 1 | đầu đọc tới biên rồi đảo chiều; phân biệt LOOK | scheduler | NOT RUN |
| 9 | `sched-deadline-expired` | T2 | R04 | 1 | request quá hạn dispatch trước | scheduler | NOT RUN |
| 10 | `inflight-at-least-2` | T3 | R01 | 1 | counter `max_inflight >= 2` + dữ liệu đúng | async | NOT RUN |
| 11 | `aio-submit-before-complete` | T3 | R06 | 1 | submit trả trước, caller làm việc khác rồi wait | async | NOT RUN |
| 12 | `aio-complete-before-wait` | T3 | R06 | 1 | completion đến trước wait, không mất wakeup | async | NOT RUN |
| 13 | `merge-adjacent` | T4 | R05 | 1 | 1 device command, completion từng con | merge | NOT RUN |
| 14 | `merge-checksum` | T4 | R05 | 4 | checksum từng child đúng | merge | NOT RUN |
| 15 | `desc-exhaustion` | T4 | R05/R08 | 1 | cấp/giải phóng descriptor đúng, không leak | merge | NOT RUN |
| 16 | `policy-switch-loaded` | T5 | R07 | 1 | đổi khi QUEUED+INFLIGHT khác rỗng, không mất request | policy-switch | NOT RUN |
| 17 | `stress-30m-cpus1` | T6 | R09 | 1 | 30 phút, checksum cuối, tài nguyên không lệch | stress | NOT RUN |
| 18 | `stress-30m-cpus4` | T6 | R09 | 4 | như trên | stress | NOT RUN |
| … | (bổ sung tới ≥ 30) | | | | | | TODO |

## 3. Ma trận chạy

| Trục | Giá trị | Ghi chú |
| --- | --- | --- |
| CPUS | 1, 4 | bắt buộc; lặp ≥ 10 cho ca đồng thời/stress |
| Policy | FCFS, SCAN, deadline (+ stock) | mỗi policy chạy riêng |
| Merge | off, on | |
| Concurrency | 1, 2, 4 reader + đọc/ghi hỗn hợp | |
| Queue depth | 1, 2, 4 (theo pool/thiết bị) | ghi lý do nếu giảm |

## 4. Benchmark protocol

- Mỗi điểm đo: **≥ 5 lần**; báo mean + độ lệch chuẩn (hoặc min–max), p50/p95/p99 nếu đủ sample.
- Cùng commit, cùng máy, cùng QEMU command line, cùng seed/dataset.
- Workload: đọc tuần tự, đọc ngẫu nhiên, nhiều reader đồng thời, đọc/ghi hỗn hợp.
- Không chỉ đọc file đã nóng trong buffer cache; ghi rõ cold/warm; đếm I/O thiết bị thực.
- Đơn vị: throughput = byte xong / thời gian; latency = complete − enqueue;
  service = complete − dispatch. Ghi timer resolution.
- Lưu: `results/bench/<timestamp>/` gồm dữ liệu thô + bảng + đồ thị + `meta.json`
  theo format [`results/README.md`](../../results/README.md).

## 5. Stress protocol

- Mỗi policy × CPUS=1/4, thời lượng tối thiểu **30 phút** cho ca phối hợp async/merge.
- Ghi: thời lượng, seed, cấu hình CPU, checksum, tài nguyên trước/sau, cách kết thúc.
- FAIL khi: checksum sai, panic, timeout không tiến triển, completion trùng/mất,
  descriptor/request không thu hồi, tài nguyên lệch sau drain.

## 6. Format kết quả

- Test: `results/local/<timestamp>/` (`summary.md`, `meta.json`, `logs/`).
- Baseline/bench: `results/baseline/<timestamp>/` / `results/bench/<timestamp>/`.
- Trường bắt buộc: commit, xv6 pin, CPUS, toolchain, seed, thời lượng, người chạy.

## 7. NOT RUN / chưa đo

| Hạng mục | Lý do | Kế hoạch |
| --- | --- | --- |
| Policy/async/merge cases (7–18) | chưa có code tuần 2–6 | làm khi có tính năng |
| Benchmark scheduler | chưa có scheduler | tuần 7 |
| Stress 30 phút | chưa có async/merge | tuần 7 |
| Free inode check | chưa có counter/format | bổ sung trước midterm |
