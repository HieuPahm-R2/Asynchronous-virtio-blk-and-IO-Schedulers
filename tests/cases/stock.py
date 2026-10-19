"""Test case stock (chưa sửa kernel) — baseline của dự án ET4290.

Mỗi case là một dict:
  name, cpus, tags, timeout, boot_timeout, fresh_fs,
  steps: [ {send, expect, reject, timeout} ],
  expect / reject: kiểm tra trên toàn bộ serial,
  survive_s: chạy thêm N giây không được panic (dùng cho stress),
  note: mô tả ngắn hiện trong summary.

Tag đang dùng:
  fast      — smoke test nhanh (boot, shell)
  baseline  — bộ đo baseline stock (make baseline)
  usertests — các ca usertests
  stress    — ca chạy dài, mặc định KHÔNG chạy trong `make test`
  slow      — ca rất lâu, mặc định KHÔNG chạy (dùng `make test-slow`)
  ci        — chạy trên GitHub Actions
"""

PASS = r"^ALL TESTS PASSED$"
FAILED = r"FAILED"

CASES = [
    {
        "name": "boot-smoke",
        "cpus": 1,
        "tags": ["fast", "baseline", "ci"],
        "timeout": 90,
        "expect": [r"^init: starting sh"],
        "steps": [
            {
                "send": "echo BOOT_OK",
                "expect": [r"^BOOT_OK$"],
                "timeout": 20,
            }
        ],
        "note": "boot xv6 + shell nhận lệnh",
    },
    {
        "name": "shell-fs-cpus3",
        "cpus": 3,
        "tags": ["fast", "baseline", "ci"],
        "timeout": 120,
        "steps": [
            {"send": "ls", "expect": [r"README"], "timeout": 30},
            {"send": "echo ET4290_OK", "expect": [r"^ET4290_OK$"], "timeout": 30},
            {
                "send": "cat README",
                "expect": [r"xv6 is a re-implementation"],
                "timeout": 60,
            },
        ],
        "note": "đọc/ghi + shell trên fs.img stock",
    },
    {
        "name": "usertests-quick-cpus1",
        "cpus": 1,
        "tags": ["baseline", "usertests"],
        "timeout": 900,
        "reject": [FAILED],
        "steps": [
            {
                "send": "usertests -q",
                "expect": [PASS],
                "timeout": 850,
            }
        ],
        "note": "stock usertests -q (CPUS=1)",
    },
    {
        "name": "usertests-quick-cpus4",
        "cpus": 4,
        "tags": ["baseline", "usertests"],
        "timeout": 900,
        "reject": [FAILED],
        "steps": [
            {
                "send": "usertests -q",
                "expect": [PASS],
                "timeout": 850,
            }
        ],
        "note": "stock usertests -q (CPUS=4)",
    },
    {
        "name": "grind-smoke-cpus1",
        "cpus": 1,
        "tags": ["baseline", "stress"],
        "timeout": 120,
        "survive_s": 60,
        "reject": [r"^panic:"],
        "steps": [{"send": "grind", "timeout": 5}],
        "note": "stock grind 60s, fail nếu panic (không phải PASS tuyệt đối)",
    },
    {
        "name": "grind-smoke-cpus4",
        "cpus": 4,
        "tags": ["baseline", "stress"],
        "timeout": 120,
        "survive_s": 60,
        "reject": [r"^panic:"],
        "steps": [{"send": "grind", "timeout": 5}],
        "note": "stock grind 60s, fail nếu panic (không phải PASS tuyệt đối)",
    },
    {
        "name": "usertests-full-cpus1",
        "cpus": 1,
        "tags": ["slow", "usertests"],
        "timeout": 2400,
        "reject": [FAILED],
        "steps": [
            {"send": "usertests", "expect": [PASS], "timeout": 2350}
        ],
        "note": "stock usertests đầy đủ (CPUS=1), rất lâu",
    },
    {
        "name": "usertests-full-cpus4",
        "cpus": 4,
        "tags": ["slow", "usertests"],
        "timeout": 2400,
        "reject": [FAILED],
        "steps": [
            {"send": "usertests", "expect": [PASS], "timeout": 2350}
        ],
        "note": "stock usertests đầy đủ (CPUS=4), rất lâu",
    },
]
