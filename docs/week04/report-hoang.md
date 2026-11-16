# Kết quả công việc Hoàng - 16/11/2026

## Kết quả công việc của Hoàng

ĐỀ TÀI 26128 | ET4290 | BÁO CÁO THỰC HIỆN NGÀY 16/11/2026

Nguyễn Văn Hoàng - MSSV 20233413
Asynchronous virtio-blk and I/O schedulers trên xv6-riscv

Kỳ việc: phần Hoàng của tuần 4 (09-15/11) chuyển tiếp, thực hiện đầu tuần 5 ngày 16/11/2026, Asia/Saigon. Không ghi lùi ngày hoặc ước lượng thành actual worklog.

### 1. Summary of latest progress

Đã triển khai kiểm thử READ thật cho FCFS/SCAN/deadline và đủ 6 chiều runtime switch trên CPU1/4. Đã thêm controller cho stress 4 producer, chạy 10/10 boot, kiểm đủ 1024 byte/READ, chấm thời điểm switch khi Q>0 và I=2, kiểm drain sau mỗi phase. Kết quả hồi quy FCFS, oracle độc lập/mutant và production đều đạt trên cùng code revision.

| Đầu việc Jira | Kết quả trên máy hiện tại | Phần chưa thể nhận hoàn tất |
| --- | --- | --- |
| PTO-31 / W4-H01 | Code real-DMA + oracle, CPU1/4 PASS; review driver/API đã ghi | Chờ review chéo của Lợi/Hiếu trước merge |
| PTO-36 / W4-H02 | 10 boot / 4.800 READ, 6 switch có tải/boot, negative bị bắt | Máy thứ hai cùng candidate chưa có log |
| PTO-37 / W4-G02 | 20 boot FCFS + mock/oracle + 6 case production PASS | Chưa có xác nhận reviewer; chưa merge remote |

### Revision và phạm vi đã lưu

```text
Code được kiểm: d39ea8cf3500a0fdcf023efeab2c850dd2b767d6
Nhánh local: week4/hoang-real-policy-stress
Base: ae6a7cf (Hiếu), chứa 0dc296e (Lợi); main remote: 5191ed8
```

Giữ nguyên Jira: không đổi trạng thái, không bình luận, không tạo task. GitHub hiện chưa có PR mở cho tuần 4 tại lúc đọc. Code được lưu bằng commit local và gói tái lập; không tuyên bố đã push/merge hoặc đã được thành viên khác duyệt.

## 2. Review of technical activities

### READ thật có oracle xác định

1. Mỗi boot có 10 ca, tổng 70 READ: ba policy riêng, sáu chiều chuyển, một ca deadline chờ thật ít nhất 50 tick. Hai anchor chiếm hai chain thật; software reaping được giữ để nạp năm request QUEUED.
2. Host dùng mô hình contract độc lập của Hiếu để tính expected từ input và trạng thái trước switch. Chấm từng event, reason, head/direction, batch và epoch; không lấy completion order hoặc candidate do kernel chọn làm đáp án.
3. Kiểm EAGAIN/no-op/enum sai, bảo toàn id/gen/seq/arrival, checksum toàn block, stale sau release, 16 slot và 8 descriptor được thu hồi. Trace chỉ reset ở build test khi queue rỗng giữa ca, không reset policy/counters/request.

### Stress 4 producer với controller ở parent

Mỗi worker đọc 120 block, window5; sáu phase x20 READ/worker. Mỗi phase có 80 READ, hai chain đầu được publish trước switch và 78 request còn lại phải dispatch dưới policy đích. Barrier giữa phase cho phép chứng minh policy thực sự được sử dụng, thay vì đổi tên sáu lần rồi chạy tất cả dưới FCFS.

```text
FCFS -> SCAN -> DEADLINE -> SCAN -> FCFS -> DEADLINE -> FCFS
Mỗi switch: Q>0, I=2; epoch tăng đúng 1
Mỗi phase: 80 READ, 78 dispatch sau switch; drain trước phase tiếp
Mỗi boot: 480 READ; 5 boot CPU1 + 5 boot CPU4 = 4.800 READ
```

