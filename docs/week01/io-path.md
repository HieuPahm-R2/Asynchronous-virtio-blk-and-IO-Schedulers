# Khảo sát virtio và interrupt của Hoàng tuần 1

Người phụ trách: Nguyễn Văn Hoàng, 20233413 (T1-06). Ngày 23/10/2026.
Project commit `a0cfa2e942fd7cf27040ec404b002e5a25c691d9`.
Xv6 pin `f780d7850765d74cbdcd1fff4b822d8829f7c9bd`.
Đã đọc code và chạy smoke trên máy hiện tại, chưa sửa kernel, chưa commit.
Hiếu chưa review; pin chính thức của GV vẫn PENDING theo hồ sơ.

## 1. Kết luận và sơ đồ

`virtio_disk_rw` là API đồng bộ với caller: chỉ trả về sau completion và
thu hồi descriptor. Thiết bị chạy độc lập sau publication/notify; process khác
có thể vào driver khi caller nhả vdisk_lock để ngủ. Không được kết luận stock
chỉ có một request outstanding toàn hệ thống.

`NUM=8`, mỗi request dùng 3 descriptor trực tiếp, nên tối đa 2 chain hoàn chỉnh
cùng giữ descriptor. Đây là giới hạn suy từ code, không phải số đo max_inflight.
Chain đã complete nhưng caller chưa chạy lại vẫn giữ 3 descriptor.

File draw.io đã đồng bộ theo bản web bạn chỉnh sửa: [virtio-submit-complete.drawio](diagrams/virtio-submit-complete.drawio), gồm hai trang Stock xv6 và Async đề xuất.

- [Sequence stock](diagrams/stock-submit-complete.mmd) và [SVG](diagrams/stock-submit-complete.svg).
- [Sequence async đề xuất](diagrams/async-submit-complete.mmd) và [SVG](diagrams/async-submit-complete.svg).
- [Contract async và pseudocode](async-design.md): DESIGN ONLY, chưa triển khai.

## 2. Bản đồ code

Số dòng gắn với commit nêu trên, kiểm tra lại bằng `nl -ba` khi code đổi.

| Vị trí | Nội dung đã đối chiếu |
| --- | --- |
| kernel/bio.c:58-88 | bget: lookup/refcnt, nhả bcache.lock trước acquiresleep |
| kernel/bio.c:92-112 | bread gọi driver khi cache miss; bwrite yêu cầu sleeplock |
| kernel/virtio_disk.c:22-59 | desc, avail/used, free[], used_idx, info[head], ops[head] |
| kernel/virtio_disk.c:155-213 | alloc/free descriptor, free_chain, alloc3 và rollback |
| kernel/virtio_disk.c:216-298 | submit, wait, caller reclaim |
| kernel/virtio_disk.c:301-333 | MMIO ACK, drain used, status, wakeup |
| kernel/trap.c:188-220 | external interrupt, plic_claim, IRQ 1, plic_complete |
| kernel/plic.c:12-47 | priority, enable, claim và complete |
| kernel/proc.c:547-595 | sleep_prepare, sleep và wakeup |
| kernel/virtio.h:53-99 | NUM, flags, rings và request header |
| kernel/riscv.h:370-375 | io_fence: fence iorw, iorw + compiler memory clobber |

## 3. Phân tích virtio_disk_rw

1. `sector = b->blockno * (BSIZE / 512)`: BSIZE=1024, block 17 bắt đầu ở sector
   34; một request stock truyền 1024 byte, tương đương hai sector 512 byte.
2. Lấy vdisk_lock, cấp 3 descriptor. Thiếu tài nguyên thì alloc3 rollback các
   descriptor vừa cấp dở. Caller prepare trên `&disk.free[0]`, nhả khóa, sleep,
   lấy lại khóa và thử lại. Ba chỉ số descriptor không cần liên tiếp nhau.
3. Header ở `disk.ops[head]` có lifetime toàn cục: type IN=0 hoặc OUT=1,
   reserved=0, sector. Header không được để trên stack sống ngắn khi tách async.
