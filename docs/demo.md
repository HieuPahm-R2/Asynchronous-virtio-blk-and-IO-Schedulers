# Demo — xem cái gì, chạy cái gì

Tài liệu này trả lời: kèm kết quả mẫu chạy thật trên base hiện tại và storyboard cho demo cuối kỳ 20 phút.

> Nguyên tắc: **demo là chạy thật + log thật**, không phải đọc slide.
> Mọi con số phải mở được file bằng chứng trong `results/` hoặc `docs/`.
> Phần chưa làm thì ghi rõ **chưa có**, không diễn cho giống đã xong.

## 1. Demo theo từng mốc của học phần

| Mốc | Thời lượng | Demo cái gì | Bằng chứng trong repo |
| --- | --- | --- | --- |
| **Check-in tuần 1** | 10 phút | môi trường build/boot, baseline stock, sơ đồ I/O, phân công, blocker | `make demo`, `results/baseline/<ts>/`, `docs/architecture.md` |
| Proposal (tuần học phần 3) | 2–3 trang + trao đổi | chốt interface/lock/scope, trace FCFS/SCAN trên giấy | `docs/architecture.md`, test case skeleton |
| Midterm (tuần học phần 5) | 10 phút | core chạy một phần + test đầu tiên | `make test` PASS, PR/issue |
| Code freeze (tuần 8) | — | tag final, build từ clone mới | tag + log CI |
| **Final demo (tuần 9)** | **20 phút kể cả Q&A** | 6 phần bên dưới | trace, đồ thị, stress log, checksum |

## 2. Check-in tuần 1 (10 phút) — chạy được ngay hôm nay

### 2.1 Kịch bản theo mục 8 của kế hoạch

| Phút | Nội dung | Thao tác trên máy |
| ---: | --- | --- |
| 0–1 | Mục tiêu/phạm vi đề tài (1 câu) | slide 1 dòng |
| 1–3 | Baseline & môi trường | `make demo` (phần 1, 2, 4, 5) |
| 3–6 | Sơ đồ submit/completion + rủi ro | mở [`architecture.md`](architecture.md) (Mermaid) |
| 6–8 | Phân công tuần 2, mỗi người 1 module kernel | README mục "Nhóm" |
| 8–10 | Blocker + câu hỏi GV + kế hoạch tuần sau | README mục "Việc cần chốt" |

### 2.2 Ba thứ nên mở sẵn trước khi vào

1. Terminal chạy `make demo` (nên chạy nóng trước 1 lần cho cache build).
2. [`docs/architecture.md`](architecture.md) — sơ đồ Mermaid + lifecycle request.
3. `results/baseline/<timestamp>/summary.md` — bảng 6/6 PASS.

### 2.3 Output mẫu — chạy thật trên base hiện tại

`make demo` (rút gọn, nguyên bản dài hơn):

