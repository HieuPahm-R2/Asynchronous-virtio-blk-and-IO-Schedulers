# W5-G03 — Demo async READ và trạng thái câu hỏi GV

**Card W5-G03** (P1, 2 h; Lợi 1 h + Hoàng 0,5 h + Hiếu 0,5 h). Chủ trì: **Lợi**;
hỗ trợ: Hiếu (oracle/checksum) trong phiên hoàn thiện. Ngày: **22/11/2026**.

Mục đích: runbook + transcript demo **10 phút** cho: nhiều READ outstanding, ba
policy FCFS/SCAN/deadline, đổi policy khi Q/I khác 0, checksum và snapshot tài
nguyên sau drain. Người khác phải chạy lại được từ SHA/lệnh/fixture ghi trong tài
liệu này.

> Giới hạn phải nói khi demo: đây là **kernel control/test program**, **chưa có
> syscall user** tổng quát; QEMU virtio-blk **không** chứng minh seek/latency vật
> lý; tick ≈ 100 ms nên `0 tick` là **dưới 1 tick**, không phải 0 ms; 480 READ/boot
> là **480 request trong một boot**, không phải 480 test độc lập.

---

## 1. Điều kiện và một lệnh chạy

- Checkout: `main` sau tích hợp (`efe2849…`, code trùng candidate `f5130bb`) hoặc
  chính checkout H01 `f5130bb`; source **không dirty** ở phần code.
- Công cụ: WSL2 Ubuntu/Ubuntu, `make`, `python3`, một trong
  `riscv64-unknown-elf-*` / `riscv64-linux-gnu-*`, QEMU ≥ 7.2.
- Fixture: 32 block cuối ảnh `1968..1999`, seed `0x26128003`; harness tự sao
  `fs.img` sang thư mục tạm, xác minh bitmap free trước khi ghi fixture; negative
  chỉ lật byte đầu block `1968` trên bản sao.

```bash
# Demo chính (READ thật, ba policy, sáu chiều switch có tải; ~1 phút):
python3 scripts/check-week04-hoang.py --mode all --repeat 1 \
  --toolprefix riscv64-linux-gnu- \
  --results-dir results/demo-week5

# Oracle độc lập + mutant (mock + READ thật snapshot; ~2 phút):
python3 scripts/check-week04-oracle-hieu.py --results-dir results/demo-week5-oracle

# Máy khác chạy lại toàn bộ candidate (policy/switch + oracle + regression):
python3 scripts/verify-second-machine.py --target <clean-candidate> \
  --results-dir results/week05/second-machine/<host>-<stamp> --full
```

Kết quả mong đợi: các dòng `IO-REAL: ... PASS`, `IO-STRESS: PASS`, `IO-SWITCH:
DONE phases=6 fail=0`, `IO-STRESS-SNAP: ...`, `IO-HWTEST: PASS`, và cuối cùng là
trạng thái `PASS` của harness kèm summary/meta/log.

## 2. Kịch bản 10 phút

| Phút | Nội dung | Lệnh/điểm nhấn |
| :---: | :--- | :--- |
| 0–1 | Mở đầu: bài toán async READ trên xv6, pool 16 slot, `NUM=8` descriptor, ba policy; nêu giới hạn QEMU/kernel control | `git rev-parse HEAD`; sơ đồ `docs/architecture.md` §2.4 |
| 1–3 | Build + boot nhanh; chỉ vào log monitor | `make clean && make`; `make qemu CPUS=1` (Ctrl-A X để thoát) |
| 3–5 | **Ba policy trên READ thật**: FCFS theo thứ tự đến; SCAN đi theo chiều + đảo tại biên 1999; DEADLINE ưu tiên request quá hạn 50 tick, batch 4 | `IO-REAL: case=0/1/2 ... pol=0/1/2`; `EV B bnd=1999`; `EV D pol=2 rsn=1/2/3` |
| 5–6.5 | **Một request bị chờ thật sự quá hạn**: ca `expired=1`, `tick=57`, `wait_sum` tăng | `IO-REAL: case=9 INIT ... expired=1 ... tick=57`; `END ... total_sum=357` |
| 6.5–8 | **Đổi policy khi có tải** (4 producer × 120 READ, window 5): sáu phase Q>0, I=2, epoch 1..6; phần lớn READ còn lại dispatch dưới policy đích trước khi đổi tiếp | `IO-SWITCH: phase=0..5` + `END reads=80 selected=78 pol=...`; `DONE phases=6 fail=0` |
| 8–9 | **Checksum + drain + snapshot**: 480 READ/boot, checksum từng block, `free_req=16/free_desc=8`, `Q=I=D=X=0`; trace overflow được đếm (dùng counters, không dùng trace cắt cụt) | `IO-STRESS: stats ...`; `IO-STRESS-SNAP: sw=6 ep=6 samples=480 zero_total=477 ovf=508` |
| 9–10 | **Oracle độc lập + mutant**: mô hình tính expected từ contract; 6 mutant cố ý bị bắt (`EXPECTED_FAIL`); READ thật snapshot `IO-SNAP` | `python3 scripts/check-week04-oracle-hieu.py`; log `mutant ... EXPECTED_FAIL` |

