# Hoàng: READ thật, stress switch và nghiệm thu (PTO-31/36/37)

Ngày thực hiện: **16/11/2026**, Asia/Saigon. Đây là công việc tuần 4 chuyển tiếp
sang đầu tuần 5, không phải worklog được ghi lùi về ngày 15/11.

Nhánh `week4/hoang-real-policy-stress` dựa trên `ae6a7cf` của Hiếu, đã chứa
`0dc296e` của Lợi. `main` tại lúc bắt đầu vẫn là `5191ed8`; chưa merge các phần
tuần 4 lên remote. Nhánh cũ và thư mục làm việc cũ được giữ nguyên.

## Chạy phần mới

```bash
# Cần Python 3, make, toolchain RISC-V và QEMU >= 7.2.
python3 scripts/check-week04-hoang.py
# Tương đương: real CPU1/4; stress 5 boot/CPU; negative; production restore.
make test-week04-hoang

# Chạy riêng từng phần, tên thư mục kết quả phải mới:
python3 scripts/check-week04-hoang.py --mode real
python3 scripts/check-week04-hoang.py --mode stress --repeat 5
# Máy có toolchain khác: dùng binary thật, không chỉ đổi tên compiler.
python3 scripts/check-week04-hoang.py --toolprefix riscv64-linux-gnu-
```

Chạy lần lượt trên một checkout vì harness clean/build với các cờ khác nhau.
Không dùng ảnh đĩa cá nhân: host sao `fs.img` sang thư mục tạm, xác minh bitmap
32 block cuối đều free trước khi viết fixture. Negative chỉ lật byte đầu của
block `1968` trên bản sao. Production luôn được build lại và kiểm symbol test.

## READ thật: 10 kịch bản mỗi boot, 70 READ

- Ba policy riêng, sáu chiều đổi giữa ba policy, một ca deadline đã thật sự
  chờ ít nhất 50 tick (~5 giây trên cấu hình pin).
- Mỗi ca nạp hai anchor vào chain thật rồi giữ software reaping để nạp năm
  request QUEUED. Thiết bị vẫn DMA thật; không tạo completion giả.
- Trace được xoá **chỉ trong build test**, giữa ca khi queue rỗng sau hai anchor;
  không reset request, generation, counter hoặc policy. Mỗi trace ngắn đủ 64 event.
- Host dùng mô hình D21/D22 độc lập của Hiếu để tính expected từ input và trạng
  thái trước switch, kiểm từng event/reason/head/direction/epoch. Không dùng thứ
  tự completion hoặc candidate do kernel chọn làm đáp án.
- Kiểm EAGAIN, no-op/enum sai, tuổi/seq/gen không đổi, checksum 1024 byte, stale
  handle sau release và pool/descriptor drain. Fixture trẻ phải luôn dưới ngưỡng
  expiry tới cuối ca; nếu không thì báo FAIL thay vì nhận một oracle không xác định.
- Cờ: `IO_HW_SELFTEST=1 EXTRA_CFLAGS=-DIO_POLICY_HW_SELFTEST`.

## Stress có điều khiển: 4 producer x120 READ, window5

Parent làm controller, bốn child là producer. Sáu phase, mỗi phase 20 READ/worker
(80 READ). Chỉ mở phase kế tiếp khi cả bốn đã drain. Đây là workload có barrier,
không phải stress tải tự nhiên liên tục hoặc benchmark throughput.

Controller đổi `FCFS -> SCAN -> DEADLINE -> SCAN -> FCFS -> DEADLINE -> FCFS`.
Mỗi switch quan sát Q>0 và I=2 dưới chính `io_lock`; hai anchor của phase được
publish trước switch. **78 request còn lại** phải được dispatch sau switch dưới
policy đích, trước khi đổi lần kế tiếp. Như vậy không chỉ đổi tên policy sáu lần
rồi chạy toàn bộ workload dưới FCFS. Mỗi boot hoàn tất 480 READ; 10 boot =4.800
READ, không phải 4.800 test độc lập. Trace dài có thể overflow; stress dùng
snapshot/counters, không tuyên bố trace 64 event là toàn bộ lịch sử 480 request.

Cờ: `IO_STRESS_SELFTEST=1 EXTRA_CFLAGS=-DIO_POLICY_STRESS_SELFTEST`.
Build cũ không có cờ mới vẫn chạy stress FCFS tuần 3, không thêm controller.
Watchdog host giới hạn boot 90 giây; lỗi fixture phải EXPECTED_FAIL, sau đó restore.

## Nghiệm thu chung và máy thứ hai

```bash
# Oracle độc lập, 6 mutant, READ thật FCFS snapshot và restore:
python3 scripts/check-week04-oracle-hieu.py
# FCFS real 10 CPU1 +10 CPU4; negative; pool/queue; restore:
make test-week02
# Production boot CPU1, shell CPU3, usertests -q CPU1/4, grind 60s CPU1/4:
python3 tests/runner.py --tag baseline
make check-text
git diff --check
```

Máy thứ hai phải nhận đúng commit của candidate, chạy harness mới và oracle,
gửi `summary.md`, `meta.json` cùng raw log. Ghi host/OS, compiler/QEMU, CPU,
fixture/seed, source hash, số lượt, negative và restore. Chạy CPU1/4 hoặc QEMU
hai lần trên cùng host **không** được tính là hai máy.

Không tự đóng PTO-36/37 hoặc ghi đã có review của Lợi/Hiếu khi chưa có xác nhận.
Owner/cancel, merge READ mức thiết bị, user API tổng quát và stress 30 phút vẫn
ngoài kết quả của bộ này. Kết quả chạy thực tế: xem `report-hoang.md` khi nghiệm thu.
