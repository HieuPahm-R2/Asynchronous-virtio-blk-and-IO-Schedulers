# Hiếu

Vai trò trong học phần (theo kế hoạch): **async API, buffer lifetime,
merging và counters kernel**; thêm phần **test harness, benchmark và báo cáo
phép đo**.

Tuần 1 mục tiêu không phải code kernel, mà là: chạy được trên máy mình, hiểu
đường I/O + ownership, có test plan, có bằng chứng.

> Xem [run-on-ubuntu.md](../run-on-ubuntu.md) nếu có lỗi.

## Bước 0 — Chuẩn bị (15 phút, làm trước mọi bước)

```bash
cd ~/ET4290
git pull                              # lấy bản mới nhất (đã sửa lỗi font + check-text)
git checkout -b week1/hieu            # nhánh làm việc riêng
make check-text                       # phải PASS
```

Đọc trước (đừng đọc hết mọi thứ, chỉ 4 file):

1. [`docs/plan/02_Checklist_tuan_1.pdf`](../plan/02_Checklist_tuan_1.pdf) — checklist bạn đang làm.
2. [`docs/architecture.md`](../architecture.md) — mục 1.1–1.5 (đường I/O stock, API sleep mới).
3. [`docs/week1.md`](../week1.md) — bảng ngày/giờ và checklist nghiệm thu.
4. [`docs/demo.md`](../demo.md) — mục 2 (check-in 10 phút) để biết cuối tuần demo gì.

---

## Bước 1 — Kickoff + ghi biên bản (1h, ngày 19/10)

**Mục tiêu (T1-01):** chốt phạm vi, owner/reviewer, câu hỏi GV; biên bản là bằng chứng.

1. Mở [`docs/week01/kickoff.md`](kickoff.md), điền:
   - thông tin buổi họp (thời gian/hình thức/thành viên),
   - **phạm vi tuần 1** (làm gì / chưa làm gì — dựa trên kế hoạch mục 1),
   - **bảng câu hỏi GV** (tag xv6, API async, SCAN vs LOOK, phạm vi merging,
     rubric, lịch nộp/demo) — chưa có trả lời thì ghi `PENDING`,
   - **URL công cụ** (repo/Jira/FigJam) — chưa có thì ghi `PENDING + deadline`,
   - **phân công tuần 1** (lấy từ checklist 02, mục ngày 19–25),
   - **quyết định sơ bộ**: dùng nhánh `week1/<tên>`, PR có reviewer, không sửa
     kernel tuần này, lệnh test chính thức là `make test`,
   - hành động sau họp (ai làm gì, hạn nào).

**Nghiệm thu:** kickoff.md không còn `PENDING` ở phần bắt buộc (câu hỏi GV được
phép PENDING nhưng phải có owner + hạn hỏi); có ít nhất 1 commit.

> Nếu nhóm chưa có Jira/FigJam: vẫn ghi PENDING + deadline 20/10 và báo GV xin
> chấp thuận công cụ (checklist T1-03/T1-04). Giảng viên phải đọc được trước
> tuần học phần 2.

---

## Bước 2 — Cài & kiểm tra môi trường trên laptop

**Mục tiêu:** máy bạn build/boot được; điền version log 3 máy.

```bash
sudo bash scripts/setup-env.sh    # 1 lần/máy; script tự chọn gói QEMU cho 26.04
make env-check                    # PHẢI ra "MÔI TRƯỜNG SẴN SÀNG", không [FAIL]
make test-fast                    # 2 case PASS (~8 giây)
make demo DEMO_ARGS=--no-qemu     # xem nhanh 6 phần demo (không cần QEMU)
```

Nếu `make env-check` FAIL: copy nguyên output gửi nhóm; các lỗi hay gặp ở bảng
[run-on-ubuntu.md](../run-on-ubuntu.md) mục 9. Riêng 26.04 chú ý tên gói QEMU:
dấu hiệu `qemu-system-riscv64: not found` dù apt báo `qemu-system-misc is
already the newest version` → cài thêm:

```bash
sudo apt-get install -y qemu-system-riscv   # gói riêng của 26.04+
make env-check                              # phải PASS
```

(Trên 26.04 `qemu-system-misc` không còn chứa binary RISC-V; script
`setup-env.sh` đã được sửa để tự thử cả hai gói sau khi `git pull`.)

Sau đó mở [`docs/week01/environment.md`](environment.md), điền **dòng máy của
bạn**: OS, git hash (`git rev-parse HEAD`), xv6 pin (`cat .xv6-commit`), gcc,
QEMU, gdb, python (copy từ output `make env-check`), ngày, `env-check = PASS`.

**Nghiệm thu:** bảng environment.md có dòng `laptop-Hiếu` đầy đủ; `make env-check` PASS.

---

## Bước 3 — DrawIO + URL (45 phút, ngày 20/10 chiều)

**Mục tiêu:** có 3 trang sơ đồ, giảng viên đọc được.

vẽ theo [`docs/architecture.md`](../architecture.md):

1. **I/O path stock**: `bread/bget → bwrite (chỉ log) → virtio_disk_rw → virtqueue
   → interrupt (trap.c devintr) → virtio_disk_intr → wakeup` + ghi chú NUM=8,
   3 descriptor/request, tối đa 2 chain đồng thời.
2. **Request state machine**: `FREE → ALLOCATED → QUEUED → INFLIGHT → DONE/ERROR → FREE`
   (kèm nhánh merge read, trạng thái con của merged request).
