# Hướng dẫn phần việc tuần 1 của Hoàng

Đề tài 26128, Nguyễn Văn Hoàng 20233413. Thực hiện ngày 23/10/2026, chưa commit.

## Kết quả theo nhiệm vụ được giao

| Nhiệm vụ | Kết quả | Bằng chứng |
| --- | --- | --- |
| Clone và chạy xv6 | Đã clone, build, boot và shell hoạt động | environment.md; env-check.log; build.log |
| Phân tích virtio_disk_rw, descriptor, IRQ | Đã đối chiếu code và ghi lỗi/lock/wait channels | io-path.md |
| Vẽ sequence submit/complete async | Có Mermaid, SVG và contract/pseudocode | async-design.md; diagrams/ |

Đây là đầu ra kỹ thuật cá nhân, không tự đánh dấu toàn bộ tuần 1 của nhóm Done.
Hiếu chưa review; async chưa có code; các tính năng core chưa được nghiệm thu.

## Chỉnh sửa sơ đồ bằng draw.io

Mở [virtio-submit-complete.drawio](diagrams/virtio-submit-complete.drawio) bằng draw.io Desktop hoặc diagrams.net qua File > Open From > Device. Chuyển giữa hai tab **01 Stock xv6** và **02 Async đề xuất** ở cuối canvas. Nhấp đúp nhãn để sửa nội dung, kéo mũi tên để chỉnh đường nối; các đối tượng được giữ dạng native. Trang async vẫn là thiết kế, chưa triển khai kernel.

## Chạy lại

```bash
cd /home/ubuntu/2026.1/HDH/Asynchronous-virtio-blk-and-IO-Schedulers
git rev-parse HEAD
cat .xv6-commit
bash scripts/check-env.sh
make test-fast
python3 scripts/check-week01-hoang.py
make qemu CPUS=1
```

Trong shell xv6:

```text
echo HOANG_DEMO > hdhdemo
cat hdhdemo
sync
ls
```

Thoát QEMU: Ctrl-A rồi X. Chạy lại `make qemu CPUS=1` và `cat hdhdemo` để
kiểm tra cùng fs.img. Sau demo: `rm hdhdemo`, `sync`. Không chạy make clean
hoặc test tạo fresh_fs giữa hai lần boot nếu muốn giữ file demo.
Helper kiểm chứng tự tạo mới fs.img cho mỗi CPU; sẽ thay dữ liệu demo trong
fs.img, không thay file source. Mặc định log theo timestamp, không ghi đè lần cũ.

## Các kết quả đã chạy

- env-check PASS, có hai WARN về gdb-multiarch/clang-format.
- Rebuild kernel + fs.img PASS, mã thoát 0.
- write-read-cpus1 PASS; reboot-read-cpus1 PASS.
- write-read-cpus4 PASS; reboot-read-cpus4 PASS.
- stock boot-smoke PASS; shell-fs-cpus3 PASS.
- Không cộng build thành một test case; không coi các lần boot lặp là case mới.
- usertests/grind/full regression, stress 30 phút, counter max_inflight, GDB trace,
  descriptor exhaustion và error injection: NOT RUN trong phiên này.

Bằng chứng có thể commit tại `results/week01/hoang-2026-10-23/`, gồm checks.json,
build.log, serial log bốn lần boot, stock-fast/meta.json và logs. Đây là bản sao
của results/local/hoang-week01-20261023 (gitignored), không phải lượt chạy mới.
Không lấy log baseline máy khác để nói máy Hoàng đã chạy full regression.

## Kịch bản trình bày 10 phút

1. Phút 0-1: nêu ba đầu việc cá nhân, commit project, xv6 pin và phạm vi thiết kế.
2. Phút 1-3: make qemu, tạo/đọc/sync file; chỉ ra checks.json và các serial log.
3. Phút 3-5: mở virtio_disk.c:216, giải thích 3 descriptor và bit WRITE theo phía device.
4. Phút 5-7: mở trap.c:188 và virtio_disk.c:301, phân biệt MMIO ACK/PLIC complete;
   ai wakeup và ai free_chain; tại sao sleep_prepare phải trước release.
