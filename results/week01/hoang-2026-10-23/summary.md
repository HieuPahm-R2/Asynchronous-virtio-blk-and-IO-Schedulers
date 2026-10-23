# Kiểm chứng máy Hoàng - tuần 1

Commit: `a0cfa2e942fd7cf27040ec404b002e5a25c691d9`

| Check | Kết quả |
| --- | --- |
| build | PASS |
| write-read-cpus1 | PASS |
| reboot-read-cpus1 | PASS |
| write-read-cpus4 | PASS |
| reboot-read-cpus4 | PASS |

Chỉ là smoke; usertests/grind, stress 30 phút và max_inflight: NOT RUN.
Reboot bằng cách kết thúc QEMU sau sync rồi mở lại cùng fs.img; không mô phỏng mất điện.
Không kết luận tốc độ hoặc độ bền khi host mất điện từ kiểm tra này.
