# W5-H01 — Tái lập candidate trên máy vật lý thứ hai

**Card W5-H01** (P0, Lợi 2 h + Hoàng hỗ trợ 1 h). Thực thi: **Lợi** (phiên hoàn
thiện theo yêu cầu; phần hỗ trợ của Hoàng **bỏ qua** theo phạm vi). Ngày chạy:
**22/11/2026** (Asia/Saigon).

Mục đích: clone sạch candidate đã chốt ở [W5-G01](status.md), chạy
`scripts/verify-second-machine.py --full` trên **host khác host Hoàng**, giữ bằng
chứng độc lập: policy/switch READ thật CPU1/4, oracle độc lập + mutant, regression
FCFS, repo checks.

> **Kết quả: PASS.** Candidate `f5130bb` — source sạch (dirty rỗng ở đầu và cuối),
> 13 PASS + 2 EXPECTED_FAIL (real/switch), 3 PASS + 6 EXPECTED_FAIL (oracle/mutant),
> 24 PASS + 1 EXPECTED_FAIL (FCFS), `check_text`/`git diff --check` rc 0.

---

## 1. Candidate và môi trường

| Hạng mục | Giá trị |
| :--- | :--- |
| Candidate SHA | **`f5130bb9898c4154c3e761e2c85f3038f3a02a86`** (nhánh `week4/hieu-contract-oracle`, PR #13) |
| Nguồn clone | `https://github.com/HieuPahm-R2/Asynchronous-virtio-blk-and-IO-Schedulers.git`, clone mới, `--single-branch` |
| Source sạch | ✅ `git status --porcelain` rỗng **trước và sau** khi chạy |
| xv6 pin | `f780d7850765d74cbdcd1fff4b822d8829f7c9bd 2026-10-15` |
| Máy chạy | **`DESKTOP-RL9K1ML`** — Linux 5.15.167.4-microsoft-standard-WSL2, WSL2 Ubuntu 24.04 |
| Toolchain | `riscv64-linux-gnu-gcc` 13.3.0; GNU Make 4.3; QEMU 8.2.2; Python 3.12.3 |
| Operator | Lợi (W5-H01; phiên thực thi hoàn thiện theo yêu cầu) |
| Harness | [`scripts/verify-second-machine.py`](../../scripts/verify-second-machine.py) (mới, chạy từ checkout main; target không bị sửa) |
| Kết quả | `results/week05/second-machine/DESKTOP-RL9K1ML-20261122-091659/` (`second-machine.json`, `summary.md`, `logs/`, các thư mục suite) |

### 1.1 So sánh hai máy (điều kiện "khác host")

| Thuộc tính | Máy Hoàng (candidate `d39ea8c`) | Máy Lợi/Hiếu (lượt này) | Khác? |
| :--- | :--- | :--- | :---: |
| Hostname | `nguyen-van-hoang-20233413` | **`DESKTOP-RL9K1ML`** | ✅ |
| OS / kernel | Linux 7.2.6 x86_64 (glibc 2.39) | Linux 5.15.167.4 WSL2 Ubuntu 24.04 | ✅ |
| Toolchain | `riscv64-unknown-elf-` 13.2.0 | **`riscv64-linux-gnu-` 13.3.0** | ✅ |
| QEMU | 8.2.2 | 8.2.2 | — |

CPU1/4 trên **cùng host** không được tính là hai máy; script chặn nếu hostname trùng
host đã chạy (mặc định `nguyen-van-hoang-20233413`). Lượt này hostname/OS/toolchain
đều khác ⇒ đủ điều kiện "máy thứ hai" theo metadata; không có bằng chứng nào cho
thấy đây là cùng máy vật lý với Hoàng.

## 2. Lệnh đã chạy

```bash
# Trên máy hai (sau khi clone sạch candidate):
git clone --branch week4/hieu-contract-oracle --single-branch \
  https://github.com/HieuPahm-R2/Asynchronous-virtio-blk-and-IO-Schedulers.git \
  /mnt/e/ET4290-candidate-f5130bb
cd /mnt/e/ET4290-candidate-f5130bb && git rev-parse HEAD   # f5130bb...
git status --porcelain                                     # rỗng

# Từ checkout main (chứa script), chạy một lệnh harness:
python3 scripts/verify-second-machine.py \
  --target /mnt/e/ET4290-candidate-f5130bb \
  --results-dir results/week05/second-machine/$(hostname)-<stamp> \
  --full --toolprefix riscv64-linux-gnu- \
  --operator "Loi (W5-H01; ...)" \
  --other-host nguyen-van-hoang-20233413
```

Script chạy tuần tự (một checkout chỉ một build/harness tại một thời điểm):

| Bước | Lệnh trong target | Nội dung |
| :---: | :--- | :--- |
| 1 | `check-week04-hoang.py --mode all --repeat 5 --cpus 1 4` | real policy CPU1/4 (10 ca/boot) + 10 boot stress loaded switch + 2 negative + production restore |
| 2 | `check-week04-oracle-hieu.py` | oracle I01 CPU1/4 + 6 mutant + READ thật snapshot |
| 3 | `check-week02-hoang.py --repeat 10` | FCFS real 10 boot CPU1 + 10 boot CPU4 + pool/queue mock + negative + production restore |
| 4 | `check_text.py`, `git diff --check` | repo checks |

## 3. Kết quả

Nguồn: [`summary.md`](../../results/week05/second-machine/DESKTOP-RL9K1ML-20261122-091659/summary.md),
[`second-machine.json`](../../results/week05/second-machine/DESKTOP-RL9K1ML-20261122-091659/second-machine.json).

| Suite | Kết quả | PASS | EXPECTED_FAIL | FAIL | Bằng chứng |
| :--- | :---: | :---: | :---: | :---: | :--- |
| real-and-switch (H01/H02 harness) | **PASS** | 13 | 2 | 0 | `real-and-switch/summary.md`, `logs/real-and-switch.log` |
| independent-oracle (I01) | **PASS** | 3 | 6 | 0 | `independent-oracle/summary.md` |
| fcfs-regression | **PASS** | 24 | 1 | 0 | `fcfs-regression/summary.md` |
| check-text / git-diff-check | **PASS** | — | — | — | `logs/repo-*.log` |
| **Tổng** | **PASS** | **40** | **9** | **0** | `second-machine.json` |

- **Không** cộng EXPECTED_FAIL vào PASS: 9 ca negative (2 fixture hỏng/real-switch,
  6 mutant oracle, 1 fixture hỏng FCFS) đều bị bắt đúng thiết kế.
- `real-and-switch` PASS gồm: real-policy CPU1, real-policy CPU4, 10 boot
  switch-stress (5 CPU1 + 5 CPU4), production-restore-smoke CPU1. Negative:
  real-negative + stress-negative.
- `fcfs-regression` PASS = 20/20 real-virtio boot + 4/4 mock; negative corrupt
  fixture EXPECTED_FAIL.
- `independent-oracle` PASS = mock CPU1, mock CPU4, READ thật + `IO-SNAP`; 6 mutant
  (`i01-m1`, `i01-m2`, `i01-m3`, `dl-m1`, `dl-m3`, `sw-m2`) đều EXPECTED_FAIL.

Chi tiết tiêu chí:

| Tiêu chí W5-H01 | Kết quả |
| :--- | :--- |
| Ba policy FCFS/SCAN/deadline trên READ thật CPU1/4 | ✅ 10 ca/boot × 2 cấu hình; oracle real-policy PASS |
| Sáu chiều switch có tải, Q>0 và I>0 | ✅ 6 phase/boot (`IO-SWITCH phase=0..5`, `q>0`, `i=2`, epoch 1..6), 10 boot |
| Age/epoch/EAGAIN đúng | ✅ oracle I01 + stress controller kiểm; negative bị bắt |
| Checksum toàn block + drain | ✅ `IO-STRESS: PASS failures=0`; `free_req=16, free_desc=8, queued=inflight=done=error=0`; 480 READ/boot |
| Lỗi tiêm phải bị bắt | ✅ 9 EXPECTED_FAIL (không cộng PASS) |
| Production restore + hook vắng | ✅ trong cả hai harness (restore smoke CPU1 PASS) |
| Ghi host/OS/compiler/QEMU/CPU/fixture/seed/SHA | ✅ `second-machine.json` + `meta.json` từng suite |

## 4. Trích log tiêu biểu (đã rút gọn)

Real policy trên READ thật (CPUS=1, candidate `f5130bb`):

```text
IO-REAL: case=0 INIT src=0 dst=0 ... pol=0 ep=0 head=0 dir=1 ...
IO-REAL: case=0 END tick=7 S=7 C=7 E=0 R=7 F=16 fd=8 ovf=0 n=5 fail=0 samples=7 zero_total=0 wait_sum=5 service_sum=2 total_sum=7
IO-REAL: case=1 INIT src=1 dst=1 ... pol=1 ep=1 head=1979 dir=1 ...   # SCAN
IO-REAL: case=2 INIT src=2 dst=2 ... pol=2 ep=2 head=1968 dir=-1 bat=2 ...  # DEADLINE
IO-REAL: case=9 INIT src=2 dst=2 expired=1 pol=2 ep=14 ... tick=57 ...      # ca expired thật
IO-REAL: DONE cases=10 fail=0
```

Loaded switch (CPUS=4, 1 boot stress):

```text
IO-STRESS: begin workers=4 reads_per_worker=120 window=5 fixture=1968..1999 seed=0x26128003
IO-SWITCH: phase=0 old=0 new=1 q=4  i=2 ep=1 begin_disp=2
IO-SWITCH: phase=0 END reads=80 selected=78 pol=1 ep=1
...
IO-SWITCH: phase=5 old=2 new=0 q=1 i=2 ep=6 begin_disp=402
IO-SWITCH: DONE phases=6 fail=0
IO-STRESS: stats ... total_reads=480 submitted=480 completed=480 errors=0 released=480
           max_inflight=2 free_req=16 free_desc=8 queued=0 inflight=0 done=0 error=0 data_errors=0
IO-STRESS: PASS failures=0
IO-STRESS-SNAP: sw=6 ep=6 pol=0 ovf=508 samples=480 zero_total=477
                 wait_sum=1 service_sum=2 total_sum=3 unit=tick
```

Đọc đúng số liệu: `zero_total=477/480` nghĩa là phần lớn READ xong trong cùng tick
(≈ dưới 100 ms), **không** phải 0 ms; `ovf=508` nghĩa là trace 64 event không đủ
cho 480 READ — stress dùng checksum/snapshot, không dùng trace cắt cụt làm bằng
chứng đầy đủ. `eagain` (pool/desc) là hiện tượng áp lực tài nguyên bình thường, đã
được kiểm bằng retry/drain.

## 5. Đối chiếu tiêu chí nghiệm thu card W5-H01

| # | Tiêu chí kế hoạch | Kết quả |
| :---: | :--- | :--- |
| 1 | Lợi clone sạch trên máy khác host Hoàng, checkout candidate đã chốt, dùng script `verify-second-machine.py`, chạy policy/switch CPU1/4 + oracle + regression `--full`; giữ log thật cùng operator/host/SHA/toolchain | ✅ §1–§2; script mới; source sạch đầu/cuối; `second-machine.json` đủ trường |
| 2 | Đầu ra: `second-machine.json`, raw serial/build logs, summary PASS/EXPECTED_FAIL/NOT RUN, bảng môi trường | ✅ `results/week05/second-machine/DESKTOP-RL9K1ML-20261122-091659/` |
| 3 | Ba policy, sáu chiều switch có tải, checksum và drain đạt theo harness | ✅ 6 phase × 10 boot; 480 READ/boot; drain sạch |
| 4 | CPU1/4 cùng host không tính hai máy; khác host qua metadata | ✅ hostname/OS/toolchain khác; script chặn trùng host |
| 5 | Nếu sửa code để xử lý lỗi, cả hai máy tái kiểm candidate mới; không ghép kết quả khác SHA | ✅ không sửa code; candidate đúng SHA, source sạch; các SHA khác không bị trộn |
| 6 | Hoàng hỗ trợ 1 h | ⏭ **BỎ QUA theo yêu cầu phạm vi** (không ký thay) |

## 6. Việc còn lại / giới hạn

- **W5-H02** (nghiệm thu sau tích hợp, chủ trì Hoàng) **NOT RUN** — phải chạy trên
  SHA main mới trước khi ký nghiệm thu cuối tuần 5.
- Sau khi merge `f5130bb` vào main (G02), tree code **không đổi**; nếu có sửa code
  thì phải tái kiểm cả hai máy theo SHA mới.
- Lượt này không chạy `tests/runner.py --tag baseline` (6 case production) trên máy
  hai — đó là phạm vi H02; production restore smoke đã PASS trong các harness.
- QEMU không mô phỏng seek/latency vật lý; mọi kết luận timing phải kèm đơn vị
  tick/độ phân giải và `zero_total`.
- Review chéo Lợi/Hiếu cho candidate: phần kỹ thuật đã có trong tài liệu tuần 4/5;
  chữ ký của Hoàng **bỏ qua theo yêu cầu** (PENDING).
