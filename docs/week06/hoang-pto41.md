# Tuần 6 - Nguyễn Văn Hoàng - PTO-41

[PTO-41](https://phamvanthang786.atlassian.net/browse/PTO-41) giao Hoàng chạy một lệnh DMA READ nhiều block và hoàn tất riêng từng request con. Nhánh `week6/hoang-pto41-multi-block-dma` lấy nền `f5a1c04` từ `origin/main`. Log trong hồ sơ này chạy trên checkout sạch của commit triển khai `c6e0dae`.

## Giao diện cho PTO-40

- Build `IO_MERGE_READ=1` cung cấp `virtio_disk_try_submit_merged_read(children, count)`. Dispatcher gọi dưới `io_lock` với 2-4 request READ còn QUEUED, cùng ROOTDEV, mỗi request đúng một block, các block liền kề và duy nhất. Thứ tự phần tử có thể đảo. Driver lấy block nhỏ nhất làm sector đầu và xác định offset từ block thực của từng request.
- Khi trả 0, các child đã INFLIGHT và có cùng descriptor head. Dispatcher phải unlink các child được nhận khỏi pending list và commit thống kê/chính sách trong cùng lần giữ khóa, theo mẫu `unlink_locked` của đường đơn.
- `IO_EINVAL` từ chối nhóm không hợp lệ. `IO_EAGAIN` báo thiếu bounce hoặc descriptor. Không có avail entry mới và các child giữ trạng thái QUEUED để dispatcher retry hoặc chọn READ đơn. Allocator hoàn trả phần descriptor đã lấy nếu không đủ cả chuỗi.
- Giữ hai bounce buffer tĩnh 4 KiB. Mỗi lệnh dùng một chuỗi gồm header, một vùng data dài `count * BSIZE` và status. Bảng con giữ slot, generation và offset cho đến lúc reap, cùng chính descriptor head đã publish.
- Sau khi thiết bị ghi used head, driver kiểm generation và trạng thái từng child. Với status 0, chép đúng 1024 byte trước khi báo DONE và đánh thức waiter. Với status khác 0, tất cả child nhận ERROR và `aio_wait()` trả `IO_EIO`. Hoàn trả chuỗi và bounce một lần cho lệnh, sau fan-out. Slot terminal thuộc caller đến `aio_release()`.
- `completed_async` của driver đếm used entry, còn `completed` và `errors` của request layer đếm child. Khi có merge, hai loại số có đơn vị khác nhau.

## Kết quả QEMU

Mỗi cấu hình 1 và 4 vCPU chạy 8 ca. Harness kiểm riêng 21 checksum FNV-1a theo danh sách block và thứ tự dự kiến. Kernel cũng so từng byte với fixture.

| Ca | Kết quả trên cả hai cấu hình |
| --- | --- |
| READ 2, 3 và 4 block | Mỗi nhóm có 1 avail entry, 1 used entry cùng head. Số lần DONE tương ứng 2, 3 và 4. Ca 3 và 4 nhận danh sách child đảo thứ tự. |
| Lỗi tiêm sau khi thiết bị ghi used | Một lệnh, 4 child EIO, không đọc được buffer qua API. |
| Lỗi do thiết bị trả về | READ 1994-1997 vượt capacity 1996 block, một used head và 4 child EIO. Ca này dùng status thực của QEMU. |
| Hết bounce và hết descriptor | Hai ca riêng. EAGAIN giữ trạng thái/vị trí ring. Retry thành công sau khi reap. Ca descriptor dùng hai single READ để giữ descriptor trong khi hai bounce còn rảnh. |
| Dải bị hở hoặc trùng | EINVAL, không publish, sửa dải rồi thực thi thành công. |

Trước reap ở các ca lỗi, release trả EBUSY. Sau release, handle cũ trả ENOENT. Mỗi boot kết thúc với 21 DONE, 8 ERROR và 29 release. Sau drain có 16 slot request, 8 descriptor, 2 bounce rảnh, cùng 0 QUEUED/INFLIGHT/DONE/ERROR còn giữ slot.

## Tái lập

Chạy ở repo root với toolchain RISC-V, QEMU và Python 3:

```sh
python3 scripts/check-week06-hoang.py --outdir /tmp/pto41-qemu
```

Harness tạo bản sao của fs.img, kiểm bitmap vùng 32 block cuối trước khi ghi fixture, sau đó cắt 4 block cuối trên bản sao. Boot trực tiếp qua QEMU virtio-blk MMIO. Kết thúc bằng build mặc định và kiểm ký hiệu kernel. Mode chỉ bật backend và mode mặc định đều boot đến shell, với test hooks vắng mặt. Mode mặc định cũng loại backend merge.

[Log serial và manifest](../../results/week06/hoang-pto41/) có SHA nguồn, phiên bản tool, checksum image và lệnh QEMU. File PNG trong hồ sơ dựng từ một phần log 4 vCPU để dễ đọc. Thư mục ảnh Drive tuần 5 cung cấp mốc READ đơn, đổi policy và lần chạy máy hai. Thư mục Hoàng thuộc week 06 trống tại lúc rà soát ngày 28/11.

## Hồi quy

Chạy `python3 scripts/check-week04-hoang.py --repeat 1 --results-dir /tmp/pto41-week04`. READ ba policy và stress đổi policy đều PASS trên 1 và 4 vCPU. Hai ca negative control cho EXPECTED_FAIL. Build mặc định boot lại thành công. `make test-fast` đạt 2/2 (boot và shell/filesystem). Xem [hồi quy tuần 4](../../results/week06/hoang-pto41/regression-week04.md) và [smoke](../../results/week06/hoang-pto41/regression-fast.md).

## Ghép vào đường chạy của nhóm

Hồ sơ hiện kiểm trực tiếp hợp đồng của driver qua selftest với nhóm ứng viên dựng sẵn, trên một máy chạy QEMU. PTO-40 sẽ cấp ứng viên từ FCFS/SCAN/deadline và quyết định fallback. PTO-42 sẽ dùng oracle của nhóm để nghiệm thu nhánh ghép. Các ca hủy, orphan/exit, bài đo hiệu năng và tái lập máy hai cho PTO-41 vẫn chờ vòng tích hợp.
