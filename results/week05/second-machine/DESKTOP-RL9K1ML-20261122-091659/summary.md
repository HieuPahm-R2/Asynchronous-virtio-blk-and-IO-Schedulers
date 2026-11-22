# W5-H01 — Candidate verification trên máy thứ hai

- Status: **PASS**
- Candidate SHA: `f5130bb9898c4154c3e761e2c85f3038f3a02a86` (week4/hieu-contract-oracle)
- Source sạch: start=True, end=True
- Operator: Loi (W5-H01; phien thuc thi hoan thien theo yeu cau)
- Máy: `DESKTOP-RL9K1ML` — Linux 5.15.167.4-microsoft-standard-WSL2
- Host khác host đã chạy (`nguyen-van-hoang-20233413`): True
- Toolchain: `riscv64-linux-gnu-`

## Môi trường

| Hạng mục | Giá trị |
| :--- | :--- |
| Hostname | `DESKTOP-RL9K1ML` |
| OS / kernel | Linux 5.15.167.4-microsoft-standard-WSL2 / 5.15.167.4-microsoft-standard-WSL2 |
| Python | Python 3.12.3 |
| Compiler | riscv64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 |
| QEMU | QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18) |
| Make | GNU Make 4.3 |
| xv6 pin | `f780d7850765d74cbdcd1fff4b822d8829f7c9bd 2026-10-15 build with -fno-delete-null-pointer-checks` |

## Kết quả suite

| Suite | Kết quả | PASS | EXPECTED_FAIL | FAIL | Log/meta |
| :--- | :---: | :---: | :---: | :---: | :--- |
| real-and-switch | **PASS** | 13 | 2 | 0 | `logs/real-and-switch.log`, `real-and-switch/summary.md` |
| independent-oracle | **PASS** | 3 | 6 | 0 | `logs/independent-oracle.log`, `independent-oracle/summary.md` |
| fcfs-regression | **PASS** | 24 | 1 | 0 | `logs/fcfs-regression.log`, `fcfs-regression/summary.md` |

- EXPECTED_FAIL tổng: **9** (không cộng vào PASS)

## Negative control (EXPECTED_FAIL riêng)

| Suite | Mutant | Kết quả |
| :--- | :--- | :---: |
| independent-oracle | i01-m1-expired-latest | EXPECTED_FAIL |
| independent-oracle | i01-m2-noop-epoch | EXPECTED_FAIL |
| independent-oracle | i01-m3-keep-batch | EXPECTED_FAIL |
| independent-oracle | dl-m1-no-expired | EXPECTED_FAIL |
| independent-oracle | dl-m3-eagain-batch | EXPECTED_FAIL |
| independent-oracle | sw-m2-reset-age | EXPECTED_FAIL |

## Repo checks
- check-text: rc=0
- git-diff-check: rc=0

## Lưu ý
- CPU1/4 trên cùng host không tính là hai máy; host này khác host đã chạy candidate.
- QEMU virtio-blk không chứng minh seek vật lý; 0 tick nghĩa là dưới 1 tick (≈100 ms), không phải 0 ms.
- Negative control EXPECTED_FAIL báo riêng, không cộng vào PASS.
