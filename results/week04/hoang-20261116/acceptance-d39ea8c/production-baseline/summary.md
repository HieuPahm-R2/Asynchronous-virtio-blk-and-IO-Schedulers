# Kết quả test ET4290

- Thời điểm: 2026-11-16T22:58:43+07:00
- Project commit: `d39ea8cf3500`
- xv6 pin: `f780d7850765`
- Môi trường: Linux-7.2.6-x86_64-with-glibc2.39
- Số CPU khả dụng: 12
- Kết quả: **6 PASS / 0 FAIL**

| Case | CPUS | Trạng thái | Thời gian (s) | Ghi chú |
| --- | ---: | --- | ---: | --- |
| `boot-smoke` | 1 | PASS | 0.86 | boot xv6 + shell nhận lệnh |
| `shell-fs-cpus3` | 3 | PASS | 1.26 | đọc/ghi + shell trên fs.img stock |
| `usertests-quick-cpus1` | 1 | PASS | 84.00 | stock usertests -q (CPUS=1) |
| `usertests-quick-cpus4` | 4 | PASS | 83.21 | stock usertests -q (CPUS=4) |
| `grind-smoke-cpus1` | 1 | PASS | 60.77 | stock grind 60s, fail nếu panic (không phải PASS tuyệt đối) |
| `grind-smoke-cpus4` | 4 | PASS | 61.00 | stock grind 60s, fail nếu panic (không phải PASS tuyệt đối) |