4. Nối header -> data -> status. Status bắt đầu 0xff. Map `info[head].b=b`, đặt
   `b->disk=1` trước khi publish để IRQ tìm đúng buffer.
5. Ghi head vào `avail.ring[avail.idx % NUM]`; fence; tăng avail.idx; fence;
   ghi QUEUE_NOTIFY=0. Số 0 là queue number, không phải request ID.
6. `while (b->disk == 1)`: sleep_prepare(b), release vdisk_lock, sleep(),
   acquire vdisk_lock. Không giữ spinlock trong lúc process ngủ.
7. Sau complete, caller xóa info[head].b và free_chain(head), nhả vdisk_lock.
   `bread` mới đặt valid=1; tầng dùng buffer sau đó gọi brelse. IRQ và driver
   không tự brelse thay caller.

| Descriptor | Địa chỉ và kích thước | Flags READ | Flags WRITE |
| --- | --- | --- | --- |
| Header idx[0] | &disk.ops[head], 16 byte | NEXT=1 | NEXT=1 |
| Data idx[1] | b->data, 1024 byte | NEXT + WRITE=3 | NEXT=1 |
| Status idx[2] | &info[head].status, 1 byte | WRITE=2 | WRITE=2 |

VRING_DESC_F_WRITE có nghĩa device được ghi RAM, không phải lệnh ghi đĩa.
Vì vậy data của READ có WRITE; data của WRITE không có bit này. Indirect
Descriptor và multi-queue bị tắt ở negotiate (virtio_disk.c:85-95), nên không
suy giới hạn 2 chain của stock sang mọi driver virtio.

## 4. Descriptor lifecycle và backpressure

```text
FREE -> RESERVED -> CHAIN READY -> PUBLISHED -> DEVICE COMPLETED
     -> REAPED BY IRQ -> FREED BY CALLER -> FREE
```

Đây là tên trạng thái phục vụ giải thích; stock chưa có enum request như vậy.
Sau publication, device đã có thể đọc chain, không chỉ sau notify.
`free_chain` lưu flags/next trước khi free descriptor hiện tại rồi đi theo NEXT.
`free_desc` xóa addr/len/flags/next, đặt free[i]=1 và wakeup(&disk.free[0]).

| Channel | Điều kiện | Nguồn wakeup |
| --- | --- | --- |
| &disk.free[0] | alloc3 chưa lấy đủ 3 descriptor | free_desc khi caller reclaim hoặc rollback |
| b | b->disk còn 1 | virtio_disk_intr sau used entry thành công |

Hai chain giữ 6 descriptor thì caller thứ ba còn 2 để thử; alloc3 rollback
phần dở rồi chờ. IRQ complete chưa làm free[] tăng ngay trong stock: caller
phải được CPU chạy lại mới reclaim. Không dựa completion order để map request:
used entry chứa head descriptor, dùng info[head].

## 5. Lock và chống mất wakeup

bcache.lock bảo vệ lookup/refcnt/LRU, buf.lock là sleeplock bảo vệ buffer,
vdisk_lock bảo vệ descriptor/ring/map/b.disk. bget nhả bcache.lock TRƯỚC khi
acquiresleep(buf.lock), không phải ba khóa lồng nhau liên tục. Caller giữ
buf sleeplock khi vào driver; nhả vdisk_lock trước khi sleep. Primitive chờ
lấy p->lock nội bộ theo proc.c.

```text
Caller giữ vdisk_lock: kiểm tra b.disk -> sleep_prepare(b)
Caller nhả vdisk_lock
IRQ có thể chạy: b.disk=0; wakeup(b) -> p.chan=0
Caller gọi sleep(): thấy p.chan==0 nên trả ngay, không mất wakeup
Caller lấy lại vdisk_lock, kiểm tra lại while
```

Nếu process đã SLEEPING, wakeup đặt RUNNABLE; không đảm bảo được chạy ngay.
Không đổi thành release rồi mới prepare. IRQ không sleep, không nhả sleeplock
của process khác và không copyout. Thứ tự này đúng với pin mới, không thay bằng
sleep(chan, lock) của một số bản sách cũ.