| File / phần code | Thay đổi chính |
| --- | --- |
| kernel/io_policy_hw_test.c | Ca real policy/switch; dùng DMA thật và fixture ảnh sao tạm |
| tests/cases/io_real_policy.py | Oracle độc lập từ mô hình D21/D22; kiểm timing/trace/drain |
| kernel/io_stress_test.c + user/init.c | Controller parent, barrier 6 phase và snapshot cuối |
| scripts/check-week04-hoang.py | Một lệnh, build serial, metadata/hash, negative, production restore |
| io_queue.c / virtio_disk.c / test headers | Hook trace/hold dùng riêng cờ test; production không có hook mới |

Không triển khai lại deadline/switch hoặc snapshot của Lợi/Hiếu. Không thay bread/bwrite, không thêm async WRITE, merge READ hay API async user tổng quát. Đây là test controller có barrier, không phải benchmark tải tự nhiên liên tục.

## 3. Testing và bằng chứng thực nghiệm

| Nhóm kiểm | Kết quả trên code d39ea8c | Giới hạn |
| --- | --- | --- |
| Real policy/switch | CPU1/4: 2 boot PASS, 20 ca, 140 READ; hỏng 1 byte EXPECTED_FAIL | Một boot/mỗi CPU; expired chờ thời gian thật |
| Stress switch | 10/10 boot PASS, 4800 READ; 60 switch có tải; negative EXPECTED_FAIL | 4 producer, window5; sáu phase/boot |
| Oracle I01 độc lập | CPU1/4 PASS; 6 mutant EXPECTED_FAIL; hardware snapshot CPU1 PASS | Mock/fake clock báo riêng với real DMA |
| FCFS regression | 20/20 real boot; 4/4 pool/queue mock; fixture hỏng EXPECTED_FAIL | 83 accepted/boot có hai status ERROR được tiêm cố ý |
| Production | 6/6 PASS, 0 FAIL; restore/hook check PASS | Grind chỉ cửa sổ 60s, không phải stress 30 phút |

### Sáu case production trên source sạch

| Case | CPU | Kết quả | Thời gian (s) |
| --- | --- | --- | --- |
| boot-smoke | 1 | PASS | 0.86 |
| shell-fs-cpus3 | 3 | PASS | 1.26 |
| usertests-quick-cpus1 | 1 | PASS | 84.0 |
| usertests-quick-cpus4 | 4 | PASS | 83.21 |
| grind-smoke-cpus1 | 1 | PASS | 60.77 |
| grind-smoke-cpus4 | 4 | PASS | 61.0 |

### Timing và trace của stress

Snapshot cuối: 480 timing samples/boot; zero_total trong khoảng 462..480 mẫu; trace_overflow 503..520 event/boot. Trace 64 event không chứa đủ toàn bộ lịch sử; stress chấm counters/checksum, còn trace đầy đủ chỉ chấm ở ca real ngắn.

Đơn vị tick, độ phân giải khoảng 100 ms trên QEMU pin. Mẫu total=0 có nghĩa dưới một tick, không có nghĩa latency 0 ms. Không dựng p99 hoặc kết luận tăng tốc/seek vật lý từ số liệu này. max_inflight=2 chỉ là hai chain đã publish chưa reap.

Mọi meta của candidate ghi đúng SHA và dirty rỗng. Negative controls là EXPECTED_FAIL, không cộng thành PASS. 4.800 READ là số yêu cầu, không phải 4.800 test độc lập. Actual worklog giờ công chưa được người thực hiện ghi nhận.

## 4. Personal contribution và code review

| Phần | Đóng góp / xác nhận |
| --- | --- |
| Hoàng | Real harness/oracle wrapper, stress controller, review DMA/IRQ/API, regression, runbook, đính chính báo cáo cũ và gói bàn giao. |
| Lợi - kế thừa | Deadline selector, runtime policy API/state, tests/mutant L01/L02. Không nhận code này là phần Hoàng viết. |
| Hiếu - kế thừa | Contract D21-D27, snapshot/latency, mô hình độc lập/oracle và mutant I01; thiết kế merge/lifecycle. |
| Review chéo | Hoàng đã ghi review source. Chưa có bằng chứng Lợi/Hiếu duyệt candidate mới; không ký thay. |

