# Kết quả test ET4290

- Thời điểm: 2026-10-23T12:13:53+07:00
- Project commit: `a0cfa2e942fd`
- xv6 pin: `f780d7850765`
- Môi trường: Linux-7.2.6-x86_64-with-glibc2.39
- Số CPU khả dụng: 12
- Kết quả: **2 PASS / 0 FAIL**

| Case | CPUS | Trạng thái | Thời gian (s) | Ghi chú |
| --- | ---: | --- | ---: | --- |
| `boot-smoke` | 1 | PASS | 0.85 | boot xv6 + shell nhận lệnh |
| `shell-fs-cpus3` | 3 | PASS | 1.26 | đọc/ghi + shell trên fs.img stock |
