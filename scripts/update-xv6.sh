#!/usr/bin/env bash
#
# update-xv6.sh — thay source xv6-riscv đang vendor bằng tag/commit khác.
#
# Dùng khi giảng viên chốt tag chính thức (mục "Chốt tag/commit xv6 gốc").
#
#   bash scripts/update-xv6.sh <tag|commit>
#   XV6_UPSTREAM=<url> bash scripts/update-xv6.sh <ref>
#
# Script chỉ thay các file thuộc xv6 upstream (theo .xv6-files); mọi file của
# dự án (tests/, scripts/, docs/, results/, mk/, README.md, .github/workflows/ci.yml)
# được giữ nguyên. Cuối cùng nó nối lại include mk/project.mk vào Makefile và
# cập nhật .xv6-commit.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REF="${1:-}"
if [ -z "$REF" ]; then
    echo "Dùng: bash scripts/update-xv6.sh <tag|commit>" >&2
    exit 2
fi
UPSTREAM="${XV6_UPSTREAM:-https://github.com/mit-pdos/xv6-riscv.git}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Clone $UPSTREAM"
git clone --quiet "$UPSTREAM" "$TMP/xv6"
echo "==> Checkout $REF"
git -C "$TMP/xv6" checkout --quiet "$REF"
NEW_COMMIT="$(git -C "$TMP/xv6" rev-parse HEAD)"
NEW_DESC="$(git -C "$TMP/xv6" log -1 --format='%ad %s' --date=short)"
OLD_PIN="$(head -n 1 .xv6-commit 2>/dev/null || true)"
echo "==> xv6 cũ: ${OLD_PIN:-?}"
echo "==> xv6 mới: $NEW_COMMIT $NEW_DESC"

# 1) Xoá các file xv6 đã vendor trước đó (trừ README/Makefile xử lý riêng).
if [ -f .xv6-files ]; then
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        case "$f" in
            # Các file dự án tự quản / xử lý riêng bên dưới.
            README|Makefile|.gitignore) ;;
            .github/*) ;;
            *) rm -f -- "$f" ;;
        esac
    done <.xv6-files
fi

# 2) Copy file của commit mới (bỏ .github của upstream — dự án tự quản CI;
#    giữ .gitignore của dự án vì đã bổ sung mục riêng).
git -C "$TMP/xv6" ls-files | grep -v '^\.github/' | LC_ALL=C sort >"$TMP/files"
while IFS= read -r f; do
    case "$f" in
        .gitignore) continue ;;
    esac
    mkdir -p "$(dirname "$f")"
    cp "$TMP/xv6/$f" "$f"
done <"$TMP/files"
cp "$TMP/files" .xv6-files

# 3) README gốc (xv6 dùng làm file mẫu trong fs.img) + Makefile gốc + include dự án.
cp "$TMP/xv6/README" README
cp "$TMP/xv6/Makefile" Makefile
cat >>Makefile <<'EOF'

# ---------------------------------------------------------------------------
# ET4290 — mục tiêu của dự án (test/baseline/env-check).
# Khối này phải giữ ở CUỐI Makefile; scripts/update-xv6.sh sẽ tự nối lại
# khi đổi commit xv6. Toàn bộ nội dung nằm trong mk/project.mk.
# ---------------------------------------------------------------------------
include mk/project.mk
EOF

# 4) Ghi pin mới
printf '%s %s\n' "$NEW_COMMIT" "$NEW_DESC" >.xv6-commit

# 5) Kiểm tra nhanh: các file dự án vẫn còn
missing=0
for f in tests/runner.py scripts/baseline.sh mk/project.mk README.md; do
    [ -e "$f" ] || { echo "!! Mất file dự án: $f" >&2; missing=1; }
done
[ "$missing" -eq 0 ] || exit 1

echo
echo "==> Đã vendor xv6 $NEW_COMMIT"
echo "    Bước tiếp theo:"
echo "      make clean && make env-check     # build + boot kiểm tra"
echo "      git diff --stat && git status    # review thay đổi"
echo "    Lưu ý: nếu tag mới đổi API sleep/wakeup, cập nhật docs/architecture.md."