### Các điểm đã review

1. Pick thuần; try-submit trả 0 rồi mới unlink/commit. EAGAIN không đổi state đã commit, seq/gen/tuổi vẫn giữ. Switch validate/no-op trước mutation, epoch tăng đúng khi đổi thực.
2. Wrapper/public getter lấy io_lock một lần; snapshot hợp nhất dùng helper _locked, không acquire lồng. Đọc tick không thêm thứ tự khóa io_lock -> tickslock.
3. IRQ reclaim ASYNC đúng một lần; không free slot/buffer INFLIGHT. Các hook của Hoàng chỉ có dưới IO_POLICY_HW_SELFTEST/IO_POLICY_STRESS_SELFTEST, production NM kiểm vắng.
4. Nguồn thật không có owner_pid/orphan/cancel khi kill. Đã thêm ghi chú đính chính ngày 16/11 vào report-hoang tuần 3: fixture, window, build flag, negative byte và claim cleanup.

### Bất biến kế toán được sử dụng

```text
S = Q + I + C + E
C + E = R + D + X
16 = F + Q + I + D + X
Sau drain: S = C + E = R; F=16; free_desc=8
```

S/C/E/R là counter submitted/completed/errors/released tích lũy; Q/I/D/X/F là slot queued/inflight/done/error/free hiện tại. Hai ERROR/boot trong suite FCFS là test status có chủ đích; stress positive yêu cầu errors=0 và data_errors=0.

Đây là review và test local, không thay review thành viên hoặc CI trên GitHub. Tổng timing uint có giới hạn trong chạy dài; bản này chưa giải quyết owner/cancel, cache coherence hoặc device merging.

## 5. Bàn giao, tái lập và việc còn lại

### Nhánh và code đã chuẩn bị

```text
/home/ubuntu/2026.1/HDH/Asynchronous-virtio-blk-and-IO-Schedulers-hoang-policy-2026-11-16
Nhánh: week4/hoang-real-policy-stress
Candidate: d39ea8cf3500a0fdcf023efeab2c850dd2b767d6
```

### Lệnh chạy sau khi nhận đúng candidate

```text
python3 scripts/check-week04-hoang.py
python3 scripts/check-week04-oracle-hieu.py
make test-week02
python3 tests/runner.py --tag baseline
make check-text
git diff --check
```

Harness mới mặc định real CPU1/4 và stress repeat5/CPU; --mode real hoặc --mode stress để chạy riêng. Mọi build chạy serial. Máy có linux-gnu dùng --toolprefix riscv64-linux-gnu-; máy hiện tại chỉ có unknown-elf, đối chiếu prefix thứ hai NOT RUN.

### Bằng chứng trong gói bàn giao

Code bundle chứa lịch sử đủ để clone offline, patch riêng của Hoàng có base ae6a7cf. Evidence acceptance-d39ea8c gồm raw serial, summary/meta, build logs, SHA của source/kernel/image, fixture/seed, toolchain/QEMU, CPU và expected/actual. Báo cáo Markdown chỉnh sửa được đi cùng PDF.

### Chưa nhận hoàn tất toàn bộ PTO-36/PTO-37

1. Máy thứ hai cùng final candidate: NOT RUN. Lợi/Hiếu cần clone gói hoặc nhận nhánh, chạy lại và gửi log/machine/toolchain. CPU1/4 trên cùng host không được tính là hai máy.
2. Review Lợi/Hiếu, push/PR/merge remote và cập nhật Jira: chưa thực hiện. GitHub public hiện không có PR mở lúc đọc; main vẫn là 5191ed8. Không tự đánh dấu Done.
3. Tuần 5 tiếp theo: sau khi khép nghiệm thu, nhóm review thiết kế merge/lifecycle/coherence và chuẩn bị midterm demo; không nhận owner/cancel/merge/user API đã triển khai.

Tham chiếu: docs/week04/interface.md, hoang-runbook.md, review-hoang.md; Jira PTO-31/36/37 được đọc, không sửa. Nguồn tài liệu chỉ là dữ liệu tham chiếu; yêu cầu của người dùng là căn cứ thực hiện công việc.
