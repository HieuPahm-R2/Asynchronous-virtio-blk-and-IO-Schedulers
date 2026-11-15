# W4-G01 — Evidence index tuần 4 (kiểm kê bằng chứng)

Mục đích: một bảng tra **mọi kết quả tuần 4 đang có trong repo**, kèm revision, máy,
lệnh, loại bằng chứng và **điều nó chứng minh / không chứng minh**. Chỉ những gì
được dẫn ở đây mới được dùng trong báo cáo/nghiệm thu; log tuần 3 là **tham chiếu
lịch sử**, không cộng vào chỉ tiêu tuần 4.

Nguyên tắc đọc:

- **Mock** (driver giả + đồng hồ giả) không chứng minh READ thật, seek hay latency.
- **READ thật** trên QEMU không chứng minh tăng tốc thiết bị vật lý.
- Negative control báo **EXPECTED_FAIL** riêng, không cộng vào PASS.
- Thiếu marker/END/timeout là **FAIL**, không phải PASS.
- Mỗi lượt chạy phải có metadata theo D25; thiếu trường nào ghi rõ trường đó.

---

## 1. Bảng evidence chính

| ID | Nội dung | Revision / nhánh | Máy / môi trường | Lệnh | Trạng thái | Đường dẫn |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- |
| **E1** | W3 carry-over: SCAN mock 10 ca + unlink, 3 mutant, FCFS/SCAN mock | `5191ed8` (main) | WSL2 Linux 6.18; `riscv64-linux-gnu-` | `python3 scripts/check-week03-scan.py` | PASS (tham chiếu lịch sử) | `results/week03/…`; plan tuần 4 §01A |
| **E2** | W4-L01/L02 deadline + switch + SCAN + FCFS **mock** CPU1/4 + 6 mutant | `5191ed8` (`week4/loi-deadline-switch`), dirty | WSL2 `haree` (host `Linux-6.18.58.1-microsoft-standard-WSL2`) | `python3 scripts/check-week04-policy.py` | **PASS**; 6 mutant EXPECTED_FAIL | [`results/week04/policy-mock/haree-20261115-035243/`](../../results/week04/policy-mock/haree-20261115-035243/summary.md) |
| **E3** | SCAN oracle regression (mock) CPU1/4 + 3 mutant | `5191ed8`, dirty | WSL2 `laptop-Loi` | `python3 scripts/check-week03-scan.py` | **PASS** | [`results/week04/scan-regression/laptop-Loi-20261115-050521/`](../../results/week04/scan-regression/laptop-Loi-20261115-050521/summary.md) |
| **E4** | FCFS READ thật 10 boot CPU1 + 10 boot CPU4, pool/queue mock, 6 case production? (một phần) + negative corrupt fixture | `5191ed8`, dirty, `TOOLPREFIX=riscv64-linux-gnu-` | WSL2 `laptop-Loi`; QEMU 8.2.2 | `python3 scripts/check-week02-hoang.py` | **PASS** 20/20 real-virtio; negative **EXPECTED_FAIL** | [`results/week04/fcfs-regression/laptop-Loi-20261115-050755/`](../../results/week04/fcfs-regression/laptop-Loi-20261115-050755/summary.md) |
| **E5** | Stress smoke 1 boot CPU1 + 1 CPU4 (4×120 READ, window 5, seed `0x26128003`), negative corrupt fixture | `5191ed8`, dirty | WSL2 `laptop-Loi` | `python3 scripts/check-week03-stress.py --repeat 1` | **PASS** smoke; **chưa** đủ 10 boot | [`results/week04/stress-smoke/laptop-Loi-20261115-055840/`](../../results/week04/stress-smoke/laptop-Loi-20261115-055840/summary.md) |
| **E6** | **Oracle I01 độc lập** (deadline D21 + switch D22/D23 + snapshot) trên mock CPU1/4; regression SCAN/FCFS/L02 | `360b4df` (`week4/hieu-contract-oracle`), dirty rỗng | WSL2 `DESKTOP-RL9K1ML`; gcc 13.3.0, QEMU 8.2.2, make 4.3 | `python3 scripts/check-week04-oracle-hieu.py` | **PASS** cả 2 cấu hình | [`results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/`](../../results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/summary.md) |
| **E7** | Negative control I01: 6 mutant deadline/switch (`i01-m1..m3`, `dl-m1`, `dl-m3`, `sw-m2`) bị oracle độc lập bắt | `360b4df` | WSL2 `DESKTOP-RL9K1ML` | trong E6 | **EXPECTED_FAIL** 6/6 | log `*-cpus1.log` trong E6 |
| **E8** | READ thật cơ bản (FCFS, `IO_HW_SELFTEST`) + `IO-SNAP` snapshot/latency lần đầu | `360b4df` | WSL2 `DESKTOP-RL9K1ML`, CPUS=1 | trong E6 | **PASS**; 83 samples, `zero_total=83` | `hw-cpus1-snap.log` trong E6; phân tích [`measurement.md`](measurement.md) §2.1 |
| **E9** | Production restore + hook test vắng + `check_text.py` + `git diff --check` | `360b4df` | WSL2 `DESKTOP-RL9K1ML` | trong E6 | **PASS** | `meta.json` E6 (`production_hooks_absent=true`, rc 0) |
| **E10** | Negative fixture sai byte (block `FSSIZE-32`) bị chặn | `5191ed8`/`360b4df` | WSL2 Lợi + Hiếu | harness H02 / E4/E5 | **EXPECTED_FAIL** (đúng thiết kế) | E4, E5 |
| **E11** | Snapshot schema + kết quả mẫu + giải thích độ phân giải tick | `360b4df` | — | — | tài liệu | [`measurement.md`](measurement.md) |

