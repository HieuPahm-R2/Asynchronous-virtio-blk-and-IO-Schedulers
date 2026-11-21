"""Oracle cho DEADLINE + đổi policy khi có tải (W4-L01/L02, Lợi).

Quy tắc lấy từ docs/week04/interface.md (D21/D22, bản đề xuất chờ G01 chốt):

D21 DEADLINE (đơn vị tick, READ expire = 50, batch limit = 4):
  1. Có request quá hạn (now - t_enqueue >= 50, so wrap-safe 32 bit) -> lấy
     expiry sớm nhất, hòa theo seq; reason EXPIRED, batch = 0.
  2. Không có, mà batch >= 4 -> FIFO cũ nhất (seq nhỏ nhất); reason FIFO, batch = 0.
  3. Không thì block thấp nhất, hòa seq; reason POSITION, batch += 1.
  Chỉ commit khi driver nhận; IO_EAGAIN không đổi batch/trace.
D22 SWITCH: enum sai -> -22, không đổi gì; cùng policy -> 0, không event;
  khác -> epoch+1, event S. Vào SCAN: head = block dispatch thành công cuối
  (mọi policy) hoặc 0, chiều UP. Vào DEADLINE: batch = 0. Queue/tuổi giữ nguyên,
  INFLIGHT không bị đụng, switch không tự dispatch.
SCAN giữ nguyên D13-D16 tuần 3 (biên logic 0/1999 rồi đảo chiều).

File này tự mô phỏng kịch bản (ADD/TICK/CAP/DONE/SW/DRAIN) trên driver giả 2
slot giống kernel/io_queue_test.c, KHÔNG đọc code C và KHÔNG lấy trace kernel
làm đáp án. MOCK: không nói gì về thiết bị thật, seek hay latency vật lý.

Dùng:
    python3 tests/cases/ioq_policy.py           # in expected từng ca
    python3 tests/cases/ioq_policy.py LOG       # chấm một serial log
"""
from __future__ import annotations

import re
import sys

FSSIZE = 2000
UP, DOWN = 1, -1
FCFS, SCAN, DL = 0, 1, 2
VALID = (FCFS, SCAN, DL)
EXPIRE, BATCH = 50, 4
RSN_NONE, RSN_EXP, RSN_POS, RSN_FIFO = 0, 1, 2, 3
SLOTS = 2
M32 = 0xFFFFFFFF
EINVAL = -22


def A(b): return ("ADD", b)
def T(n): return ("TICK", n)
def C(n): return ("CAP", n)
def SW(p): return ("SW", p)
DN = ("DONE", 0)
DR = ("DRAIN", 0)

# Fixture: phải giống hệt dl_cases[] trong kernel/io_queue_test.c.
DL_CASES = [
    ("dl-position", DL, 1000, [C(0), A(70), A(20), A(90), A(10), A(50), A(30), C(1), DR]),
    ("dl-expired-first", DL, 1000, [C(0), A(500), T(30), A(10), A(20), T(25), C(1), DR]),
    ("dl-tie-expiry", DL, 1000, [C(0), A(300), A(200), T(20), A(5), T(40), C(1), DR]),
    ("dl-batch-boundary", DL, 1000, [C(0), A(1000), A(9), A(8), A(7), A(6), A(5), A(4), C(1), DR]),
    ("dl-old-vs-stream", DL, 1000, [C(1), A(1), A(900), A(2), T(30), DN, A(3), T(30), DN, A(4),
                                    DN, A(5), DN, A(6), DR]),
    ("dl-eagain", DL, 1000, [C(0), A(40), A(30), A(20), A(10), A(60), C(1), DN, C(0), A(5), A(15),
                             C(1), DR]),
    ("dl-wrap", DL, 0xFFFFFFF0, [C(0), A(100), T(40), A(50), T(20), C(1), DR]),
    ("sw-all6", FCFS, 1000, [C(0), A(300), A(100), A(700), A(200), A(600), A(50), A(800), A(400),
                             C(2), SW(SCAN), DN, SW(DL), T(60), DN, SW(SCAN), DN, SW(FCFS), DN,
                             SW(DL), DN, SW(FCFS), DR]),
    ("sw-noop-invalid", FCFS, 1000, [SW(FCFS), SW(7), SW(-1), SW(SCAN), SW(SCAN), C(0), A(30),
                                     A(10), C(1), SW(3), SW(DL), SW(DL), DR]),
    ("sw-keep-age", FCFS, 1000, [C(1), A(1), A(400), T(45), SW(DL), T(10), A(5), A(6), DN, DR]),
    ("sw-scan-head", FCFS, 1000, [C(1), A(300), A(100), A(500), A(200), SW(SCAN), C(0), A(350),
                                  C(1), DR]),
]

