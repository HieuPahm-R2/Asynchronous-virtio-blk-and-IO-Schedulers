# Candidate Hoàng: d39ea8c - nghiệm thu local ngày 16/11/2026

Code đã test: `d39ea8cf3500a0fdcf023efeab2c850dd2b767d6`, source sạch.
Bổ sung commit tài liệu/evidence sau đó không thay kernel/user/scripts/tests.

| Suite | Kết quả | Evidence |
| --- | --- | --- |
| READ thật + stress switch | 2 boot real, 20 ca/140 READ; 10 stress boot/4.800 READ; 2 fixture negative EXPECTED_FAIL; restore PASS | [summary](../../results/week04/hoang-20261116/acceptance-d39ea8c/real-and-switch/summary.md) |
| Oracle độc lập I01 | CPU1/4 PASS, 6 mutant EXPECTED_FAIL, real snapshot CPU1 PASS | [summary](../../results/week04/hoang-20261116/acceptance-d39ea8c/independent-oracle/summary.md) |
| FCFS regression | 20/20 real boot, 4/4 mock, negative EXPECTED_FAIL | [summary](../../results/week04/hoang-20261116/acceptance-d39ea8c/fcfs-regression/summary.md) |
| Production | 6/6 PASS: boot CPU1, shell CPU3, usertests -q CPU1/4, grind60s CPU1/4 | [summary](../../results/week04/hoang-20261116/acceptance-d39ea8c/production-baseline/summary.md) |

Host-only oracle controls: [oracle-controls.json](../../results/week04/hoang-20261116/acceptance-d39ea8c/oracle-controls.json).
Raw log, metadata, hash và build logs đi kèm từng thư mục. Không cộng log debug hoặc tuần 3 vào số final.

**Chưa đạt toàn bộ acceptance:** máy thứ hai cùng candidate NOT RUN; review chéo Lợi/Hiếu PENDING;
không push/PR/merge, không thay đổi Jira. Hai CPU config trên cùng host không được coi là hai máy.
Owner/cancel, device merge, user API tổng quát và stress30phút chưa được triển khai/nghiệm thu bởi phần này.

Xem [report-hoang.md](report-hoang.md), [PDF](report-hoang.pdf),
[runbook](hoang-runbook.md), [review](review-hoang.md).