```text
================================================================
 1/6. MÔI TRƯỜNG & PIN XV6
================================================================
  Distro:             Ubuntu 24.04 LTS
  Kernel:             Linux 6.x ... x86_64
  CPU / RAM:          6 CPU / 7.7Gi
  Project commit:     29774c8 main
  xv6 pin:            f780d7850765... 2026-10-15
  RISC-V gcc:         riscv64-linux-gnu-gcc (Ubuntu 13.3.0...) 13.3.0
  QEMU:               QEMU emulator version 8.2.2
  -> Không có /dev/kvm — QEMU chạy TCG (chậm hơn KVM, vẫn đúng chức năng)

================================================================
 2/6. BUILD MỘT LỆNH
================================================================
  make kernel/kernel fs.img:   OK (1 giây)
  kernel/kernel:               272K
  fs.img:                      2.0M

================================================================
 3/6. BOOT XV6 TRONG QEMU (CPUS=1)
================================================================
  xv6 kernel is booting
  init: starting sh
  $ echo BOOT_OK
  BOOT_OK
  $
  -> PASS: xv6 boot, init chạy, shell nhận lệnh

================================================================
 4/6. TEST HARNESS — PASS/FAIL TỪNG CASE (make test-fast)
================================================================
--- [1/2] boot-smoke (CPUS=1) ... PASS (3.1s)
--- [2/2] shell-fs-cpus3 (CPUS=3) ... PASS (4.1s)
== Kết quả: 2 PASS / 0 FAIL ==

================================================================
 5/6. BASELINE STOCK ĐÃ ĐO (bằng chứng tuần 1)
================================================================
  | `boot-smoke`            | 1 | PASS | 3.50  |
  | `shell-fs-cpus3`        | 3 | PASS | 4.27  |
  | `usertests-quick-cpus1` | 1 | PASS | 536.77|
  | `usertests-quick-cpus4` | 4 | PASS | 492.98|
  | `grind-smoke-cpus1`     | 1 | PASS | 63.00 |
  | `grind-smoke-cpus4`     | 4 | PASS | 63.27 |
  -> 6 PASS / 0 FAIL — results/baseline/2026-10-19_222935/

================================================================
 6/6. HẠ TẦNG CHỜ CHO TUẦN 2 TRỞ ĐI
================================================================
  (danh sách 8 test case: boot, shell, usertests, grind...)
  => TẤT CẢ PASS: môi trường + build + boot + test + baseline đều sẵn sàng.
```

Bản đầy đủ: chạy `make demo` trên máy bạn. Boot serial nằm ở
`results/local/demo/logs/boot-smoke.log`, baseline ở
[`../results/baseline/2026-10-19_222935/summary.md`](../results/baseline/2026-10-19_222935/summary.md).

## 3. Final demo 20 phút (tuần 9) — storyboard

Theo mục 10 của kế hoạch. Cột "hiện có" cho biết phần nào base đã có sẵn hôm nay,
phần nào sẽ được xây ở tuần 2–8.

| Phút | Phần | Show gì (khi hoàn thành) | Hiện có |
| ---: | --- | --- | --- |
| 0–2 | Kiến trúc | sơ đồ đường I/O + state machine request + lock order | ✅ `docs/architecture.md` |
| 2–6 | Async & nhiều outstanding | submit nhiều request, kernel trace `INFLIGHT`, counter `max_inflight ≥ 2`, kết quả đúng | ⏳ cần code + user program |
| 6–10 | Đổi scheduler khi đang chạy | workload đang chạy, đổi FCFS→SCAN→deadline, trace dispatch, counter `policy_switch`, không mất request | ⏳ |
| 10–13 | Merging + checksum | nhiều request read liền kề → **một** lệnh thiết bị, checksum đúng từng request con, descriptor exhaustion test | ⏳ |
| 13–16 | Đồ thị + stress + hạn chế | throughput/latency cùng workload, p50/p95, log stress 30 phút, danh sách hạn chế | ✅ số baseline, ⏳ đồ thị scheduler |
| 16–20 | Q&A | mỗi người giải thích module kernel của mình | — |

### 3.1 Demo sẽ "trông như thế nào" — ví dụ trace dự kiến (chưa có, tuần 2–5 sẽ in ra)

Khi có tính năng, demo là một chuỗi lệnh ngắn, mỗi lệnh in ra bằng chứng:

```text
$ iotest async 4            # submit 4 read bất đồng bộ rồi làm việc khác
SUBMIT   id=1 seq=1 sector=100 nbytes=1024
SUBMIT   id=2 seq=2 sector=102 nbytes=1024
SUBMIT   id=3 seq=3 sector=104 nbytes=1024
SUBMIT   id=4 seq=4 sector=106 nbytes=1024
WORK     caller làm việc khác trong lúc chờ
DISPATCH id=2 policy=FCFS max_inflight=2
DISPATCH id=1 policy=FCFS max_inflight=2
COMPLETE id=2 checksum=OK
...
RESULT   max_inflight=2 (>=2), 4 request, checksum ALL OK
```