3. **Sequence async đề xuất**: caller → `aio_read_submit` → pending queue →
   scheduler → device → interrupt → completion → `aio_poll/aio_wait` → `aio_release`.

---

## Bước 4 — Đọc code + ghi chú buffer/async

**Mục tiêu (T1-08):** bạn là người nắm buffer lifetime/async API của nhóm.

### 4a. Đọc (khoảng 1h30)

| File | Đọc gì | Câu hỏi phải trả lời được |
| --- | --- | --- |
| `kernel/buf.h`, `kernel/bio.c` | `struct buf`, `bget/bread/bwrite/brelse`, `bpin/bunpin` | Ai giữ `b->lock` (sleeplock) khi nào? `refcnt` bảo vệ điều gì? Vì sao `bwrite` chỉ được log gọi? |
| `kernel/log.c` | `begin_op/end_op`, `log_write`, `commit`, `write_log`, `install_trans` | Write đi qua log thế nào? Vì sao giai đoạn đầu **không reorder/merge write**? |
| `kernel/fs.c` | `readi/writei/bmap` | Buffer nào được giữ qua bao lâu? Copy ra user xảy ra ở đâu? |
| `kernel/virtio_disk.c` | `virtio_disk_rw`, `virtio_disk_intr` | `b->disk` nghĩa là gì? `sleep_prepare/sleep` chống mất wakeup thế nào? Buffer được trả lại lúc nào? |
| `kernel/proc.c` | `sleep_prepare`, `sleep`, `wakeup` | Vì sao phải gọi `sleep_prepare()` **trước** khi `release(lock)`? |
| `kernel/defs.h` + `kernel/param.h` | API, `NBUF`, `MAXOPBLOCKS` | Giới hạn nào ảnh hưởng thiết kế pool/merged request? |

### 4b. Ghi vào [`docs/week01/decisions.md`](decisions.md) (khoảng 1h30)

Điền 4 mục (template đã có sẵn câu hỏi gợi ý):

1. **Buffer ownership hiện tại** — bảng: tình huống / ai giữ / cần làm gì.
2. **Write path & logging** — 4 bước `log_write → commit → write_log → bwrite`,
   kết luận: write giữ đồng bộ + fence ở giai đoạn đầu.
3. **Completion-before-wait** — giải thích bằng `b->disk` + `sleep_prepare/sleep/wakeup`;
   quy tắc không release sleeplock trong IRQ.
4. **API async đề xuất** — `aio_read_submit / aio_poll / aio_wait / aio_release`:
   semantics, buffer lifetime (refcount/pin), lỗi khi queue/pool đầy, ai copy dữ
   liệu ra user space, ràng buộc DMA (không giữ user pointer sau khi process exit).

**Nghiệm thu:** decisions.md có đủ 4 mục, mỗi mục có kết luận + câu hỏi mở;
Hoàng review và ghi nhận xét (1 dòng + approve).

---

## Bước 5 — Test matrix & protocol (1h, ngày 23/10)

**Mục tiêu (T1-10):** có kế hoạch ≥ 30 case, ma trận CPUS, benchmark, stress.

1. Đọc lại [`docs/testing.md`](../testing.md) (khung đã có) + [`docs/baseline.md`](../baseline.md) (protocol đã chạy).
2. Điền [`docs/week01/test-plan.md`](test-plan.md):
   - bảng phân tầng T0–T6 + số case dự kiến (tổng ≥ 30),
   - danh sách case (ít nhất các case R01–R09 — ghi rõ oracle từng case),
   - ma trận: CPUS=1/4, lặp ≥ 10, policy FCFS/SCAN/deadline, merge off/on,
   - benchmark: ≥ 5 lần/điểm, workload, đơn vị, format lưu (link `results/README.md`),
   - stress: 30 phút × CPUS=1/4, tiêu chí dừng/fail,
   - mục **NOT RUN**: những gì chưa đo.
3. Không điền số liệu giả; phần chưa có để `NOT RUN`.

**Nghiệm thu:** test-plan.md có bảng ≥ 30 dòng (có thể nhóm theo tầng), mỗi case
có tag + cách kiểm; mục benchmark/stress khớp với `docs/testing.md`.

---

## Bước 6 — Baseline trên máy bạn + protocol đo

**Mục tiêu** máy thứ hai tái lập được baseline.

```bash
make baseline        # ~10–25 phút trên laptop; chạy ở terminal riêng
```

Khi xong:

1. Kiểm tra `results/baseline/<timestamp>/`: có `meta.json` (commit, toolchain,
   `dirty: false`) + `summary.md` (6 case PASS) + `logs/`.
2. Ghi kết quả vào [`docs/week01/environment.md`](environment.md) cột baseline
   và vào báo cáo tuần (không ghi đè baseline của máy dev).
3. **Tái lập từ clone mới** (bằng chứng "máy thứ hai build được"):
   ```bash
   git clone . /tmp/et4290-repro && cd /tmp/et4290-repro
   make -j"$(nproc)" kernel/kernel fs.img
   python3 tests/runner.py --case boot-smoke --results-dir results/local/repro
   # phải PASS; so commit giống repo chính; sau đó xoá /tmp/et4290-repro
   ```
4. Cập nhật mục "Benchmark protocol" trong test-plan.md: máy, commit, CPUS,
   lệnh, số lần lặp, format dữ liệu thô (dùng đúng `meta.json` hiện có).

**Nghiệm thu:** baseline máy bạn 6/6 PASS + clone mới build/boot PASS; ghi vào
environment.md + báo cáo tuần.