**Câu chốt khi demo:** "Thứ tự **dispatch** khác thứ tự **hoàn tất**; policy chỉ
quyết định dispatch order. Số liệu timing là tick 100 ms — mẫu 0 là dưới 1 tick.
Ba policy và switch có tải đã chạy trên READ thật; merge/owner-cancel chỉ là thiết
kế."

## 3. Transcript thực tế (rút gọn)

Nguồn: máy hai `DESKTOP-RL9K1ML`, candidate `f5130bb`, ngày 22/11/2026 —
`results/week05/second-machine/DESKTOP-RL9K1ML-20261122-091659/`:

```text
# 1) Ba policy trên READ thật (CPUS=1)
IO-REAL: case=0 INIT src=0 dst=0 expired=0 pol=0 ep=0 head=0 dir=1 bat=0 last=1979 has=1 tick=6 q=5 i=2
IO-REAL: case=0 END tick=7 S=7 C=7 E=0 R=7 F=16 fd=8 ovf=0 n=5 fail=0 samples=7 zero_total=0 wait_sum=5 service_sum=2 total_sum=7
IO-REAL: case=1 INIT src=1 dst=1 expired=0 pol=1 ep=1 head=1979 dir=1 bat=0 last=1979 has=1
IO-REAL: case=1 EV B bnd=1999 hb=1996 ha=1996 db=1 da=-1 ep=1
IO-REAL: case=2 INIT src=2 dst=2 expired=0 pol=2 ep=2 head=1968 dir=-1 bat=2 last=1979
IO-REAL: case=2 EV D pol=2 rsn=3 seq=17 blk=1996 hb=1968 ha=1968 db=-1 da=-1 bat=0 ep=2   # FIFO batch boundary
IO-REAL: case=9 INIT src=2 dst=2 expired=1 pol=2 ep=14 head=1968 dir=-1 bat=2 last=1979 tick=57
IO-REAL: case=9 END tick=57 S=70 C=70 E=0 R=70 F=16 fd=8 ovf=0 n=5 fail=0 samples=70 zero_total=56 wait_sum=255 service_sum=102 total_sum=357
IO-REAL: DONE cases=10 fail=0
```

```text
# 2) Switch có tải (CPUS=4, 1 boot; mỗi boot 4 worker × 120 READ)
IO-STRESS: begin workers=4 reads_per_worker=120 window=5 fixture=1968..1999 seed=0x26128003
IO-SWITCH: phase=0 old=0 new=1 q=4  i=2 ep=1 begin_disp=2
IO-SWITCH: phase=0 END reads=80 selected=78 pol=1 ep=1
IO-SWITCH: phase=1 old=1 new=2 q=2  i=2 ep=2 begin_disp=82
IO-SWITCH: phase=2 old=2 new=1 q=14 i=2 ep=3 begin_disp=162
IO-SWITCH: phase=3 old=1 new=0 q=1  i=2 ep=4 begin_disp=242
IO-SWITCH: phase=4 old=0 new=2 q=3  i=2 ep=5 begin_disp=322
IO-SWITCH: phase=5 old=2 new=0 q=1  i=2 ep=6 begin_disp=402
IO-SWITCH: phase=5 END reads=80 selected=78 pol=0 ep=6
IO-SWITCH: DONE phases=6 fail=0
IO-STRESS: stats workers=4 total_reads=480 submitted=480 completed=480 errors=0 released=480
           max_inflight=2 free_req=16 free_desc=8 queued=0 inflight=0 done=0 error=0
           eagain_pool=210 eagain_desc=212 q_enqueued=480 q_dispatched=480 q_eagain=212
           head_reuse=438 data_errors=0
IO-STRESS: PASS failures=0
IO-STRESS-SNAP: sw=6 ep=6 pol=0 ovf=508 samples=480 zero_total=477 wait_sum=1 service_sum=2 total_sum=3 unit=tick
```

