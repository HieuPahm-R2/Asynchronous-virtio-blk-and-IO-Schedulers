"""W4-I01 model độc lập cho DEADLINE (D21), runtime switch (D22) và snapshot (D23).

File này là *mô hình tính expected từ contract*, không đọc code C và không lấy
trace/đáp án của kernel làm expected:

- D21 (docs/week04/interface.md §D21): tuổi = now - t_enqueue (int32 wrap-safe);
  READ expire = 50 tick, batch limit = 4. Có expired -> chọn expiry sớm nhất
  (t_enqueue nhỏ nhất), hòa theo enqueue_seq. Không có expired: nếu batch >= 4
  -> FIFO request cũ nhất; ngược lại block thấp nhất (hòa theo seq). Commit
  EXPIRED/FIFO mở batch mới (batch=0); POSITION tăng batch.
- D22: enum sai -> IO_EINVAL, không đổi gì; cùng policy -> no-op rc 0, không
  tăng epoch/counter; khác -> epoch+1, một sự kiện SWITCH. Vào SCAN: head =
  block dispatch thành công cuối (mọi policy) hoặc 0, dir=UP. Vào DEADLINE:
  batch=0. Switch không đổi queue/id/gen/seq/t_enqueue, không đụng INFLIGHT.
- D23: snapshot một khóa, kế toán S/C/E/R tích lũy, Q/I/D/X/F hiện tại.
  Mock selftest không dùng request layer thật nên S=C=E=R=0, Q=I=D=X=0,
  F=IO_NREQ=16, descriptor free = NUM = 8, latency samples = 0.

Mô phỏng đúng driver giả 2 slot + đồng hồ giả của kernel/io_queue_test.c:
  ADD -> enqueue + dispatch; TICK -> tăng đồng hồ; CAP -> đổi số slot mở rồi
  dispatch; DONE -> hoàn tất slot cao nhất rồi dispatch; SW -> đổi policy;
  DRAIN -> mở đủ slot và drain hoàn toàn.
Driver giả nhận request vào slot trống đầu tiên trong [0, min(2, cap)) và trả
EAGAIN khi hết slot (không commit gì). Mock: không nói gì về thiết bị thật.
"""
from __future__ import annotations

FSSIZE = 2000
NUM_DESC = 8          # NUM của virtio pin
IO_NREQ = 16          # pool size
SLOTS = 2             # driver giả 2 slot
EXPIRE = 50           # IOQ_DL_READ_EXPIRE
BATCH = 4             # IOQ_DL_BATCH
M32 = 0xFFFFFFFF
EINVAL = -22
UP, DOWN = 1, -1
FCFS, SCAN, DL = 0, 1, 2
POLICIES = (FCFS, SCAN, DL)
RSN_NONE, RSN_EXPIRED, RSN_POSITION, RSN_FIFO = 0, 1, 2, 3

# Fixture W4-I01. PHẢI giống hệt i01_cases[] trong kernel/io_queue_test.c.
def A(block): return ("ADD", block)
def T(n): return ("TICK", n)
def C(n): return ("CAP", n)
def SW(p): return ("SW", p)
DN = ("DONE", 0)
DR = ("DRAIN", 0)

