# Kết quả test ET4290

- Thời điểm: 2026-10-19T22:29:45+07:00
- Project commit: `9f5b7847be53`
- xv6 pin: `f780d7850765`
- Môi trường: Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.39
- Số CPU khả dụng: 6
- Kết quả: **6 PASS / 0 FAIL**

| Case | CPUS | Trạng thái | Thời gian (s) | Ghi chú |
| --- | ---: | --- | ---: | --- |
| `boot-smoke` | 1 | PASS | 3.50 | boot xv6 + shell nhận lệnh |
| `shell-fs-cpus3` | 3 | PASS | 4.27 | đọc/ghi + shell trên fs.img stock |
| `usertests-quick-cpus1` | 1 | PASS | 536.77 | stock usertests -q (CPUS=1) |
| `usertests-quick-cpus4` | 4 | PASS | 492.98 | stock usertests -q (CPUS=4) |
| `grind-smoke-cpus1` | 1 | PASS | 63.00 | stock grind 60s, fail nếu panic (không phải PASS tuyệt đối) |
| `grind-smoke-cpus4` | 4 | PASS | 63.27 | stock grind 60s, fail nếu panic (không phải PASS tuyệt đối) |