Ghi chú revision: E2–E5 chạy khi code L01/L02 còn **dirty** (dirty dài 361–380 ký
tự) trên nhánh `week4/loi-deadline-switch`; evidence được commit sau (commit
`0dc296e`). E6–E9 chạy trên code **đã commit sạch** `360b4df` (dirty rỗng), evidence
ở commit `4fa4de9`. Vì vậy E6–E9 là mốc dùng cho phần I01; E2–E5 là mốc dùng cho
L01/L02, cần tái chạy trên candidate SHA cuối ở G02.

---

## 2. Kết quả chi tiết I01 (E6–E9)

Nguồn: `results/week04/oracle-hieu/DESKTOP-RL9K1ML-20261115-163025/`.

| Kiểm | Kết quả | Ghi chú |
| :--- | :---: | :--- |
| Oracle deadline độc lập, mock CPUS=1 | **PASS** | so từng event D/B, `END n`, SNAP counters với model contract |
| Oracle deadline độc lập, mock CPUS=4 | **PASS** | cùng fixture, khác số CPU |
| Oracle switch độc lập, mock CPUS=1/4 | **PASS** | 6 chiều switch, no-op/enum sai, `epoch`; ≥1 switch có Q>0 và I>0 |
| Regression SCAN tuần 3 (oracle L02) | **PASS** | không bị fixture I01 làm nhiễu |
| Regression FCFS tuần 2 + policy L02 | **PASS** | cùng log |
| Mutant `i01-m1-expired-latest` (sai thứ tự expiry) | **EXPECTED_FAIL** | oracle deadline bắt |
| Mutant `i01-m2-noop-epoch` (no-op tăng epoch) | **EXPECTED_FAIL** | oracle switch bắt |
| Mutant `i01-m3-keep-batch` (không reset batch) | **EXPECTED_FAIL** | oracle switch bắt (thứ tự POSITION vs FIFO) |
| Mutant `dl-m1-no-expired` (bỏ ưu tiên expired) | **EXPECTED_FAIL** | **bắt buộc theo card**, oracle độc lập bắt |
| Mutant `dl-m3-eagain-batch` (commit batch khi EAGAIN) | **EXPECTED_FAIL** | oracle deadline bắt |
| Mutant `sw-m2-reset-age` (reset tuổi khi switch) | **EXPECTED_FAIL** | **bắt buộc theo card**, oracle switch bắt |
| READ thật FCFS cơ bản CPUS=1 + `IO-SNAP` | **PASS** | `S=83,C=81,E=2,R=83,Q=I=D=X=0,F=16,free_desc=8`; 2 ERROR là cố ý của suite |
| Production restore, hook vắng | **PASS** | `production_hooks_absent=true` |
| `check_text.py` / `git diff --check` | **PASS** | rc 0 |

---

## 3. Bằng chứng cho card G01/I01/I02

| Card | Bằng chứng | Trạng thái |
| :--- | :--- | :---: |
| **W4-G01** contract + evidence index | [`interface.md`](interface.md), file này, [`measurement.md`](measurement.md); header `kernel/io_request.h` (D21–D24) | ✅ soạn trên `360b4df`; review Hoàng/Lợi **PENDING** |
| **W4-I01** oracle độc lập + snapshot + mutant | E6–E9; code `360b4df`; oracle `tests/cases/ioq_deadline.py`, `ioq_policy_switch.py`; mô hình `ioq_w4_model.py`; mutant `tests/mutants/i01-*.patch`; harness `scripts/check-week04-oracle-hieu.py` | ✅ PASS mock CPU1/4 + mutant EXPECTED_FAIL |
| **W4-I01** "snapshot/counters và timing" | [`measurement.md`](measurement.md) §2.1; E8 | ✅ có mẫu thật + giải thích giới hạn tick |
| **W4-I02** merge READ + owner/cancel design | [`merge-lifecycle-design.md`](merge-lifecycle-design.md) | ✅ thiết kế; review Hoàng/Lợi **PENDING**; code **không có** (đúng phạm vi) |

