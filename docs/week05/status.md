# W5-G01 — Rà trạng thái và chốt candidate tuần 5

**Card W5-G01** (P0, 1,5 h tổng). Chủ trì: **Phạm Trung Hiếu (20233402)**; cả nhóm
xác nhận. Thời điểm rà: **21–22/11/2026** (Asia/Saigon), trên checkout `main` vừa
pull từ `origin`.

Mục đích: đối chiếu thay đổi **sau snapshot 19/11** của kế hoạch tuần 5 (main,
các nhánh tuần 4, PR #11–#13, log máy hai), chốt **một candidate sạch** cho máy
thứ hai và ghi rõ còn thiếu gì. Tài liệu này không thay bằng chứng; mọi dòng trạng
thái phải truy được SHA/log hoặc được đánh dấu **PENDING/NOT RUN**.

> Ghi chú phạm vi thực hiện: theo yêu cầu, công việc tuần 5 được hoàn thiện cho
> phần **Hiếu + Lợi (vai trò chủ trì)**; **bỏ qua** các bước review thuộc Hoàng,
> **bỏ qua W5-G04** (báo cáo/đồng bộ hồ sơ nhóm). Các dòng liên quan được đánh
> dấu rõ để không nhận thay phần của người khác.

---

## 1. Trạng thái thực tế khi bắt đầu

Kế hoạch tuần 5 dựa trên snapshot **19/11** (main `5191ed8`, PR #11 còn Draft).
Repo tại thời điểm bắt đầu việc tuần 5 đã **đi xa hơn snapshot đó**; bảng dưới ghi
đúng trạng thái đã đối chiếu:

| Hạng mục | Snapshot kế hoạch 19/11 | Trạng thái thực tế lúc rà | Bằng chứng |
| :--- | :--- | :--- | :--- |
| `main` | `5191ed8` | **`544673d`** lúc bắt đầu (merge PR #12 từ `week4/hieu-contract-oracle`); **sau W5-G02: `efe2849`** (merge candidate `f5130bb`) | `git log --oneline -1` |
| Nhánh tuần 4 của Lợi | `0dc296e` | **`0dc296e`** (đã nằm trong main qua PR #12) | `git log`, `results/week04/policy-mock/…` |
| Nhánh tuần 4 của Hiếu | `ae6a7cf` (PR #12) | PR #12 **đã merge** vào main; nhánh `week4/hieu-contract-oracle` trên remote tiến tới **`f5130bb`** (PR #13: merge PR #11 của Hoàng vào nhánh Hiếu) | `git ls-remote`, PR refs |
| Nhánh tuần 4 của Hoàng | PR #11 Draft, head tài liệu `e29e824`, code đã kiểm `d39ea8c` | **`e29e824`** (PR #11) và **đã được merge vào nhánh Hiếu** tại `f5130bb` (PR #13); **chưa vào main** | `git log f5130bb`, `git ls-remote` |
| Candidate đã kiểm trên máy Hoàng | `d39ea8c` (code) + `e29e824` (docs) | Đúng: `d39ea8c` là code đã test; `e29e824` là head có tài liệu bổ sung; **`f5130bb` là head tích hợp** (Hiếu + Lợi + Hoàng trên một nhánh) | `docs/week04/acceptance-hoang.md`, `results/week04/hoang-20261116/…` |
| Máy thứ hai | NOT RUN | **Đã chạy trong phiên** trên host `DESKTOP-RL9K1ML` (khác host Hoàng); candidate `f5130bb` **PASS** | [`second-machine.md`](second-machine.md) |
| Review chéo Lợi/Hiếu | PENDING | Phiên này review phần Lợi/Hiếu; **không ký thay Hoàng** (review Hoàng bỏ qua theo yêu cầu) | [`integration.md`](integration.md) §3 |
| Jira PTO | Snapshot 19/11: 29/32 Done; PTO-31 To Do, PTO-33/34 In Progress | **Không truy cập Jira trong phiên này** ⇒ **NOT VERIFIED**; không sửa Jira | — |
| Nhánh/evidence tuần 5 | Chưa có | **Đã có**: `docs/week05/`, `results/week05/`, `scripts/verify-second-machine.py` | cây làm việc |
| `main` sau phiên | — | **`efe2849`** (merge candidate `f5130bb`) | [`integration.md`](integration.md) |

Nguồn đối chiếu: S1 (Jira — không truy cập), S2 (PR #11), S3 (báo cáo/evidence Hoàng
16/11), S4 (thiết kế merge/lifecycle Hiếu), S5 (báo cáo tuần 4). Các nguồn này chỉ
là dữ liệu tham chiếu; không cấp quyền sửa hệ thống ngoài repo.

---

## 2. Candidate chốt cho máy thứ hai

**Candidate: `f5130bb9898c4154c3e761e2c85f3038f3a02a86`**
(nhánh `week4/hieu-contract-oracle`, PR #13; là nhánh Hiếu đã merge PR #11 của Hoàng).
Candidate này **đã được merge vào `main` tại `efe2849`** ở W5-G02; máy hai chạy trên
đúng candidate `f5130bb` (code sau merge trùng nội dung — xem
[`integration.md`](integration.md) §4).

| Thuộc tính | Giá trị |
| :--- | :--- |
| Thành phần | Lợi L01/L02 (`0dc296e`) + Hiếu G01/I01/I02 (`360b4df`, `4fa4de9`, `ae6a7cf`) + Hoàng H01/H02 (`51b2cad`, `d39ea8c`, `a10758b`, `e29e824`) |
| Code đã kiểm trên máy Hoàng | `d39ea8c` (source sạch; `d39ea8c` → `e29e824` chỉ thêm tài liệu/evidence, không đổi kernel/user/scripts/tests) |
| Head tích hợp | `f5130bb` = `ae6a7cf` + merge PR #11; **không thay code** so với `d39ea8c` (chỉ thêm file docs/evidence/scripts test của Hoàng) |
| Điều kiện dùng | Clone sạch, `git status --porcelain` rỗng, checkout đúng `f5130bb`; không dùng working tree đang dirty |
| Chưa đạt | Chưa merge main; máy hai chưa chạy; review chéo Lợi/Hiếu chưa ghi (phiên này bổ sung); review Hoàng đã có cho phần driver/IRQ |

**Vì sao không chọn `main` `544673d`:** main mới có Lợi + Hiếu, **thiếu toàn bộ
phần Hoàng** (real policy/switch harness, stress loaded switch, production 6 case).
Chọn `f5130bb` để máy hai kiểm **bản ghép đủ ba phần** trước khi merge (đúng thứ tự
G01 → H01 → G02 của kế hoạch).

**Vì sao không chọn thẳng `d39ea8c`:** `d39ea8c` thiếu nhánh tài liệu/evidence bổ
sung của Hoàng và chưa gộp vào nhánh Hiếu; `f5130bb` là head tích hợp đã merge
PR #11 và giữ nguyên nội dung code của `d39ea8c`.

---

## 3. Bảng task / owner / SHA / trạng thái / evidence / blocker

| Card | Chủ trì / phối hợp | SHA liên quan | Trạng thái trước phiên | Evidence hiện có | Blocker còn lại |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **W5-G01** rà trạng thái, chốt candidate | Hiếu | `f5130bb` | ✅ phiên này hoàn thiện | tài liệu này | Jira không truy cập (NOT VERIFIED) |
| **W5-H01** máy vật lý thứ hai | Lợi (Hoàng hỗ trợ) | `f5130bb` | ⏳ phiên này thực hiện | `results/week05/second-machine/…` + [`second-machine.md`](second-machine.md) | Hoàng hỗ trợ bỏ qua (theo yêu cầu) |
| **W5-G02** review chéo + tích hợp | Lợi điều phối; cả ba | `f5130bb` → main mới | ⏳ phiên này thực hiện | [`integration.md`](integration.md) | Review Hoàng bỏ qua (theo yêu cầu); PR retarget cần quyền GitHub |
| **W5-H02** nghiệm thu sau tích hợp | Hoàng; Hiếu kiểm oracle | SHA sau merge | ⛔ **NOT RUN** | — | **Ngoài phạm vi yêu cầu** (chủ trì Hoàng); cần chạy trước khi nghiệm thu tuần 5 |
| **W5-I01** review/chốt merge + owner/cancel | Hiếu; Hoàng/Lợi review | `360b4df` + docs | ✅ phiên này hoàn thiện (thiết kế) | [`merge-owner-cancel.md`](merge-owner-cancel.md) | Code **chưa có** (đúng phạm vi); review Hoàng bỏ qua |
| **W5-G03** demo async + mốc GV | Lợi; Hoàng/Hiếu hỗ trợ | candidate + SHA sau merge | ✅ phiên này hoàn thiện runbook/transcript | [`demo.md`](demo.md) | Phản hồi GV **PENDING/không có nguồn** |
| **W5-G04** báo cáo/đồng bộ hồ sơ | Lợi tổng hợp | — | ⛔ **KHÔNG LÀM** theo yêu cầu | — | Cố ý bỏ qua (W5-G04) |
| Prototype merge READ 2 block (có điều kiện) | Hoàng/Lợi/Hiếu | — | ⛔ **DEFERRED** | — | Điều kiện G02/H02 đạt chưa thoả (H02 NOT RUN); không lấy giờ dự phòng correctness |

**Ghi chú về review:** kế hoạch yêu cầu reviewer khác tác giả. Phiên này hoàn thiện
phần Hiếu + Lợi; review của Lợi/Hiếu được ghi trong từng tài liệu tuần 5. **Review
của Hoàng cho các phần đó bỏ qua theo yêu cầu** — không tự ký thay, ghi PENDING ở
nơi cần chữ ký nghiệm thu.

---

## 4. Bằng chứng kế thừa (không làm lại)

Các kết quả dưới đây **đã có trên nhánh/nhánh tích hợp**, không chạy lại nguyên
trạng trừ khi sửa code hoặc theo candidate cuối:

| Nhóm | Kết quả đã có | Nguồn |
| :--- | :--- | :--- |
| Real policy/switch (Hoàng) | 10 ca real policy/boot, 6 chiều switch có tải (Q>0, I=2), 5 boot/CPU stress, negative EXPECTED_FAIL; candidate `d39ea8c` | `results/week04/hoang-20261116/acceptance-d39ea8c/real-and-switch/summary.md` |
| Oracle I01 (Hiếu) | CPU1/4 PASS, 6 mutant EXPECTED_FAIL, READ thật snapshot CPU1 PASS | `results/week04/hoang-20261116/acceptance-d39ea8c/independent-oracle/summary.md` |
| FCFS regression | 20/20 real boot, 4/4 mock, negative EXPECTED_FAIL | `results/week04/hoang-20261116/acceptance-d39ea8c/fcfs-regression/summary.md` |
| Production | 6/6 PASS: boot CPU1, shell CPU3, usertests -q CPU1/4, grind 60s CPU1/4 | `results/week04/hoang-20261116/acceptance-d39ea8c/production-baseline/summary.md` |
| Mock deadline/switch L01/L02 | CPU1/4 PASS + 6 mutant | `results/week04/policy-mock/haree-20261115-035243/summary.md` |
| Week 3 carry-over | SCAN oracle, FCFS, stress cũ | `results/week03/…` (tham chiếu lịch sử) |

Bổ sung trong phiên này: **máy thứ hai PASS** trên candidate `f5130bb`
([`second-machine.md`](second-machine.md)); **tích hợp main `efe2849`** + smoke PASS
([`integration.md`](integration.md)). Vẫn **chưa có**: H02 sau tích hợp, prototype
merge 2 block, phản hồi GV/Jira.

---

## 5. Việc cần làm ngay (theo thứ tự phụ thuộc)

1. **H01** — clone sạch candidate `f5130bb` trên host khác host Hoàng, chạy
   `verify-second-machine.py --full`: policy/switch CPU1/4, oracle I01, regression
   FCFS; lưu `second-machine.json`, raw log, summary, môi trường. ✅ **PASS** —
   `results/week05/second-machine/DESKTOP-RL9K1ML-20261122-091659/`.
2. **G02** — review (phần Lợi/Hiếu) rồi merge `f5130bb` vào `main`; kiểm diff/build/
   smoke sau merge; ghi SHA main mới và phạm vi cần tái kiểm. ✅ **main `efe2849`**;
   smoke real-policy CPU1/4 PASS — `results/week05/post-merge/`.
3. **H02** — hồi quy sau tích hợp trên `efe2849`/SHA sau commit tuần 5: **NOT RUN**
   (chủ trì Hoàng, ngoài phạm vi yêu cầu). Việc này phải chạy trước khi ký nghiệm
   thu cuối.
4. **I01** — chốt thiết kế merge/owner/cancel, contract command/child, checklist
   tuần 6. ✅ [`merge-owner-cancel.md`](merge-owner-cancel.md).
5. **G03** — runbook + transcript demo 10 phút; trạng thái câu hỏi GV. ✅
   [`demo.md`](demo.md).
6. Prototype merge 2 block: **DEFERRED** — điều kiện "G02/H02 đạt" chưa thoả (H02
   NOT RUN), và plan yêu cầu không lấy giờ dự phòng correctness.
7. **G04**: không làm theo yêu cầu.

---

## 6. Đối chiếu tiêu chí nghiệm thu card W5-G01

| # | Tiêu chí kế hoạch | Kết quả |
| :---: | :--- | :--- |
| 1 | Đối chiếu thay đổi sau snapshot 19/11: main, ba nhánh tuần 4, PR #11, log máy hai | ✅ §1 (thực tế: main `544673d` → `efe2849`; PR #12 merged; PR #13 branch `f5130bb`; PR #11 nằm trong `f5130bb`; máy hai đã chạy PASS trong phiên) |
| 2 | Chốt SHA sẽ kiểm; ghi rõ `d39ea8c` là code đã kiểm, `e29e824` là head tài liệu; bỏ việc lặp lại khi đã đủ evidence | ✅ §2 (candidate `f5130bb`; mapping code/docs/integrated head) và §4 (không chạy lại phần đã có) |
| 3 | Đầu ra: bảng task/owner/SHA/trạng thái/evidence/blocker; một candidate sạch cho máy hai | ✅ §2, §3 |
| 4 | Rà PTO-31/33/34, PTO-36/37; card Done không thay evidence; PTO-38 thiết kế không phải merge đã code | ⚠️ Jira **không truy cập** ⇒ **NOT VERIFIED**; ghi rõ trong §1/§3; không sửa Jira |

## 7. Change log

| Ngày | Revision | Nội dung |
| :---: | :--- | :--- |
| 2026-11-22 | `main` `544673d`; candidate `f5130bb` | Rà trạng thái sau snapshot 19/11; chốt candidate tích hợp `f5130bb` (Hiếu+Lợi+Hoàng) cho máy thứ hai; ghi gap/review/Jira NOT VERIFIED; xác định thứ tự H01 → G02 → I01/G03; H02 out-of-scope, G04 bỏ qua, prototype DEFERRED. |