```text
# 3) Oracle độc lập + mutant (trích summary H01)
independent-oracle: PASS (PASS=3, EXPECTED_FAIL=6)
  i01-m1-expired-latest / i01-m2-noop-epoch / i01-m3-keep-batch /
  dl-m1-no-expired / dl-m3-eagain-batch / sw-m2-reset-age: EXPECTED_FAIL
```

Đọc đúng: `selected=78` mỗi phase nghĩa là 78 READ còn lại thực sự được dispatch
dưới policy đích trước khi đổi tiếp (không chỉ đổi tên policy 6 lần rồi chạy FCFS);
`eagain_*` là retry do áp lực pool/descriptor; `zero_total=477/480` là giới hạn độ
phân giải tick; `ovf=508` là trace overflow — stress dùng counters/checksum.

## 4. Trạng thái câu hỏi GV / midterm

Kế hoạch yêu cầu Lợi đối chiếu phản hồi GV về lịch midterm, SCAN/LOOK, API và
rubric. Trong phiên này **không có nguồn phản hồi GV nào trong repo/Jira truy cập
được**, nên tất cả giữ **PENDING**, không suy diễn thành "GV đã xác nhận":

| Câu hỏi | Nguồn | Trạng thái |
| :--- | :--- | :---: |
| Q1 — Tag/commit xv6 chính thức | PTO-7, docs/week03 §8 | **PENDING** |
| Q2 — Async WRITE có bắt buộc? | PTO-7/Q2 | **PENDING** |
| Q3 — API kernel hay syscall user? | PTO-7/Q3 | **PENDING** |
| Q4 — SCAN hay LOOK là yêu cầu chính thức? | PTO-7/Q4 | **PENDING** |
| Q5 — Rubric 40/35/25 có áp dụng? | PTO-7 | **PENDING** |
| Q6 — Merge READ mức thiết bị / tối đa 4 block? | PTO-7/Q6 | **PENDING** |
| Q7 — Có được tăng `NUM` descriptor? | PTO-7/Q7 | **PENDING** |
| Q8 — Coherence với buffer cache/`bread`? | PTO-7/Q8 | **PENDING** |
| Lịch midterm / check-in giữa kỳ | Kế hoạch tuần 5 §W5-G03 | **PENDING — không có phản hồi GV trong repo** |

Hành động đã làm: giữ nguyên PTO-7/Q1–Q8 **Pending**, không sửa Jira, không tuyên
bố lịch GV; ghi rõ mốc 22/11 là **mốc nội bộ nhóm**.

## 5. Runbook cho người chạy lại (không dùng lời kể thay log)

1. `git clone`/`git switch` đúng SHA trong §1; `git status --porcelain` rỗng ở phần code.
2. Chạy lệnh §1 (harness tự build clean từng cấu hình, tự sao fixture, tự restore production).
3. Kiểm log: `real-policy-cpus1/4.log`, `switch-stress-*-cpus1/4.log`,
   `real-negative`, `stress-negative`, `production-smoke.log`.
4. Đối chiếu expected: `real-*`/`switch-stress-*` = PASS; negative = **EXPECTED_FAIL**;
   không chấp nhận nếu thiếu marker/END hoặc timeout (harness coi là FAIL).
5. So SHA/máy/toolchain trong `meta.json` với SHA/máy bạn đang chạy; không trộn
   log khác SHA.
6. Lưu `summary.md`, `meta.json`, raw log vào `results/week05/…`.

## 6. Đối chiếu tiêu chí nghiệm thu card W5-G03

| # | Tiêu chí kế hoạch | Kết quả |
| :---: | :--- | :--- |
| 1 | Demo 10 phút: submit nhiều READ trước wait, ba policy, switch khi Q/I khác 0, checksum và snapshot drain | ✅ kịch bản §2 + transcript §3 (480 READ/boot, 6 phase Q>0/I=2, checksum, drain snapshot) |
| 2 | Runbook/demo transcript có SHA, lệnh và fixture; trạng thái các câu hỏi GV | ✅ §1/§3/§5; câu hỏi GV **PENDING** (§4) |
| 3 | Người khác chạy lại được | ✅ một lệnh harness + runbook; second-machine đã chạy lại độc lập |
| 4 | Không tự coi 22/11 là lịch GV; chưa có syscall user thì nêu rõ demo dùng kernel control/test program | ✅ ghi rõ ở đầu tài liệu và §4 |

## 7. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-22 | candidate `f5130bb`; main `efe2849` | Runbook + transcript demo 10 phút (3 policy, 6 chiều switch có tải, checksum, drain snapshot); trạng thái câu hỏi GV PENDING; giới hạn kernel control/tick 100 ms. |