```text
$ sched FCFS; iotest randread 20; sched switch SCAN
POLICY   FCFS -> SCAN (policy_switch=1, queued=7, inflight=2)
DISPATCH id=3 sector=180 dir=up
DISPATCH id=5 sector=196 dir=up
DISPATCH id=7 sector=204 dir=up
REVERSE  head=capacity, dir=down          # SCAN khác LOOK ở chỗ đi tới biên
DISPATCH id=2 sector=196 dir=down
RESULT   no request lost, queued/inflight preserved
```

```text
$ iotest merge                 # 8 logical read liền kề
MERGE    children=[1,2,3,4] -> device_cmd sector=100 nbytes=4096
MERGE    children=[5,6,7,8] -> device_cmd sector=108 nbytes=4096
COMPLETE child=1 checksum=OK ... child=8 checksum=OK
RESULT   logical=8 device_cmds=2 merge_ratio=4.0, descriptor leak=0
```

```text
$ make bench                   # kết quả thật khi có scheduler
policy   merge  throughput(MB/s)  latency p50/p95 (ms)  max_inflight
stock    -      1.0               ...
FCFS     off    ...               ...
FCFS     on     ...               ...
SCAN     off    ...
SCAN     on     ...
deadline off    ...
deadline on     ...
→ đồ thị: results/bench/<timestamp>/throughput.png
```

> Các chương trình `iotest`/`sched`/`bench` **chưa tồn tại** — chúng là việc của
> tuần 2–8. Base hiện có harness QEMU để chạy chúng dưới dạng test case khi xong.

### 3.2 Điều bắt buộc theo spec

- Mỗi thành viên **tự trình bày module kernel mình làm** (không để 1 người nói hết).
- Chuẩn bị workload ngắn (≤ 2 phút) tái lập được; log stress 30 phút là bằng chứng bổ sung.
- Q&A 4 phút: trả lời được vì sao thứ tự dispatch đúng, vì sao không mất wakeup,
  vì sao merging không sai dữ liệu, vì sao không rò descriptor.

## 4. Checklist trước buổi demo (tự kiểm 10 phút)

- [ ] Cùng commit đã push: `git rev-parse HEAD` khớp commit trên GitHub.
- [ ] `make env-check` PASS trên **đúng máy demo**.
- [ ] `make demo` PASS; mở sẵn `results/baseline/<ts>/summary.md`.
- [ ] Các log/trace/đồ thị cần demo đã có trong `results/` (không phụ thuộc mạng).
- [ ] Không dùng số liệu chưa có log; phần chưa làm thì nói "chưa có / kế hoạch tuần X".
- [ ] Quay video dự phòng 2–3 phút toàn bộ luồng demo (trường hợp QEMU lỗi tại chỗ).
- [ ] Tắt thông báo; terminal font đủ lớn; đóng tab thừa.
- [ ] Mỗi người biết phần mình nói + 2 câu Q&A dự kiến.

## 5. Lỗi thường gặp khi demo & cách xử lý

| Tình huống | Xử lý ngay |
| --- | --- |
| QEMU khởi động chậm/vướng | chạy `make demo DEMO_ARGS=--no-qemu`, dùng video dự phòng, chỉ vào log đã lưu |
| Build fail tại chỗ | chạy `make env-check` và nói rõ đây là môi trường; mở log baseline đã lưu |
| Mất mạng | mọi thứ đã local (source + log), không cần mạng để demo |
| GV hỏi số liệu | mở đúng file `results/.../summary.md` + `meta.json` (commit, toolchain, CPUS) |
| Thời gian trôi | bám mốc phút trong bảng; phần Q&A luôn giữ 4 phút |
| Câu hỏi ngoài phạm vi | ghi vào "pending" — không trả lời phỏng đoán |
