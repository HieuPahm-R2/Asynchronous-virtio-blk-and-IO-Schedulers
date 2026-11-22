# W5-G02 — Review chéo và tích hợp tuần 4 vào `main`

**Card W5-G02** (P0, 3 h tổng; Lợi điều phối PR). Thực thi: **Lợi** (điều phối +
review queue/switch) và **Hiếu** (review lock/snapshot/oracle) trong phiên hoàn
thiện. Ngày: **22/11/2026**.

Mục đích: xử lý nhận xét rồi tích hợp tuần 4 vào `main` theo thứ tự **Lợi → Hiếu →
Hoàng**, kiểm diff/build/smoke sau mỗi bước, ghi SHA mới và phạm vi cần chạy lại.

> Phạm vi phiên: theo yêu cầu, **bỏ qua review thuộc Hoàng** cho phần của Lợi/Hiếu;
> không ký thay. Phần review driver/IRQ của Hoàng đã có sẵn từ nhánh tuần 4. Việc
> retarget/đóng PR trên GitHub không thực hiện được trong phiên (không có quyền
> GitHub); thay bằng **merge local** đúng candidate rồi ghi rõ.

---

## 1. Trạng thái trước tích hợp

| Thành phần | SHA | Trạng thái |
| :--- | :--- | :--- |
| `main` trước merge | `544673d99afdef605272cf4154336c07124b3562` | PR #12 đã merge: Lợi `0dc296e` + Hiếu `360b4df`/`4fa4de9`/`ae6a7cf` |
| Nhánh Lợi | `0dc296e133c9fab1e9b36cc9a52ab416821baf49` | `week4/loi-deadline-switch` (đã vào main qua PR #12) |
| Nhánh Hiếu | `ae6a7cfeddc7e1f66b67a55da70b82d981dc3ac8` | `week4/hieu-contract-oracle` (đã vào main qua PR #12); remote tiến tới `f5130bb` qua PR #13 |
| Nhánh Hoàng | `e29e8248e95ba595f5cd13a5091589a0b2ca5c73` | `week4/hoang-real-policy-stress` = PR #11 (Draft), base nhánh Hiếu; code đã kiểm `d39ea8c` |
| Candidate tích hợp | `f5130bb9898c4154c3e761e2c85f3038f3a02a86` | PR #13 = nhánh Hiếu đã merge PR #11 (đủ ba phần) |

## 2. Thứ tự và cách tích hợp

```
main (544673d)  ←  merge  ←  origin/week4/hieu-contract-oracle (f5130bb)
                              = ae6a7cf (Hiếu) + merge PR #11 (Hoàng e29e824)
```

- Base merge với `main` là `ae6a7cf` (tree `main` = tree `ae6a7cf`), nên merge chỉ
  mang phần Hoàng thêm vào; **không sửa code Lợi/Hiếu**, không conflict.
- Lệnh:

```bash
git fetch origin
git switch main && git pull --ff-only origin main          # 544673d
git merge --no-ff origin/week4/hieu-contract-oracle         # f5130bb
git rev-parse HEAD                                          # efe2849...
```

- **Kết quả:** merge commit **`efe28493d22fd506317df781b87a58bbc9cc54a0`**
  (`main` mới). Thống kê so với `544673d`: **110 file, +13 395 dòng, -7 dòng**
  (toàn bộ là harness/evidence/docs/tests tuần 4 của Hoàng + `user/init.c` thêm chế
  độ test + `mk/project.mk`/`Makefile` target, không đổi selector/pool/driver).
- Các commit tuần 5 nằm **sau** merge commit (docs/week05, evidence H01,
  `scripts/verify-second-machine.py`) và **không đổi code**; HEAD cuối của nhánh
  xem `git log -1` tại thời điểm nghiệm thu.

### 2.1 PR / base / head

| PR | Head | Base | Xử lý |
| :---: | :--- | :--- | :--- |
| #11 (Hoàng) | `e29e824` (code `d39ea8c`) | `week4/hieu-contract-oracle` | Đã merge vào nhánh Hiếu qua PR #13; cần retarget/đóng trên GitHub sau khi push (ngoài phiên) |
| #12 (Hiếu) | `ae6a7cf` | `main` | Đã merge (main cũ `544673d`) |
| #13 (tích hợp) | `f5130bb` | `main` | **Đã merge local** vào `main` tại `efe2849`; nội dung = PR #11 + nhánh Hiếu |

### 2.2 Đẩy nhánh và PR (branch protection)

- Push trực tiếp vào `main` bị remote từ chối: *"Changes must be made through a
  pull request"* (branch protection). Không cưỡng chế bypass.
- Đã push nhánh tích hợp **`week5/loi-hieu-integration`** (HEAD `3406d8e`,
  fast-forward từ `544673d`, chứa merge commit `efe2849` + commit tuần 5 không đổi
  code) và mở **PR #14**:
  <https://github.com/HieuPahm-R2/Asynchronous-virtio-blk-and-IO-Schedulers/pull/14>
  (base `main`, head `week5/loi-hieu-integration`).
- Trạng thái merge vào `main`: xem kết quả thực tế ở PR #14; nếu chưa merge được
  (yêu cầu review/approval), ghi **PENDING** thay vì nhận đã tích hợp.

## 3. Review chéo (theo phạm vi)
| Phần | Reviewer | Kết luận | Trạng thái |
| :--- | :--- | :--- | :---: |
| Driver/IRQ/lifetime, test hooks, stress controller (phần Hoàng) | Hoàng (tự review ở tuần 4) | Đã có `docs/week04/review-hoang.md`; không đổi code trong merge | ✅ có sẵn |
| Selector/switch/queue, giữ tuổi request, commit sau try-submit | **Lợi** | Chấp nhận: pick thuần, EAGAIN không commit, switch validate/no-op trước mutation, không reset queue/age, `last_block` mọi policy | ✅ phiên này |
| Lock/snapshot/oracle, counters kế toán, bất biến D23 | **Hiếu** | Chấp nhận: snapshot một `io_lock`, helper `*_locked` không acquire lồng, oracle độc lập + mutant bắt đúng; FCFS 20 boot và 6 case production có evidence Hoàng | ✅ phiên này |
| Review của Hoàng cho phần Lợi/Hiếu | Hoàng | — | ⏳ **BỎ QUA theo yêu cầu phạm vi** → **PENDING** (không ký thay) |

Ghi chú trung thực: review Lợi/Hiếu được thực hiện trong cùng phiên hoàn thiện
công việc tuần 5 theo yêu cầu; đây không thay chữ ký độc lập của Hoàng hay GV.

## 4. Kiểm diff / build / smoke sau merge

Nguồn: `results/week05/post-merge/` (`real-smoke/`, `real-smoke-console.log`,
`check-text.log`, `git-diff-check.log`, `head.txt`).

| Bước | Lệnh | Kết quả |
| :--- | :--- | :---: |
| Diff code candidate ↔ main mới | `git diff --stat f5130bb HEAD -- kernel user scripts tests Makefile mk .xv6-commit docs/week04` | **rỗng** (tree code/docs tuần 4 giống `f5130bb`) |
| Diff tổng so main cũ | `git diff --stat 544673d HEAD` | 110 file, +13 395/−7 (chỉ phần Hoàng) |
| Build + READ thật smoke sau merge | `check-week04-hoang.py --mode real --repeat 1 --toolprefix riscv64-linux-gnu- --results-dir results/week05/post-merge/real-smoke` | **PASS**: real-policy CPU1/4 PASS, real-negative **EXPECTED_FAIL**, production-restore-smoke PASS |
| Repo encoding | `python3 scripts/check_text.py` | rc 0 |
| Whitespace | `git diff --check` | rc 0 |

Ghi chú: `real-smoke/meta.json` ghi `dirty = True` vì lúc chạy đang có file **chưa
commit của tuần 5** (`docs/week05/`, `results/week05/`, `scripts/verify-second-machine.py`);
các file code/kernel/user/tests **không bị sửa** so với `f5130bb` (diff ở trên rỗng).
Sau khi commit tuần 5, trạng thái này được ghi lại trong lịch sử.

## 5. Phạm vi cần chạy lại (không dùng log cũ thay nghiệm thu)

- Code `main` sau merge **trùng nội dung** candidate `f5130bb` đã được máy hai kiểm
  ([W5-H01](second-machine.md)); vì vậy **không cần** chạy lại toàn bộ H01 cho phần
  code, nhưng **SHA đã đổi** (merge commit + commit tuần 5 phía sau).
- Theo kế hoạch, **W5-H02** (chủ trì Hoàng) phải chạy hồi quy trên SHA `main` mới:
  real policy/switch CPU1/4, stress 5 boot/CPU, oracle/mutant, FCFS 20 boot, 6 case
  production, hook vắng. Trạng thái phiên này: **NOT RUN** (ngoài phạm vi yêu cầu).
- Nếu có sửa code sau merge: tái kiểm **cả hai máy** trên cùng SHA mới; không ghép
  log khác SHA.
- `tests/runner.py --tag baseline` (6 case production) chưa chạy lại trên SHA mới —
  thuộc H02; evidence production 6/6 cũ ở `d39ea8c` là tham chiếu, không thay.

## 6. Đối chiếu tiêu chí nghiệm thu card W5-G02

| # | Tiêu chí kế hoạch | Kết quả |
| :---: | :--- | :--- |
| 1 | Xử lý nhận xét rồi tích hợp lần lượt Lợi → Hiếu → Hoàng; PR #11 retarget sau upstream và kiểm lại diff | ✅ Lợi/Hiếu có trong main từ PR #12; PR #11 merge qua PR #13 rồi vào main `efe2849`; diff kiểm rỗng so candidate; retarget GitHub **ngoài phiên** (không quyền API retarget); đã mở **PR #14** cho phần tuần 5 (base main) |
| 2 | Đầu ra: nhận xét review có người xác nhận khác tác giả; danh sách PR/base/head; SHA main mới; checklist lỗi + phạm vi chạy lại | ✅ §2, §3, §5 (review Hoàng bỏ qua theo yêu cầu, ghi PENDING) |
| 3 | Không merge khi còn lỗi dữ liệu/deadlock/thiếu review; kiểm diff/build/smoke sau mỗi bước; không dùng Sonar thay nghiệm thu kernel | ✅ không phát hiện lỗi dữ liệu/deadlock trong smoke; diff/build/smoke PASS; không dùng Sonar; **review Hoàng bỏ qua theo yêu cầu** (đánh đổi đã ghi) |
| 4 | Dù candidate cũ đạt, SHA sau merge vẫn phải qua W5-H02 | ⏳ **H02 NOT RUN** (chủ trì Hoàng, ngoài phạm vi) — bắt buộc trước nghiệm thu cuối |

## 7. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-22 | `544673d` → **`efe2849`**, candidate `f5130bb` | Merge tuần 4 vào main (PR #11/#13); diff code rỗng so candidate; post-merge real-policy CPU1/4 + production restore PASS, negative EXPECTED_FAIL; repo checks PASS; H02 NOT RUN; review Hoàng bỏ qua (PENDING). |
