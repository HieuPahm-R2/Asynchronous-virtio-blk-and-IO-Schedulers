# W2-G01 — bằng chứng contract async READ (2026-10-30)

**Card:** W2-G01 (CARD 1/9) — Chốt interface request, buffer ownership và quy tắc
khóa. **Owner:** Phạm Trung Hiếu. **Reviewer:** Nguyễn Văn Hoàng, Phạm Quý Lợi
(**chưa review — PENDING**).

**Base chạy:** `e8095001b2e64f361cd80b25e98a1bea5fd60888` (origin/main, 3 PR tuần 1
đã merge) · **Pin xv6:** `f780d7850765d74cbdcd1fff4b822d8829f7c9bd` (tạm, GV
chưa xác nhận) · **Nhánh:** `week2/hieu-request` · **Máy:** Windows 11 + WSL2
Ubuntu-24.04, 6 CPU, QEMU 8.2.2, riscv gcc 13.3.0.

## Đầu ra của card

| File | Nội dung |
| --- | --- |
| [`docs/week02/interface.md`](../../../docs/week02/interface.md) | Contract đầy đủ: D1–D10, chữ ký/API, ownership, lock order, state machine, 3 kịch bản review, câu hỏi GV/PTO |
| [`kernel/io_request.h`](../../../kernel/io_request.h) | Header contract: struct/enum/handle/API/prototypes, compile độc lập |
| [`docs/week01/kickoff.md`](../../../docs/week01/kickoff.md) | Cập nhật trạng thái thật đầu tuần 2 + câu hỏi GV |
| `docs/architecture.md`, `docs/week01/async-design.md`, `docs/week01/decisions_report.md` | Trỏ về contract, đánh dấu mô hình cũ đã bị thay thế |

## Kết quả kiểm tra

| # | Kiểm tra | Kết quả | Log |
| ---: | --- | --- | --- |
| 1 | `io_request.h` compile độc lập `-Wall -Werror -std=gnu11` + 3 `_Static_assert` (size 1080, NREQ 16, sector×2) | **PASS** | [header-check.log](logs/header-check.log) |
| 2 | `make clean && make -j6` (base + contract không đổi kernel) | **PASS** | [build.log](logs/build.log) |
| 3 | `make check-text` (UTF-8/mojibake/LF, toàn bộ file trong commit) | **PASS** | [check-text.log](logs/check-text.log) |
| 4 | `make test-fast` — boot-smoke CPUS=1, shell-fs-cpus3 CPUS=3 | **PASS 2/2** | [test-fast.log](logs/test-fast.log) |

## NOT RUN (ghi đúng trạng thái)

- **T01–T13**: chưa có implementation W2-I01/I02/H01/H02/L01, nên toàn bộ test
  async **chưa chạy**. Không lấy contract/thiết kế làm kết quả test.
- `make test`, `make test-slow`, `make baseline`: không cần cho card contract.
- **Review**: Hoàng + Lợi review cùng revision = commit của PR này — **PENDING**.

## Tiêu chí nghiệm thu card (đối chiếu `docs/week02/interface.md` §10)

- [x] Một contract duy nhất; hết mâu thuẫn buffer/lock với tài liệu tuần 1.
- [x] Mỗi hàm ghi context, khóa vào/ra, hành vi hết tài nguyên.
- [x] 3 kịch bản review trên giấy (hết pool, IRQ trước wait, head reuse).
- [x] Header compile sạch; base build + check-text + test-fast PASS.
- [x] Câu hỏi GV + PTO ghi PENDING có owner, không ghi "đã duyệt".
- [ ] Hoàng review driver/IRQ/lock (D6/D7) — PENDING.
- [ ] Lợi review queue/state/error (D5/D8) + đối chiếu PTO — PENDING.

Card chỉ được đóng khi cả hai reviewer ký cùng revision và mục PTO được rà
(xem `interface.md` §9.2 và §12).
