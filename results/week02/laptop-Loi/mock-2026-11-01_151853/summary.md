# Kết quả test ET4290

- Thời điểm: 2026-11-01T15:18:53+07:00
- Project commit: `657e1b50a92e`
- xv6 pin: `f780d7850765`
- Môi trường: Linux-6.18.54.1-microsoft-standard-WSL2-x86_64-with-glibc2.39
- Số CPU khả dụng: 16
- Kết quả: **1 PASS / 0 FAIL**

| Case | CPUS | Trạng thái | Thời gian (s) | Ghi chú |
| --- | ---: | --- | ---: | --- |
| `ioq-fcfs-mock` | 1 | PASS | 13.49 | MOCK 2 slot: FCFS theo enqueue_seq, EAGAIN giữ queue, tự dispatch sau complete |