5. Phút 7-9: trình bày sequence async; handle trả trước wait, head map, descriptor
   reclaim trong IRQ đề xuất, giữ request/buffer tới release; completion dispatch tiếp.
6. Phút 9-10: nêu 4/4 smoke CPUS=1/4 và 2/2 stock-fast, chưa chạy baseline đầy đủ;
   đề nghị Hiếu review, hỏi GV tag/API, trình bày nhiệm vụ K02 tiếp theo.

## Câu hỏi cần tự trả lời

- Read sao descriptor data lại có WRITE? Vì device ghi RAM; khác với OUT ghi đĩa.
- NUM=8 có 8 outstanding không? Không, mỗi chain stock dùng 3; giới hạn 2 chain.
- Stock có đúng một outstanding không? Caller sync nhưng nhiều process có thể submit;
  chưa đo max_inflight thực tế nên không khẳng định số quan sát được.
- Ai free descriptor? Stock: caller sau wakeup; async đề xuất: IRQ sau device complete.
- Kênh chờ nào? b cho completion, &disk.free[0] cho tài nguyên.
- Complete trước sleep có treo không? Prepare dưới khóa đăng ký p.chan, wakeup xóa
  p.chan; sleep trả ngay nếu đã được wake. Vẫn phải kiểm tra điều kiện bằng while.
- MMIO ACK có thay PLIC complete không? Không, hai tầng báo nhận riêng.
- Async mới có hoạt động chưa? Chưa; tuần này chỉ thiết kế, chưa thêm syscall/driver mới.
- Vì sao không free khi caller timeout? Device có thể còn DMA, gây use-after-free.
- Read cùng phiên có chắc xuống đĩa không? Có thể hit cache; reboot dùng cùng fs.img
  là kiểm tra mạnh hơn cho dữ liệu lưu trong image, chưa phải kiểm thử mất điện host.

## Điền báo cáo nhóm theo Spec

Dùng Doc/Spec/Progress Report template.docx: thông tin nhóm/kỳ báo cáo, summary
200-300 từ, technical activities, personal contribution, developed code review,
TODO gồm issue/task kỳ sau/milestone; đối chiếu TODO trước với thực tế. Spec yêu
cầu một trang báo cáo tuần; PDF chi tiết cá nhân là phụ lục để học và demo.
Chỉ báo đóng góp Hoàng, không gán việc Hiếu/Lợi nếu chưa có xác nhận. Không tự
điền URL Jira/FigJam/quyền GV, giờ công hay tỷ lệ hoàn thành dự án.

Summary gợi ý cá nhân nằm trong báo cáo PDF; phải tổng hợp lại cùng kết quả hai
thành viên trước khi nộp bản nhóm. Kỳ thực hiện được kiểm chứng ở đây là
23/10/2026, không ghi như đã làm đủ cả tuần 19-25/10.

## Việc chuyển tiếp

- Hiếu review T1-06 và sequence, ghi nhận review thật, chưa đánh dấu thay.
- Nhóm xác nhận tag GV, phạm vi kernel API/syscall và write fence.
- Hoàng K02 (đề xuất 8 giờ, chưa phải thời gian thực đã làm): tách submit/complete
  theo interface K01/K03 đã thống nhất; DoD một request checksum đúng, map head
  tới request, descriptor không rò và hoàn tất trước wait không treo.
- Chạy baseline máy Hoàng CPUS=1 khi thực hiện T1-09H; đây là task ngoài ba đầu
  việc cụ thể của phiên này, chưa hoàn thành bởi smoke test.

Không tạo commit/PR/push trong phiên này theo yêu cầu người dùng.

## Đồng bộ và đưa lên GitHub

Sơ đồ draw.io và SVG đã cập nhật theo [bản web của nhóm](https://app.diagrams.net/#G1lpHCZ3cDq0vzGF7y1B910eJgA_-NZf_m).
[Báo cáo PDF](reports/hoang-week01-2026-10-23.pdf) dùng đúng hình xuất từ bản này.
Xem [hướng dẫn commit và push](git-workflow-hoang.md). Chưa stage, commit hay
push tự động; người dùng thực hiện các bước khi đã xem diff.