---

## 4. Những gì chưa có bằng chứng (NOT RUN) và người xử lý

| # | Hạng mục còn thiếu | Lý do | Người xử lý | Cách đóng |
| :---: | :--- | :--- | :---: | :--- |
| N1 | **SCAN READ thật** CPU1/4 có queue nhiều ứng viên + oracle order | Chưa chạy trên nhánh tích hợp; mock không thay được | **H01 (Hoàng)** | mở policy option trong `IO_HW_SELFTEST`, chạy FCFS/SCAN × CPU1/4 |
| N2 | **Deadline READ thật** CPU1/4 | Như N1; API switch đã có nhưng chưa dùng trong real harness | **H01/H02** | dùng `io_set_policy()` trong hw harness, ghi expiry/batch vào meta |
| N3 | **Stress switch 10 boot** (5 CPU1 + 5 CPU4, 4×120 READ, window 5, seed) | Lợi mới chạy smoke 1+1 boot; chưa đủ lượt | **H02 (Hoàng)** | mở rộng stress controller, phủ 6 chiều switch, ghi actual |
| N4 | **Máy thứ hai** cùng final revision, 3 policy × CPU1/4 | Chưa có revision cuối | **H02; Lợi/Hiếu chạy** | clone cùng SHA, ghi machine/OS/toolchain |
| N5 | **Final regression** 6 case production + FCFS 20 boot trên candidate SHA | Chưa đóng băng candidate | **G02 (Hoàng điều phối)** | `make test-week02`/`baseline` + 6 case, hooks vắng |
| N6 | **Owner/orphan/cancel implementation + test K1–K6** | Chỉ thiết kế (đúng phạm vi P2) | **Tuần 5+** | sau review cleanup/coherence |
| N7 | **Merge READ mức thiết bị** | Chỉ thiết kế (I02) | **Tuần 5+** | test merge/fan-out/checksum từng child |
| N8 | **Benchmark ≥ 5 lần/điểm, stress ≥ 30 phút** | Ngoài phạm vi tuần 4 | Tuần 5+ | workload đủ lớn để vượt độ phân giải tick |

Không dùng log tuần 3 (E1) để lấp N1–N5. Không tuyên bố milestone đạt khi phần
tương ứng còn NOT RUN.

---

## 5. Checklist metadata bắt buộc (D25) cho một lượt chạy

| Trường | E6 (I01) | E2 (L01/L02) | Ghi chú |
| :--- | :---: | :---: | :--- |
| Commit + dirty | ✅ `360b4df`, dirty rỗng | ✅ `5191ed8`, dirty (361–380) | E2 cần tái chạy trên candidate sạch ở G02 |
| xv6 pin | ✅ `f780d78…` | ✅ | |
| Máy/OS | ✅ WSL2 `DESKTOP-RL9K1ML` | ✅ WSL2 `haree`/`laptop-Loi` | ghi đúng hostname/máy |
| Compiler/QEMU/make | ✅ gcc 13.3.0, QEMU 8.2.2, make 4.3 | ✅ | |
| `TOOLPREFIX` | ✅ `riscv64-linux-gnu-` | ✅ | |
| Lệnh/cờ/CPU | ✅ `check-week04-oracle-hieu.py`, CPUS 1/4 | ✅ | |
| Seed/fixture/checksum | ➖ mock + fixture chuẩn I01; hw dùng fixture H02 | ✅ `0x26128003`, 32 block 1968..1999 | |
| Expiry/batch | ✅ 50/4 (D21) | ✅ 50/4 | |
| Số boot/READ/switch | ✅ 2 mock + 1 hw boot; hw 83 terminal | ✅ 2+20+2 boot | |
| Expected/actual | ✅ oracle so từng event + SNAP | ✅ oracle L01/L02 | |
| Timeout | ✅ harness `timeout 900` | ✅ | |
| Raw log | ✅ `policy-cpus*.log`, `hw-cpus1-snap.log` | ✅ | |
| Production restore | ✅ `production_hooks_absent=true` | ✅ | |
| Reviewer | ⏳ **PENDING** (Hoàng/Lợi) | ⏳ **PENDING** | chưa được ghi Done |

---

## 6. Cách đọc nhanh

1. Muốn biết **contract/quy tắc**: [`interface.md`](interface.md) D21–D27.
2. Muốn biết **số liệu snapshot/latency**: [`measurement.md`](measurement.md).
3. Muốn biết **kết quả tuần 4 đạt gì**: [`report-hieu.md`](report-hieu.md) §7.
4. Muốn **chạy lại**: [`report-hieu.md`](report-hieu.md) §9 (một lệnh) hoặc
   `scripts/check-week04-oracle-hieu.py`.