I01_CASES = [
    # D21: tuổi 49 < 50 -> POSITION; hết EAGAIN thì dispatch tiếp.
    ("i01-dl-age-before", DL, 500, [C(0), A(40), A(10), T(49), C(1), DN, DN, DR]),
    # D21: tuổi đúng 50 -> EXPIRED; cùng expiry hòa theo seq.
    ("i01-dl-age-at", DL, 500, [C(0), A(40), A(10), T(50), C(1), DN, DN, DR]),
    # D21: expired thắng request mới ở block thấp hơn.
    ("i01-dl-age-after", DL, 500, [C(0), A(40), T(51), A(5), C(1), DN, DN, DR]),
    # D21: 4 POSITION rồi FIFO lấy request cũ block 1000 (batch boundary).
    ("i01-dl-batch-boundary", DL, 1000,
     [C(0), A(1000), A(9), A(8), A(7), A(6), A(5), C(1), DN, DN, DN, DN, DN, DN, DR]),
    # D21/D16: EAGAIN trước candidate (cổng đóng) và sau candidate không commit.
    ("i01-dl-eagain", DL, 1000, [C(0), A(40), A(30), T(60), C(1), DN, C(0), DR]),
    # D21: đồng hồ wrap qua 0xFFFFFFFF.
    ("i01-dl-wrap", DL, 0xFFFFFFF0, [C(0), A(100), T(50), A(50), C(1), DN, DN, DR]),
    # D21: nhiều expired khác tuổi -> chọn expiry (t_enqueue) sớm nhất.
    ("i01-dl-expired-order", DL, 1000,
     [C(0), A(500), T(10), A(300), T(60), C(1), DN, DN, DR]),
    # D22: switch giữ tuổi -> request cũ vẫn expired dưới DEADLINE.
    ("i01-sw-keep-age", FCFS, 1000,
     [C(0), A(40), T(45), SW(DL), T(10), A(5), C(1), DN, DN, DR]),
    # D22: no-op/không hợp lệ không đổi gì; queue rỗng vẫn switch được.
    ("i01-sw-noop-invalid", FCFS, 1000,
     [SW(FCFS), SW(9), SW(-3), SW(SCAN), SW(SCAN), C(0), A(30), A(10), C(1),
      SW(9), SW(DL), SW(DL), DR]),
    # D22: vào DEADLINE reset batch (không reset thì pick kế tiếp thành FIFO).
    ("i01-sw-batch-reset", DL, 1000,
     [C(0), A(1000), A(9), A(8), A(7), A(6), A(5), C(1), DN, DN, DN, SW(FCFS),
      SW(DL), DN, DR]),
    # D22: vào SCAN lấy last_block của FCFS làm head, dir=UP; switch khi Q>0,I>0.
    ("i01-sw-scan-head", FCFS, 1000,
     [C(1), A(300), A(100), A(500), A(200), SW(SCAN), C(0), A(350), C(1), DR]),
    # D22: đủ 6 chiều chuyển giữa 3 policy, mỗi lần switch đều có Q>0 và I>0.
    ("i01-sw-all6", FCFS, 1000,
     [C(2), A(300), A(100), A(700), A(200), A(600), A(50), A(800), A(400),
      SW(SCAN), SW(DL), SW(FCFS), SW(DL), SW(SCAN), SW(FCFS), DR]),
]

# Nhóm kiểm mà kernel tự in cho mỗi ca (run_scenario trong io_queue_test.c).
CHECKS = [
    "commit-matches-trace",
    "drain-each-once",
    "age-seq-gen-kept",
    "no-trace-overflow",
    "snapshot-invariants",
]


def signed_age(now, t_enqueue):
    """now - t_enqueue theo int32 (wrap-safe trong miền D21)."""
    d = (now - t_enqueue) & M32
    return d - (1 << 32) if d >= 1 << 31 else d


def expired(t_enqueue, now):
    return signed_age(now, t_enqueue) >= EXPIRE


