# Chạy dự án trên laptop Ubuntu (clone về máy mới)

Tài liệu này là runbook cho **máy Ubuntu thật** (laptop Linux). Nếu dùng Windows
thì xem [environment.md](environment.md) (WSL2 Ubuntu). Toàn bộ lệnh dưới đây
chạy trong terminal Ubuntu, không cần mạng sau bước cài toolchain.

## 0. Điều kiện cần

| Hạng mục | Yêu cầu | Ghi chú |
| --- | --- | --- |
| OS | **Ubuntu 24.04 LTS** (môi trường chuẩn của nhóm) hoặc **26.04 LTS** | 22.04 có QEMU 6.2 < 7.2 → Makefile báo lỗi |
| CPU/RAM | 2 CPU / 2 GB trở lên | `CPUS=4` cần ≥ 4 CPU; QEMU chỉ cấp `-m 128M` nên RAM không cần nhiều |
| Đĩa | ~2 GB trống | toolchain ~1 GB + source/build |
| Quyền | `sudo` (một lần để cài) | build/test không cần root |
| Mạng | lần đầu cài apt + clone repo | sau đó chạy offline được |
| Truy cập repo | repo **private** → cần PAT/SSH key GitHub | dùng `gh auth login` hoặc SSH key |

> Repo private theo yêu cầu học phần; giảng viên phải được cấp quyền đọc.

### Ubuntu 26.04 có sao không?

**Không sao** — thậm chí mượt hơn:

