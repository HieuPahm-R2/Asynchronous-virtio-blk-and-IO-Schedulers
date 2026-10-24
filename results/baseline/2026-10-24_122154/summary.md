# Kết quả test ET4290

- Thời điểm: 2026-10-24T12:22:01+07:00
- Project commit: `50e296a39c2a`
- xv6 pin: `f780d7850765`
- Môi trường: Linux-6.18.54.1-microsoft-standard-WSL2-x86_64-with-glibc2.39
- Số CPU khả dụng: 16
- Kết quả: **6 PASS / 0 FAIL**

| Case | CPUS | Trạng thái | Thời gian (s) | Ghi chú |
| --- | ---: | --- | ---: | --- |
| `boot-smoke` | 1 | PASS | 5.66 | boot xv6 + shell nhận lệnh |
| `shell-fs-cpus3` | 3 | PASS | 4.33 | đọc/ghi + shell trên fs.img stock |
| `usertests-quick-cpus1` | 1 | PASS | 139.81 | stock usertests -q (CPUS=1) |
| `usertests-quick-cpus4` | 4 | PASS | 131.25 | stock usertests -q (CPUS=4) |
| `grind-smoke-cpus1` | 1 | PASS | 61.18 | stock grind 60s, fail nếu panic (không phải PASS tuyệt đối) |
| `grind-smoke-cpus4` | 4 | PASS | 61.83 | stock grind 60s, fail nếu panic (không phải PASS tuyệt đối) |
