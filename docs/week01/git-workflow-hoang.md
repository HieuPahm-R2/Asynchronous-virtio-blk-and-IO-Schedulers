# Đưa phần việc tuần 1 của Hoàng lên GitHub

Ngày chuẩn bị: 23/10/2026. Khi kiểm tra, HEAD và origin/main cùng ở a0cfa2e;
chưa stage/commit/push. Git đã có author và gh đã đăng nhập. Các bước dưới
đây do người dùng chạy sau khi xem lại các đầu ra.

## 1. Chuyển sang nhánh riêng

```bash
cd /home/ubuntu/2026.1/HDH/Asynchronous-virtio-blk-and-IO-Schedulers
git status --short --branch
git switch -c docs/hoang-week01-virtio
```

Lệnh switch giữ các thay đổi hiện có trên nhánh mới; không cần sao chép repo.
Nếu nhánh đã được tạo ở lần trước, dùng git switch docs/hoang-week01-virtio.

## 2. Kiểm tra rồi stage phần việc

```bash
make check-text check-mermaid
git diff --check
git add docs/week01 scripts/check-week01-hoang.py \
  results/week01/hoang-2026-10-23
git diff --cached --stat
git diff --cached --check
```

Những gì nên có trong staged diff: tài liệu phân tích, hướng dẫn, file draw.io
2 trang theo bản web, SVG/Mermaid, nguồn/checksum, PDF cá nhân, helper smoke
và bằng chứng 4/4 + 2/2 PASS. Kernel/user/Makefile không có thay đổi.
Không stage fs.img, file .o, file _user binary hay results/local; chúng là
file sinh ra hoặc đã được thay bằng evidence chọn lọc trong results/week01.

## 3. Commit

```bash
git commit -m "docs(week01): add Hoang virtio analysis and xv6 evidence" \
  -m "T1-05H, T1-06: verified build/boot and smoke; sync edited drawio diagrams. Async remains design only."
git log -1 --stat
```

Đây là commit tài liệu/kiểm chứng tuần 1; không mô tả là hoàn thành driver
async hoặc nhiều outstanding đã được đo. Không tạo commit rỗng để chứng minh
đóng góp kernel; phần code kernel sẽ nằm ở task K02 khi nhóm chốt interface.

## 4. Push nhánh và mở PR

```bash
git push -u origin docs/hoang-week01-virtio
gh pr create --web --base main --head docs/hoang-week01-virtio
```

Lệnh gh mở form tạo PR để bạn xem và điền trước khi gửi. Nhờ Hiếu review
phần driver/ownership theo phân công. Chưa merge main cho đến khi nhóm review.

Nếu origin/main đã có commit mới sau lần kiểm tra này, cập nhật nhánh sau khi
commit bằng git fetch origin rồi git rebase origin/main, giải quyết conflict
nếu có, sau đó push. Không dùng force để thay thế lịch sử main.

## Nội dung PR gợi ý

Tiêu đề: docs(week01): Hoang virtio analysis, drawio diagrams and xv6 evidence

T1-05H/T1-06: ghi môi trường máy Hoàng, phân tích virtio_disk_rw/descriptor/IRQ
và sequence stock/async. Sơ đồ draw.io và SVG đồng bộ từ bản ProjectTerm người
dùng đã chỉnh sửa. Bổ sung helper read/write/reboot và log trong
results/week01/hoang-2026-10-23 để người review có bằng chứng ngay trong repo.

Validation: rebuild và env-check PASS; helper 4/4 smoke CPUS=1/4 PASS; stock-fast
2/2 CPUS=1/3 PASS; check-text, check-mermaid và diff-check PASS. Log là lần chạy
23/10/2026 ở a0cfa2e, không phải lần benchmark mới sau khi sửa tài liệu.

Giới hạn: không sửa kernel/user; async ở mức thiết kế; full usertests/grind,
stress 30 phút và max_inflight NOT RUN. Tag GV và review nhóm còn pending.