- QEMU trên 26.04 mới hơn 24.04 (chắc chắn ≥ 7.2), GCC RISC-V mới hơn.
- Chính upstream xv6-riscv chạy CI trên `ubuntu-26.04` (xem `test.yml` của
  <https://github.com/mit-pdos/xv6-riscv>), nên build/boot xv6 được kiểm chứng
  sẵn trên nền này.
- `clang-format` trên 26.04 nhiều khả năng ≥ 19 → `make fmt` sẽ chạy được
  (trên 24.04 chỉ có 18 nên `make fmt` lỗi config của upstream).

Cần chú ý khi cả nhóm dùng nhiều version khác nhau:

1. **Chạy `make env-check` và lưu output** (git hash, gcc, QEMU, OS) vào báo
   cáo tuần — spec yêu cầu cả ba ghi lại version.
2. **Không trộn số liệu baseline/benchmark giữa 24.04 và 26.04**; mỗi máy có
   baseline riêng, chỉ so sánh giữa các lần đo cùng máy/cùng command line.
3. **Không sửa Makefile/source để "chạy được trên máy tôi"** — nếu GCC mới hơn
   làm `-Werror` nổi cảnh báo, gửi log lại để cả nhóm xử lý chung bằng PR.
4. CI của repo chạy `ubuntu-24.04`; nếu CI xanh mà máy bạn lỗi (hoặc ngược lại),
   ghi rõ khác biệt để cùng xử lý.
5. **Tên gói QEMU có thể khác**: 24.04 dùng `qemu-system-misc`, một số bản mới
   (26.04+) tách riêng `qemu-system-riscv`. `scripts/setup-env.sh` đã thử lần
   lượt cả hai tên gói; nếu cả hai đều lỗi, gửi output apt lại để cập nhật script.

## 1. Clone source (đúng commit)

```bash
git clone https://github.com/HieuPahm-R2/Asynchronous-virtio-blk-and-IO-Schedulers.git ~/ET4290
cd ~/ET4290

git log --oneline -2          # phải thấy commit base/baseline của nhóm
cat .xv6-commit               # commit xv6 đang pin
git rev-parse HEAD            # ghi hash này vào báo cáo tuần
```

Nên clone vào `~/ET4290` (đường dẫn **không có dấu cách**).

## 2. Cài toolchain (một lần cho mỗi máy)

```bash
sudo bash scripts/setup-env.sh
# hoặc tối thiểu: sudo bash scripts/setup-env.sh --minimal
```

Script cài: `build-essential`, `gcc-riscv64-linux-gnu`, `binutils-riscv64-linux-gnu`,
`qemu-system-misc`, `gdb-multiarch`, `bc`, `perl`, `python3`, `clang-format`…
(idempotent — chạy lại vô hại; tự thử IPv4 nếu apt lỗi mạng).

> Script được kiểm thử trên Ubuntu 24.04. Trên 26.04, tên gói dự kiến không đổi;
> nếu apt báo thiếu gói nào, gửi log lại để cập nhật script.

## 3. Kiểm tra môi trường — bước quan trọng nhất

```bash
make env-check
```

Kết quả mẫu (máy dev WSL2 Ubuntu 24.04 — số version trên 26.04 sẽ mới hơn):

```text
== Hệ điều hành ==
  distro: Ubuntu 24.04 LTS
  kernel: 5.15.167.4-microsoft-standard-WSL2
  môi trường: WSL2
  CPU: 6  |  RAM: 7.7Gi

== Pin xv6-riscv ==
  f780d7850765d74cbdcd1fff4b822d8829f7c9bd 2026-10-15 build with -fno-delete-null-pointer-checks
  [ OK ] đã ghi pin xv6 (.xv6-commit)

== Toolchain ==
  [ OK ] make: GNU Make 4.3
  [ OK ] git: git version 2.43.0
  [ OK ] python3: Python 3.12.3
  [ OK ] bc: bc 1.07.1
  [ OK ] perl: v5.38.2
  [ OK ] RISC-V gcc: riscv64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
  [ OK ] QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18)
  [ OK ] QEMU >= 7.2
  [ OK ] gdb-multiarch (debug kernel)
  [ OK ] clang-format (Ubuntu clang-format version 18.1.3)

== Build thử (make -j) ==
  [ OK ] build kernel/kernel + fs.img thành công (272K kernel)

== Boot smoke (QEMU, CPUS=1) ==
  --- [1/1] boot-smoke (CPUS=1) ... PASS (3.6s)
  [ OK ] QEMU boot xv6 và shell trả lời

== MÔI TRƯỜNG SẴN SÀNG (cảnh báo: 0) ==
```

Điều kiện đạt: dòng cuối `MÔI TRƯỜNG SẴN SÀNG` và **không có `[FAIL]`**.
Nếu có `[FAIL]` → xem bảng sự cố ở mục 9.

## 4. Boot thử xv6

```bash
make qemu             # CPUS=3 mặc định
make qemu CPUS=1      # bắt buộc thử cả 1 và 4 theo spec
make qemu CPUS=4
```

Kết quả mẫu trên serial console (bên trong QEMU):

```text
xv6 kernel is booting

init: starting sh
$ echo BOOT_OK
BOOT_OK
$
```

Thoát QEMU: `Ctrl-A` rồi `X`. (Hoặc `bash scripts/run-qemu.sh --timeout 15`
để tự kill sau 15 giây, dùng cho CI/ghi log.)

## 5. Test harness — PASS/FAIL từng case

```bash
make test-fast        # 2 case, ~8 giây
make list-tests       # xem toàn bộ case sẽ chạy
make test             # suite mặc định, ~10–20 phút trên QEMU TCG
```

Kết quả mẫu:

```text
== ET4290 test runner — 2 case ==
   kết quả: /home/<user>/ET4290/results/local/tests-2026-10-21_214921
--- [1/2] boot-smoke (CPUS=1) ... PASS (3.1s)
--- [2/2] shell-fs-cpus3 (CPUS=3) ... PASS (4.1s)

== Kết quả: 2 PASS / 0 FAIL ==
```

Kết quả nằm trong `results/local/<timestamp>/` (`summary.md`, `meta.json`,
`logs/<case>.log`) — **không** commit (đã gitignore).

## 6. Baseline riêng cho máy này (khuyến nghị)

```bash
make baseline         # build sạch + usertests -q CPUS=1/4 + grind 60s ×2
```

Kết quả vào `results/baseline/<timestamp>/`; mất **10–25 phút tùy máy**.
Số liệu **khác máy dev là bình thường** — chỉ so sánh giữa các lần đo cùng máy,
cùng QEMU command line. Giữ lần chạy mới, không ghi đè lần cũ.

> Khi baseline xong: ghi hash commit + version toolchain (trong `meta.json`) vào
> báo cáo tuần để cả nhóm đối chiếu.

## 7. Làm việc hằng ngày

```bash
git pull                          # lấy code mới của nhóm
make env-check                    # nếu vừa pull/đổi tag xv6
make qemu CPUS=4                  # phát triển
make test-fast                    # sau mỗi thay đổi nhỏ (~8s)
make test                         # trước khi commit lớn/PR (~10–20 phút)
make baseline                     # khi cần số liệu so sánh
```

## 8. Quan tâm những gì (quan trọng nhất)

1. **Đúng commit** — ghi `git rev-parse HEAD` + nội dung `.xv6-commit`. Không so
   số liệu giữa hai máy khác commit/toolchain; đó là lỗi hay bị bắt trong báo cáo.
2. **QEMU ≥ 7.2** — Makefile chặn nếu thấp hơn. Ubuntu 22.04 mặc định 6.2 → dùng
   24.04 hoặc 26.04.
3. **Cùng toolchain** — `make env-check` in ra version; chụp lại vào báo cáo tuần
   (T1-05 yêu cầu cả ba lưu git hash, compiler, QEMU, OS).
4. **TCG vs KVM** — laptop Ubuntu có thể có `/dev/kvm`; hiện dùng TCG (như Makefile)
   nên số liệu tuyệt đối phụ thuộc máy. Muốn nhanh hơn có thể tự thêm `-accel kvm`
   khi chạy QEMU thủ công, nhưng **không** trộn cấu hình khi so sánh.
5. **Không commit build artifacts** — `fs.img`, `kernel/kernel`, `*.o`… đã gitignore.
6. **Repo private** — không đưa token/PAT vào log/README; dùng credential helper.
7. **Không sửa để "chạy được trên máy tôi"** — nếu build fail, sửa môi trường
   (cài package/đổi QEMU), không sửa Makefile/source để lách; mọi thay đổi phải qua PR.
8. **Thời gian** — QEMU TCG chậm; đừng bật `make test` rồi đi làm việc khác rồi
   tưởng treo. `usertests -q` ~8–10 phút/cấu hình là bình thường.

## 9. Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Xử lý |
| --- | --- | --- |
| `Couldn't find a riscv64 version of GCC/binutils` | thiếu toolchain | `sudo bash scripts/setup-env.sh` |
| `Need qemu version >= 7.2` | QEMU cũ (Ubuntu 22.04) | nâng lên 24.04/26.04 hoặc cài QEMU mới hơn |
| `make: bc: No such file or directory` | thiếu `bc` | `sudo apt install bc` |
| `Permission denied` khi clone | chưa đăng nhập GitHub cho repo private | `gh auth login` hoặc SSH key |
| `apt-get update` lỗi mạng/IPv6 | mạng chỉ IPv6 lỗi | script đã tự thử IPv4; hoặc `-o Acquire::ForceIPv4=true` |
| QEMU đứng ở "xv6 kernel is booting" | hiếm: `fs.img` hỏng/CPU ít | `make clean && make`, thử `CPUS=1` |
| `make fmt` lỗi `invalid boolean` | `.clang-format` upstream cần clang-format ≥ 19 | không bắt buộc; trên 26.04 nhiều khả năng đã chạy được |
| Build chậm | QEMU TCG + ít CPU | bình thường; build kernel chỉ ~2–5 giây, chậm là phần QEMU/USERTESTS |
| `results/local` không thấy trong git status | đúng thiết kế | log chạy thử bị gitignore; chỉ `results/baseline` được commit |
| File tài liệu hiển thị lỗi font | file bị lưu sai encoding (mojibake) | chạy `make check-text` để kiểm tra; sửa file bằng UTF-8 |

## 10. Chạy demo để tự kiểm tra / demo GV

```bash
make demo                                 # 6 phần: môi trường → build → boot → test → baseline → hạ tầng
make demo DEMO_ARGS=--no-qemu             # chỉ in thông tin, không chạy QEMU
```

Kịch bản demo đầy đủ cho giảng viên: [demo.md](demo.md).
