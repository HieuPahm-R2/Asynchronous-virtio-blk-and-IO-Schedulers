# ET4290 — Asynchronous virtio-blk và I/O schedulers trên xv6-riscv

Đề tài **26128** (nhóm 3 người): xây dựng đường I/O có hàng đợi cho xv6-riscv —
nhiều request outstanding, ba chính sách lập lịch **FCFS / SCAN / deadline**,
**gộp request** và **API đọc bất đồng bộ** — kèm test tự động, benchmark và
demo chuyển policy khi hệ thống đang chạy.

Repo này là **base dự án**: source xv6-riscv đã pin, môi trường phát triển tái
lập được, harness test/baseline và khung tài liệu. Kernel **chưa** được sửa
so với stock — đó là việc của tuần 2 trở đi.

> Tài liệu kế hoạch gốc: [`docs/plan/01_Bao_cao_ke_hoach_26128.pdf`](docs/plan/01_Bao_cao_ke_hoach_26128.pdf)

## Trạng thái hiện tại

| Hạng mục | Trạng thái |
| --- | --- |
| Source xv6-riscv pin theo commit | ✅ `.xv6-commit` (pin tạm, chờ tag giảng viên) |
| Môi trường WSL2 Ubuntu 24.04 + toolchain RISC-V + QEMU | ✅ đã cài, kiểm tra bằng `make env-check` |
| Build một lệnh (`make`) / boot (`make qemu`) | ✅ |
| Test harness một lệnh (`make test`), PASS/FAIL từng ca | ✅ khung + case stock |
| Baseline stock (`usertests -q`, `grind`) lưu bằng chứng | ✅ [6/6 PASS](results/baseline/2026-10-19_222935/summary.md) — xem [`docs/baseline.md`](docs/baseline.md) |
| Build lại được từ clone mới | ✅ đã kiểm tra (clone → `make` → boot smoke PASS) |
| Sơ đồ kiến trúc I/O hiện tại + lifecycle request đề xuất | ✅ [`docs/architecture.md`](docs/architecture.md) |
| Kịch bản demo cho GV (`make demo` + 20 phút final) | ✅ [`docs/demo.md`](docs/demo.md) |
| Tag/commit xv6 chính thức của giảng viên | ⏳ **pending** — đổi bằng `scripts/update-xv6.sh` |

## Bắt đầu nhanh

### Windows (khuyến nghị: WSL2 Ubuntu 24.04)

```powershell
# 1) Cài WSL2 (nếu chưa có) — PowerShell quản trị
wsl --install --no-distribution

# 2) Cài môi trường dự án (tải Ubuntu 24.04 rootfs, import, apt toolchain, check)
powershell -ExecutionPolicy Bypass -File scripts\wsl\import-ubuntu.ps1
```

Sau đó mở terminal WSL và làm việc trong repo:

```bash
wsl -d Ubuntu-24.04
cd /mnt/e/ET4290          # đường dẫn repo của bạn
make env-check            # kiểm tra toolchain + build + boot (~10 giây)
make qemu                 # boot xv6 (Ctrl-A rồi X để thoát)
make test-fast            # smoke test nhanh (~8 giây)
make test                 # suite đầy đủ hơn (~18 phút trên QEMU TCG)
```

### Linux / VM (Ubuntu 24.04 hoặc 26.04 LTS)

```bash
sudo bash scripts/setup-env.sh   # cài gcc/binutils RISC-V, QEMU, gdb-multiarch, Python
bash scripts/check-env.sh        # build + boot thử
make qemu CPUS=4
```

Ubuntu 26.04 dùng được bình thường (QEMU/GCC mới hơn, upstream xv6 cũng CI trên
26.04); chỉ cần ghi lại version vào báo cáo và không trộn số liệu giữa các máy —
chi tiết trong [`docs/run-on-ubuntu.md`](docs/run-on-ubuntu.md).

Chi tiết môi trường, version và cách xử lý sự cố:
[`docs/environment.md`](docs/environment.md) (Windows/WSL2) ·
[`docs/run-on-ubuntu.md`](docs/run-on-ubuntu.md) (laptop Ubuntu: clone → cài → chạy → baseline).

## Cấu trúc repo

```
.
├── kernel/ user/ mkfs/      # xv6-riscv upstream (pin tại .xv6-commit)
├── Makefile                 # Makefile xv6 + include mk/project.mk
├── mk/project.mk            # target của dự án: test, baseline, env-check
├── tests/
│   ├── qemu.py              # lớp điều khiển QEMU: send/expect/kill process group
│   ├── runner.py            # chạy case, in PASS/FAIL, ghi results
│   └── cases/               # khai báo test case (thêm file .py mới là xong)
├── scripts/
│   ├── setup-env.sh         # cài toolchain (Ubuntu/Debian, idempotent)
│   ├── check-env.sh         # kiểm tra môi trường + build + boot
│   ├── baseline.sh          # đo baseline stock, lưu vào results/
│   ├── demo.sh              # demo 6 phần cho GV / tự kiểm tra máy mới
│   ├── run-qemu.sh          # boot QEMU có CPUS/log/timeout
│   ├── update-xv6.sh        # đổi sang tag/commit xv6 của giảng viên
│   └── wsl/                 # helper cài WSL2 Ubuntu trên Windows
├── docs/                    # kiến trúc, môi trường, test, baseline, plan gốc
├── results/                 # bằng chứng đo (baseline..., local/ bị gitignore)
├── .xv6-commit              # commit xv6 đang dùng
├── .xv6-files               # manifest file thuộc upstream (cho update-xv6.sh)
└── .github/workflows/ci.yml # CI: build + test-case nhanh
```