CHECKS = ["commit-matches-trace", "drain-each-once", "age-seq-gen-kept", "no-trace-overflow"]


def expired(t_enq, now):
    age = (now - t_enq) & M32
    if age >= 1 << 31:  # âm theo int32
        age -= 1 << 32
    return age >= EXPIRE


def older(a, b):
    """a.t_enqueue trước b.t_enqueue (wrap-safe)."""
    d = (a - b) & M32
    return d >= 1 << 31


class Sim:
    def __init__(self, policy, clock0):
        self.policy, self.now = policy, clock0 & M32
        self.head, self.dir = 0, UP          # logical head SCAN (reset_case head=0, UP)
        self.batch, self.epoch = 0, 0
        self.last = None                     # block dispatch thành công cuối
        self.queue = []                      # [(seq, blk, t_enq)] theo thứ tự đến
        self.slots = [None] * SLOTS
        self.cap = SLOTS
        self.seq = 0
        self.events, self.sw = [], []

    # ---- driver giả: slot trống đầu tiên trong [0, cap) ----
    def submit(self):
        for i in range(min(SLOTS, self.cap)):
            if self.slots[i] is None:
                return i
        return None

    def inflight(self):
        return sum(s is not None for s in self.slots)

    # ---- pick thuần theo policy hiện tại ----
    def pick(self):
        if not self.queue:
            return None
        if self.policy == FCFS:
            return self.queue[0], RSN_NONE, None
        if self.policy == DL:
            best = None
            for r in self.queue:
                if expired(r[2], self.now) and (best is None or older(r[2], best[2])):
                    best = r
            if best:
                return best, RSN_EXP, None
            if self.batch >= BATCH:
                return self.queue[0], RSN_FIFO, None
            return min(self.queue, key=lambda r: (r[1], r[0])), RSN_POS, None
        at = [r for r in self.queue if r[1] == self.head]
        if at:
            return at[0], RSN_NONE, None
        r = self.nearest(self.dir)
        if r:
            return r, RSN_NONE, None
        r = self.nearest(-self.dir)
        return r, RSN_NONE, -self.dir         # cần BOUNDARY trước

    def nearest(self, d):
        if d == UP:
            c = [r for r in self.queue if r[1] > self.head]
            return min(c, key=lambda r: (r[1], r[0])) if c else None
        c = [r for r in self.queue if r[1] < self.head]
        return min(c, key=lambda r: (-r[1], r[0])) if c else None

    def dispatch(self):
        while True:
            p = self.pick()
            if p is None:
                return
            r, rsn, newdir = p
            slot = self.submit()
            if slot is None:
                return                        # EAGAIN: không commit gì
            self.slots[slot] = r
            if newdir is not None:
                bnd = FSSIZE - 1 if self.dir == UP else 0
                self.events.append(f"B bnd={bnd} hb={self.head} ha={self.head} db={self.dir} "
                                   f"da={newdir} ep={self.epoch}")
                self.dir = newdir
            self.queue.remove(r)
            hb, db = self.head, self.dir
            if self.policy == SCAN:
                self.head = r[1]
            if self.policy == DL:
                self.batch = self.batch + 1 if rsn == RSN_POS else 0
            self.last = r[1]
            self.events.append(f"D pol={self.policy} rsn={rsn} seq={r[0]} blk={r[1]} hb={hb} "
                               f"ha={self.head} db={db} da={self.dir} bat={self.batch} ep={self.epoch}")

    def complete(self):
        s = 1 if self.slots[1] is not None else 0
        self.slots[s] = None
        self.dispatch()

    def switch(self, p):
        q, i = len(self.queue), self.inflight()
        if p not in VALID:
            rc = EINVAL
        elif p == self.policy:
            rc = 0
        else:
            rc = 0
            hb = self.head
            if p == SCAN:
                self.head, self.dir = (self.last if self.last is not None else 0), UP
            if p == DL:
                self.batch = 0
            old, self.policy = self.policy, p
            self.epoch += 1
            self.events.append(f"S old={old} new={p} hb={hb} ha={self.head} da={self.dir} "
                               f"bat={self.batch} ep={self.epoch}")
        self.sw.append(f"SW pol={p} rc={rc} q={q} i={i} ep={self.epoch}")
        return q, i, rc

    def run(self, ops):
        loaded = []  # (old, new) của switch thành công khi Q>0 và I>0
        for op, arg in ops:
            if op == "ADD":
                self.seq += 1
                self.queue.append((self.seq, arg, self.now))
                self.dispatch()
            elif op == "TICK":
                self.now = (self.now + arg) & M32
            elif op == "CAP":
                self.cap = arg
                self.dispatch()
            elif op == "DONE":
                if self.inflight():
                    self.complete()
            elif op == "SW":
                old = self.policy
                q, i, rc = self.switch(arg)
                if rc == 0 and arg != old and q > 0 and i > 0:
                    loaded.append((old, arg))
            elif op == "DRAIN":
                self.cap = SLOTS
                self.dispatch()
                while self.inflight():
                    self.complete()
        assert not self.queue, "fixture không drain hết"
        return loaded