class Sim:
    """Mô hình tất định của queue + driver giả 2 slot (contract D21/D22)."""

    def __init__(self, policy, clock0):
        self.policy = policy
        self.now = clock0 & M32
        self.head = 0                       # logical head của SCAN
        self.dir = UP
        self.batch = 0
        self.epoch = 0
        self.last = None                    # block dispatch thành công cuối
        self.queue = []                     # [seq, block, t_enqueue] theo thứ tự đến
        self.slots = [None] * SLOTS
        self.cap = SLOTS
        self.seq = 0
        self.events = []
        self.switches = []
        self.counters = {"enqueued": 0, "dispatched": 0, "eagain": 0,
                         "boundary_events": 0, "policy_switches": 0,
                         "dl_expired": 0, "dl_fifo": 0}

    # -- driver giả --------------------------------------------------------
    def _free_slot(self):
        for i in range(min(SLOTS, self.cap)):
            if self.slots[i] is None:
                return i
        return None

    def inflight(self):
        return sum(s is not None for s in self.slots)

    def _complete(self):
        s = 1 if self.slots[1] is not None else 0
        self.slots[s] = None
        self.dispatch()

    # -- pick thuần theo policy hiện tại ----------------------------------
    def _pick(self):
        if not self.queue:
            return None
        if self.policy == FCFS:
            return self.queue[0], RSN_NONE, None
        if self.policy == DL:
            best = None
            for r in self.queue:
                if not expired(r[2], self.now):
                    continue
                if best is None or signed_age(r[2], best[2]) < 0:
                    best = r
            if best is not None:
                return best, RSN_EXPIRED, None
            if self.batch >= BATCH:
                return self.queue[0], RSN_FIFO, None
            return min(self.queue, key=lambda r: (r[1], r[0])), RSN_POSITION, None
        at = [r for r in self.queue if r[1] == self.head]
        if at:
            return at[0], RSN_NONE, None
        near = self._nearest(self.dir)
        if near is not None:
            return near, RSN_NONE, None
        return self._nearest(-self.dir), RSN_NONE, -self.dir  # cần BOUNDARY

    def _nearest(self, direction):
        if direction == UP:
            cand = [r for r in self.queue if r[1] > self.head]
            return min(cand, key=lambda r: (r[1], r[0])) if cand else None
        cand = [r for r in self.queue if r[1] < self.head]
        return max(cand, key=lambda r: (r[1], -r[0])) if cand else None

    # -- dispatch/commit ---------------------------------------------------
    def dispatch(self):
        while True:
            picked = self._pick()
            if picked is None:
                return
            r, rsn, newdir = picked
            if self._free_slot() is None:
                self.counters["eagain"] += 1     # EAGAIN: không commit gì
                return
            self.slots[self._free_slot()] = r
            if newdir is not None:
                bnd = FSSIZE - 1 if self.dir == UP else 0
                self.events.append(
                    f"B bnd={bnd} hb={self.head} ha={self.head} db={self.dir} "
                    f"da={newdir} ep={self.epoch}")
                self.counters["boundary_events"] += 1
                self.dir = newdir
            self.queue.remove(r)
            hb, db = self.head, self.dir
            if self.policy == SCAN:
                self.head = r[1]
            if self.policy == DL:
                if rsn == RSN_POSITION:
                    self.batch += 1
                else:
                    self.batch = 0               # EXPIRED/FIFO mở batch mới
                    if rsn == RSN_EXPIRED:
                        self.counters["dl_expired"] += 1
                    else:
                        self.counters["dl_fifo"] += 1
            self.last = r[1]
            self.counters["dispatched"] += 1
            self.events.append(
                f"D pol={self.policy} rsn={rsn} seq={r[0]} blk={r[1]} hb={hb} "
                f"ha={self.head} db={db} da={self.dir} bat={self.batch} ep={self.epoch}")

    # -- switch ------------------------------------------------------------
    def switch(self, policy):
        q, inflight = len(self.queue), self.inflight()
        if policy not in POLICIES:
            rc = EINVAL
        elif policy == self.policy:
            rc = 0                               # no-op: không epoch/counter/event
        else:
            rc = 0
            hb = self.head
            if policy == SCAN:
                self.head = self.last if self.last is not None else 0
                self.dir = UP
            if policy == DL:
                self.batch = 0
            old, self.policy = self.policy, policy
            self.epoch += 1
            self.counters["policy_switches"] += 1
            self.events.append(
                f"S old={old} new={policy} hb={hb} ha={self.head} da={self.dir} "
                f"bat={self.batch} ep={self.epoch}")
        self.switches.append(f"SW pol={policy} rc={rc} q={q} i={inflight} ep={self.epoch}")
        return rc

    # -- run ---------------------------------------------------------------
    def add(self, block):
        self.seq += 1
        self.queue.append([self.seq, block, self.now])
        self.counters["enqueued"] += 1
        self.dispatch()

    def run(self, ops):
        for op, arg in ops:
            if op == "ADD":
                self.add(arg)
            elif op == "TICK":
                self.now = (self.now + arg) & M32
            elif op == "CAP":
                self.cap = arg
                self.dispatch()
            elif op == "DONE":
                if self.inflight() > 0:
                    self._complete()
            elif op == "SW":
                self.switch(arg)
            elif op == "DRAIN":
                self.cap = SLOTS
                self.dispatch()
                guard = 0
                while self.inflight() > 0 and guard < 100:
                    self._complete()
                    guard += 1
            else:  # pragma: no cover - fixture sai
                raise AssertionError(f"thao tác lạ: {op}")
        if self.queue:
            raise AssertionError("fixture không drain hết")
        return self


def expected_case(name, policy, clock0, ops):
    """Tính expected của một ca (events, SW record, snapshot, counters)."""
    sim = Sim(policy, clock0).run(ops)
    snap = {
        # request layer: mock không dùng pool/request API thật (D23)
        "S": 0, "C": 0, "E": 0, "R": 0, "Q": 0, "I": 0, "D": 0, "X": 0,
        "F": IO_NREQ,
        "eq": sim.counters["eagain"],
        "dlx": sim.counters["dl_expired"],
        "dlf": sim.counters["dl_fifo"],
        "sw": sim.counters["policy_switches"],
        "ep": sim.epoch,
        "batch": sim.batch,
        "last": sim.last if sim.last is not None else 0,
        "haslast": 0 if sim.last is None else 1,
        "bnd": sim.counters["boundary_events"],
        "ovf": 0,
        "fdesc": NUM_DESC,
        "lat_samples": 0, "wait_sum": 0, "wait_max": 0, "service_sum": 0,
        "service_max": 0, "total_sum": 0, "total_max": 0, "zero_total": 0,
    }
    return {"name": name, "events": sim.events, "switches": sim.switches,
            "snap": snap, "counters": sim.counters, "epoch": sim.epoch}


def expected():
    out = {}
    for name, policy, clock0, ops in I01_CASES:
        out[name] = expected_case(name, policy, clock0, ops)
    return out


def is_deadline_case(name):
    return name.startswith("i01-dl-")