Quy ước `results/`: `results/baseline/<timestamp>/` được commit (bằng chứng
stock baseline), `results/local/` bị gitignore (chạy thử hằng ngày).
Xem [`results/README.md`](results/README.md).

## Pin xv6-riscv

- Đang dùng: **`f780d785` — "build with -fno-delete-null-pointer-checks"**
  (nhánh `riscv`, 2026-10-15), ghi tại `.xv6-commit`.
- Pin này là **tạm thời** cho tới khi giảng viên chốt tag chính thức
  (mục "Chốt tag/commit xv6 gốc" trong kế hoạch tuần 1).
- Đổi pin: `bash scripts/update-xv6.sh <tag|commit>` — script giữ nguyên
  toàn bộ file dự án và tự nối lại `mk/project.mk`.

Lưu ý: commit hiện tại dùng API sleep mới của xv6 (`sleep_prepare()` +
`sleep()` + `io_fence()`), khác bản cũ `sleep(chan, lock)` trong sách xv6.
Xem ghi chú trong [`docs/architecture.md`](docs/architecture.md).

## Make targets

| Lệnh | Việc |
| --- | --- |
| `make qemu` | boot xv6 (`CPUS=1..4`, mặc định 3) |
| `make qemu-gdb` | boot chờ `gdb-multiarch` |
| `make env-check` | kiểm tra toolchain + build + boot smoke |
| `make demo` | demo 6 phần (~25 giây): môi trường/build/boot/test/baseline — dùng cho GV |
| `make test` | suite mặc định (trừ tag `slow`/`stress`) |
| `make test-fast` | chỉ smoke test boot/shell (~8 giây) |
| `make test-slow` | usertests đầy đủ (rất lâu, chạy có chủ đích) |
| `make list-tests` | liệt kê test case |
| `make baseline` | build sạch + đo baseline stock → `results/baseline/<ts>/` |
| `make fmt` | clang-format kernel/user (cần clang-format ≥ 19) |
| `make check-text` | kiểm tra encoding tài liệu/script (UTF-8, mojibake, CRLF) |

Thời gian tham khảo trên máy dev WSL2 (QEMU TCG): `make test-fast` ~8 giây;
`make test` ~18 phút (chủ yếu là `usertests -q` trên CPUS=1/4);
`make baseline` ~19,4 phút. Dùng `make test-fast` khi code hằng ngày và
`make test` trước khi commit lớn/PR. Chi tiết: [`docs/testing.md`](docs/testing.md).

## Demo cho giảng viên

- Chạy `make demo` — 6 phần: môi trường & pin → build một lệnh → boot xv6 →
  test PASS/FAIL từng case → baseline đã đo → hạ tầng tuần 2 (`make demo DEMO_ARGS=--no-qemu`
  nếu không muốn chạy QEMU).
- Kịch bản demo check-in tuần 1 (10 phút) và **final demo 20 phút** theo từng
  mục 0–2–4–3–3–4 phút, kèm output mẫu và checklist chuẩn bị:
  [`docs/demo.md`](docs/demo.md).

## Viết thêm test case

Thêm một entry vào `tests/cases/*.py` (hoặc file mới):

```python
CASES = [{
    "name": "my-test",
    "cpus": 1,
    "tags": ["scheduler"],
    "timeout": 120,
    "steps": [
        {"send": "myprog arg", "expect": [r"^DISPATCH 0 1 2$"]},
    ],
    "reject": [r"FAILED", r"^panic:"],
}]
```

`make list-tests` để xem; `python3 tests/runner.py --case my-test --verbose`.
Chi tiết oracle/ma trận test: [`docs/testing.md`](docs/testing.md).

## Việc cần chốt với giảng viên (từ kế hoạch)

- [ ] Tag/commit xv6 chính thức (đang dùng pin tạm ở trên)
- [ ] Quy đổi tuần học phần ↔ tuần làm việc, ngày/giờ nộp tuần 10, lịch demo
- [ ] API đọc bất đồng bộ: syscall user-space hay API kernel + chương trình minh hoạ?
- [ ] Định nghĩa SCAN giảng viên mong đợi (SCAN vs LOOK), phạm vi merging được chấp nhận
- [ ] Trọng số rubric (Functionality/Testing/Measurement) — không tự suy ra
- [ ] Jira/Trello + FigJam URL và quyền đọc của giảng viên

## Nhóm

| Thành viên | MSSV | Module kernel chính (đề xuất) |
| --- | --- | --- |
| Nguyễn Văn Hoàng | 20233413 | virtio submit/complete, descriptor lifecycle, error path |
| Phạm Qúy Lợi | 20233501 | request queue, FCFS/SCAN/deadline, chuyển policy |
| Phạm Trung Hiếu | 20233402 | async API, buffer lifetime, merging, counters |

Repo cần **private** và chia sẻ với giảng viên; giữ `main` luôn build được.