## 6. Interrupt path và lỗi

QEMU ghi data/status/used rồi phát IRQ 1 (VIRTIO0_IRQ). Từ user đi qua
uservec/usertrap; từ kernel đi qua kernelvec/kerneltrap. Hai nhánh cùng gọi
devintr. Với scause=0x8000000000000009, devintr claim PLIC, dispatch IRQ 1 vào
virtio_disk_intr. Handler lấy vdisk_lock, ACK MMIO INTERRUPT_STATUS & 0x3,
fence, drain mọi used entry còn lại. `used.ring[used_idx % NUM].id` là head,
không phải blockno/PID. Với status=0, tìm b, đặt b.disk=0, wakeup(b), tăng
used_idx. Nhả khóa, trả về; devintr mới plic_complete(irq). MMIO ACK và PLIC
complete là hai tầng riêng; một ngắt có thể xử lý nhiều completion.

| Trường hợp | Stock hiện tại | Đề xuất cho tuần triển khai |
| --- | --- | --- |
| Hết descriptor | rollback + sleep/retry | QUEUED hoặc EAGAIN, IRQ không ngủ |
| status khác 0 | panic(virtio_disk_intr status) | ERROR, trả lỗi và reclaim đúng một lần |
| Free sai/trùng | panic ở free_desc | invariant và test double free |
| Device không complete | chờ không có timeout | bàn reset/cancel, không free DMA chỉ vì timeout |
| Used ID không hợp lệ | tin dữ liệu device, thiếu validate bounds đầy đủ | validate map/state trước dereference |

OASIS định nghĩa status OK=0, IOERR=1, UNSUPP=2. Không có error injection
trong lần chạy này. Giới hạn outstanding, hết descriptor, IOERR và lost-wakeup
được phân tích tĩnh, chưa có test động riêng cho các nhánh này.

## 7. Kết quả và việc cần review

- env-check exit 0; log results/local/hoang-week01-20261023/env-check.log.
- Build bắt buộc rebuild thành công; checks.json và build.log.
- 4/4 smoke read/write/reboot, CPUS=1/4 PASS; stock-fast 2/2 PASS.
- Reboot đọc lại sau sync kiểm tra cùng fs.img; không phải crash/power-loss test.
- Full usertests/grind, stress 30 phút và max_inflight: NOT RUN trong phiên này.
- Kernel/user/mkfs/Makefile/mk không đổi. Không lấy baseline máy cũ làm số đo mới.
- [ ] Hiếu review bản đồ code, lock, descriptor/error path.
- [ ] Nhóm chốt interface với Lợi/Hiếu và write ordering.
- [ ] GV xác nhận pin và phạm vi async kernel API hay syscall.

Nguồn: mã nguồn local tại commit nêu trên; Doc/T1/02_Checklist_tuan_1.md,
04_Backlog_va_phan_cong.md và 03_De_xuat_thiet_ke_26128.md.
[VIRTIO 1.2 mục 2.7 và 5.2.6](https://docs.oasis-open.org/virtio/virtio/v1.2/virtio-v1.2.html),
đối chiếu 23/10/2026, dùng cho flags/ring/sector/status; không sao chép giải pháp project.

## 8. Đồng bộ sơ đồ và bằng chứng để review

Bố cục đã cập nhật theo [ProjectTerm - ET4290](https://app.diagrams.net/#G1lpHCZ3cDq0vzGF7y1B910eJgA_-NZf_m); SVG lấy trực tiếp từ draw.io.
Xem [nguồn và checksum](diagrams/drawio-source.json). Thứ tự 20 bước stock và
21 bước async không đổi; thay đổi hình thức không chứng minh triển khai async.
Bằng chứng có thể commit tại [results/week01/hoang-2026-10-23](../../results/week01/hoang-2026-10-23/README.md), sao chép từ results/local, không phải lượt test mới.
Báo cáo PDF: [hoang-week01-2026-10-23.pdf](reports/hoang-week01-2026-10-23.pdf).
