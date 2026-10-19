# Pin xv6-riscv và cập nhật

## Đang pin

| | |
| --- | --- |
| Upstream | <https://github.com/mit-pdos/xv6-riscv> |
| Branch | `riscv` |
| Commit | `f780d7850765d74cbdcd1fff4b822d8829f7c9bd` |
| Mô tả | `build with -fno-delete-null-pointer-checks` |
| Ngày commit | 2026-10-15 |
| Ghi tại | `.xv6-commit` |

**Đây là pin tạm** cho tới khi giảng viên chốt tag/commit chính thức cho học
phần (mục "Chốt tag/commit xv6 gốc" — kế hoạch tuần 1). Khi có tag:

```bash
bash scripts/update-xv6.sh <tag-hoac-commit>
make clean && make env-check
git diff --stat        # review thay đổi xv6
```

## Upstream có gì

- Branches: `riscv` (main), `verified`, `verified-quota`, `inode-leak-test`.
- Tags công bố: `verified-v1`, `verified-v2`, `xv6-riscv-rev5` (cũ).
- `test-xv6.py` của upstream vẫn giữ nguyên trong repo để tham khảo/so sánh;
  harness của dự án là `tests/` nhưng dùng cùng cơ chế (pipe stdin/stdout QEMU).

## Những điểm khác biệt đáng chú ý của commit này

1. **API sleep mới**: `sleep_prepare(chan)` + `sleep()` thay cho
   `sleep(chan, lock)`; thêm `io_fence()` cho MMIO. Tài liệu/sách cũ sẽ nói
   khác — xem `docs/architecture.md` mục 1.5.
2. `virtio_disk_rw` theo dõi **nhiều descriptor chain** (info[]), nên baseline
   có thể có >1 request INFLIGHT; không được mô tả stock là "chỉ một request
   toàn hệ thống".
3. Makefile tự dò `TOOLPREFIX` (hỗ trợ `riscv64-linux-gnu-` của Ubuntu) và
   yêu cầu QEMU ≥ 7.2 (`check-qemu-version`).
4. `user/` có thêm `logstress`, `forphan`, `dorphan`, `sync`, `kill`; usertests
   có `-q` (quick), `-c/-C` (continuous).

## Cơ chế vendor

- File của upstream nằm trực tiếp trong repo (kernel/, user/, mkfs/, Makefile,
  README…) đúng như cấu trúc repo đề xuất trong kế hoạch.
- `.xv6-files` = manifest `git ls-files` của upstream tại thời điểm vendor;
  `scripts/update-xv6.sh` dùng manifest này để xoá đúng file cũ trước khi copy
  bản mới.
- File của dự án (tests/, scripts/, docs/, results/, mk/, README.md,
  .github/workflows/ci.yml, .xv6-*) **không** bị đụng.
- Makefile upstream được copy lại rồi nối thêm đúng khối
  `include mk/project.mk` ở cuối.
- `.github` của upstream **không** copy (CI của dự án tự quản); workflow cũ
  upstream nằm ngoài phạm vi.

## Kiểm tra nhanh sau khi update

```bash
git status                                   # chỉ thay file xv6 + .xv6-commit
make clean && make -j"$(nproc)" kernel/kernel fs.img
python3 tests/runner.py --tag fast           # boot + shell
python3 tests/runner.py --tag baseline       # usertests + grind smoke
```

Nếu tag mới đổi API (sleep/wakeup, virtio), cập nhật `docs/architecture.md`
và kiểm tra lại toàn bộ test stock trước khi code tính năng.
