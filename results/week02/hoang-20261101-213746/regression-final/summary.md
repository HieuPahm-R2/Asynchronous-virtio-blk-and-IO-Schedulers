# Kết quả test ET4290

- Thời điểm: 2026-11-01T21:43:17+07:00
- Project commit: `b6b44bb6da73` (dirty)
- xv6 pin: `f780d7850765`
- Môi trường: Linux-7.2.6-x86_64-with-glibc2.39
- Số CPU khả dụng: 12
- Kết quả: **6 PASS / 0 FAIL**

| Case | CPUS | Trạng thái | Thời gian (s) | Ghi chú |
| --- | ---: | --- | ---: | --- |
| `boot-smoke` | 1 | PASS | 1.45 | boot xv6 + shell nhận lệnh |
| `shell-fs-cpus3` | 3 | PASS | 1.45 | đọc/ghi + shell trên fs.img stock |
| `usertests-quick-cpus1` | 1 | PASS | 85.60 | stock usertests -q (CPUS=1) |
| `usertests-quick-cpus4` | 4 | PASS | 75.19 | stock usertests -q (CPUS=4) |
| `grind-smoke-cpus1` | 1 | PASS | 60.79 | stock grind 60s, fail nếu panic (không phải PASS tuyệt đối) |
| `grind-smoke-cpus4` | 4 | PASS | 60.79 | stock grind 60s, fail nếu panic (không phải PASS tuyệt đối) |