def is_switch_case(name):
    return name.startswith("i01-sw-")


# ---------------------------------------------------------------------------
# Parser log QEMU (chỉ đọc output của hệ thống được kiểm, không dùng làm đáp án).
# ---------------------------------------------------------------------------
def parse_log(text):
    """Trả về ({case: {checks, events, switches, end_n, snap}}, done_fail, panic)."""
    import re

    text = text.replace("\r", "")
    cases, done_fail = {}, None
    panic = bool(re.search(r"(^|\n)panic:", text))
    for line in text.splitlines():
        if line.startswith("IOQI01 DONE fail="):
            done_fail = int(line.split("fail=", 1)[1].strip())
            continue
        m = re.match(r"^IOQI01 (\S+) (CHK|EV|SW|END|SNAP) (.*)$", line)
        if not m:
            continue
        name, kind, body = m.groups()
        c = cases.setdefault(name, {"checks": {}, "events": [], "switches": [],
                                    "end_n": None, "snap": None})
        if kind == "CHK":
            check, status = body.split(" ", 1)
            c["checks"][check] = status.strip()
        elif kind == "EV":
            c["events"].append(body.strip())
        elif kind == "SW":
            c["switches"].append("SW " + body.strip())
        elif kind == "END":
            c["end_n"] = int(body.split("n=", 1)[1].strip())
        elif kind == "SNAP":
            fields = {}
            for token in body.split():
                if "=" in token:
                    key, value = token.split("=", 1)
                    fields[key] = int(value)
            c["snap"] = fields
    return cases, done_fail, panic


def snapshot_errors(name, snap, exp_snap):
    """Kiểm snapshot: bất biến D23 + counters phải khớp expected của model."""
    errs = []
    ap = lambda key: snap.get(key)
    if ap("S") != ap("Q") + ap("I") + ap("C") + ap("E"):
        errs.append(f"{name}: snapshot S != Q+I+C+E")
    if ap("C") + ap("E") != ap("R") + ap("D") + ap("X"):
        errs.append(f"{name}: snapshot C+E != R+D+X")
    if IO_NREQ != ap("F") + ap("Q") + ap("I") + ap("D") + ap("X"):
        errs.append(f"{name}: snapshot pool balance != IO_NREQ")
    if ap("sw") != ap("ep"):
        errs.append(f"{name}: snapshot switch count != epoch")
    if ap("fdesc") > NUM_DESC:
        errs.append(f"{name}: snapshot descriptor free > NUM")
    for key in ("S", "C", "E", "R", "Q", "I", "D", "X", "F", "eq", "dlx", "dlf",
                "sw", "ep", "batch", "last", "haslast", "bnd", "ovf", "fdesc",
                "lat_samples", "wait_sum", "wait_max", "service_sum",
                "service_max", "total_sum", "total_max", "zero_total"):
        if ap(key) != exp_snap[key]:
            errs.append(f"{name}: SNAP {key}={ap(key)} expected {exp_snap[key]}")
    return errs


def coverage_errors(exp):
    """Tự kiểm fixture có phủ đủ ma trận D21/D22 (không phụ thuộc log)."""
    errs = []
    reasons = set()
    for item in exp.values():
        for event in item["events"]:
            if event.startswith("D "):
                reasons.add(int(event.split("rsn=")[1].split()[0]))
    for reason, label in ((RSN_EXPIRED, "EXPIRED"), (RSN_POSITION, "POSITION"),
                          (RSN_FIFO, "FIFO")):
        if reason not in reasons:
            errs.append(f"fixture thiếu reason {label}")
    switch_pairs = set()
    for item in exp.values():
        for event in item["events"]:
            if event.startswith("S "):
                old = int(event.split("old=")[1].split()[0])
                new = int(event.split("new=")[1].split()[0])
                switch_pairs.add((old, new))
    need = {(a, b) for a in POLICIES for b in POLICIES if a != b}
    if (need - {p for p in switch_pairs if p in need}):
        errs.append(f"fixture thiếu chiều switch: {sorted(need - switch_pairs)}")
    names = [item["name"] for item in exp.values()]
    for required in ("i01-dl-age-before", "i01-dl-age-at", "i01-dl-age-after",
                     "i01-dl-batch-boundary", "i01-dl-eagain", "i01-dl-wrap",
                     "i01-sw-keep-age", "i01-sw-noop-invalid", "i01-sw-batch-reset",
                     "i01-sw-scan-head"):
        if required not in names:
            errs.append(f"thiếu fixture {required}")
    return errs


if __name__ == "__main__":
    for item in expected().values():
        print(item["name"])
        for event in item["switches"] + item["events"]:
            print("   ", event)
        print("    SNAP", item["snap"])
    errors = coverage_errors(expected())
    print("coverage:", "OK" if not errors else errors)