def expected():
    out = {}
    for name, pol, clock0, ops in DL_CASES:
        sim = Sim(pol, clock0)
        loaded = sim.run(ops)
        out[name] = (sim.events, sim.sw, loaded)
    return out


def check(text):
    """So serial log với oracle. Trả về danh sách lỗi (rỗng = PASS)."""
    errors = []
    text = text.replace("\r", "")
    if re.search(r"(^|\n)panic:", text):
        errors.append("panic")
    m = re.search(r"^IOQDL DONE fail=(\d+)\s*$", text, re.M)
    if not m:
        errors.append("thiếu marker IOQDL DONE (timeout/không chạy)")
    elif m.group(1) != "0":
        errors.append(f"kernel báo {m.group(1)} check FAIL")
    exp = expected()
    for name, (events, sw, _loaded) in exp.items():
        for c in CHECKS:
            if not re.search(rf"^IOQDL {re.escape(name)} CHK {c} PASS\s*$", text, re.M):
                errors.append(f"{name}: thiếu CHK {c} PASS")
        got = re.findall(rf"^IOQDL {re.escape(name)} EV (.*?)\s*$", text, re.M)
        if got != events:
            errors.append(f"{name}: trace sai\n  expected={events}\n  actual  ={got}")
        got_sw = re.findall(rf"^IOQDL {re.escape(name)} (SW .*?)\s*$", text, re.M)
        if got_sw != sw:
            errors.append(f"{name}: bản ghi SW sai\n  expected={sw}\n  actual  ={got_sw}")
        if not re.search(rf"^IOQDL {re.escape(name)} END n={len(events)}\s*$", text, re.M):
            errors.append(f"{name}: END n khác {len(events)}")
    errors += coverage_errors(exp)
    return errors


def coverage_errors(exp):
    """Fixture phải phủ đủ những gì kế hoạch W4 đòi (tự kiểm fixture, không cần log)."""
    errs = []
    loaded = set(exp["sw-all6"][2])
    need = {(a, b) for a in VALID for b in VALID if a != b}
    if loaded != need:
        errs.append(f"sw-all6: thiếu chiều switch có Q>0,I>0: {sorted(need - loaded)}")
    allev = [e for evs, _, _ in exp.values() for e in evs]
    for rsn, label in ((RSN_EXP, "EXPIRED"), (RSN_POS, "POSITION"), (RSN_FIFO, "FIFO")):
        if not any(f" rsn={rsn} " in e and e.startswith("D pol=2") for e in allev):
            errs.append(f"fixture không có dispatch deadline reason {label}")
    return errs


CASES = [
    {
        "name": "ioq-policy-mock",
        "cpus": 1,
        "tags": ["selftest", "scheduler", "mock", "deadline", "switch"],
        "timeout": 90,
        "expect": [rf"^IOQDL {re.escape(n)} EV {re.escape(ev)}\s*$"
                   for n, (evs, _, _) in expected().items() for ev in evs]
                  + [r"^IOQDL DONE fail=0\s*$"],
        "reject": [r"IOQDL .* FAIL", r"^panic:"],
        "steps": [{"send": "echo BOOT_OK", "expect": [r"^BOOT_OK$"], "timeout": 20}],
        "note": "MOCK: deadline D21 + runtime switch D22 (đề xuất); oracle Python mô phỏng độc lập",
    },
]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        for name, (evs, sw, loaded) in expected().items():
            print(name)
            for e in sw + evs:
                print("   ", e)
        cov = coverage_errors(expected())
        print("coverage:", "OK" if not cov else cov)
        sys.exit(0)
    errs = check(open(sys.argv[1], encoding="utf-8", errors="replace").read())
    for e in errs:
        print("FAIL:", e)
    print("PASS" if not errs else f"FAIL ({len(errs)} lỗi)")
    sys.exit(1 if errs else 0)
