"""Điều khiển một phiên QEMU RISC-V cho xv6-riscv.

Lớp QemuSession được tests/runner.py dùng cho mọi test case:
  - build kernel/kernel + fs.img bằng `make`
  - boot qemu với -nographic, stdin/stdout nối vào pipe
  - gửi lệnh vào shell xv6, chờ pattern xuất hiện trên serial console
  - kill sạch cả process make lẫn qemu (cả process group)

Chỉ dùng thư viện chuẩn của Python 3, chạy trên Linux/WSL (không chạy trên
Windows trực tiếp vì cần os.killpg/selectors trên pipe).
"""

from __future__ import annotations

import os
import re
import selectors
import signal
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KERNEL = PROJECT_ROOT / "kernel" / "kernel"
FS_IMG = PROJECT_ROOT / "fs.img"

# xv6 in "init: starting sh" ngay trước khi shell sẵn sàng nhận lệnh.
BOOT_RE = re.compile(r"^init: starting sh", re.MULTILINE)
# Chỉ bắt panic thật của kernel; các dòng "usertrap" của usertests là hợp lệ.
PANIC_RE = re.compile(r"^(panic:|kernel panic)", re.MULTILINE)


class BuildError(RuntimeError):
    """Build `make` thất bại."""


class BootError(RuntimeError):
    """QEMU không boot được / thoát bất thường."""


class PanicDetected(AssertionError):
    """Kernel panic."""


class ExpectTimeout(AssertionError):
    """Không thấy pattern mong đợi trong thời gian cho phép."""


def _tail(text: str, lines: int = 25) -> str:
    parts = text.splitlines()[-lines:]
    return "\n".join(parts)


class QemuSession:
    """Một phiên QEMU + shell xv6.

    Cách dùng tối thiểu::

        with QemuSession(cpus=3).start() as q:
            q.send("echo hello")
            q.expect([r"^hello$"], timeout=10)
            print(q.raw)
    """

    def __init__(self, cpus: int = 3, fresh_fs: bool = True, verbose: bool = False):
        self.cpus = int(cpus)
        self.fresh_fs = bool(fresh_fs)
        self.verbose = bool(verbose)
        self._proc: subprocess.Popen | None = None
        self._buf = b""
        self._sel: selectors.BaseSelector | None = None
        self._eof = False
        self._last_read = time.monotonic()

    # -- build ------------------------------------------------------------
    def _make(self, targets: list[str], timeout: float = 600.0) -> None:
        cmd = ["make", "-s", *targets]
        try:
            p = subprocess.run(
                cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as e:
            raise BuildError(f"`{' '.join(cmd)}` quá {timeout}s") from e
        if p.returncode != 0:
            raise BuildError(
                f"`{' '.join(cmd)}` thất bại (exit {p.returncode}):\n"
                f"{p.stdout}{p.stderr}"
            )

    def build(self) -> None:
        if self.fresh_fs:
            FS_IMG.unlink(missing_ok=True)
        self._make(["kernel/kernel", "fs.img"])

    # -- vòng đời ---------------------------------------------------------
    def start(self, boot_timeout: float = 60.0) -> "QemuSession":
        self.build()
        cmd = ["make", "-s", "qemu", f"CPUS={self.cpus}"]
        self._proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            bufsize=0,
        )
        os.set_blocking(self._proc.stdout.fileno(), False)
        self._sel = selectors.DefaultSelector()
        self._sel.register(self._proc.stdout, selectors.EVENT_READ)
        try:
            self.wait_boot(boot_timeout)
        except BaseException:
            self.kill()
            raise
        return self

    def __enter__(self) -> "QemuSession":
        return self.start() if self._proc is None else self

    def __exit__(self, *exc) -> None:
        self.kill()

    @property
    def raw(self) -> str:
        return self._buf.decode("utf-8", "replace")

    # -- đọc serial -------------------------------------------------------
    def _pump(self, timeout: float) -> bool:
        """Đọc dữ liệu mới nếu có; trả về True nếu vừa đọc thêm."""
        got = False
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            remain = deadline - time.monotonic()
            if remain < 0 or self._eof:
                break
            events = self._sel.select(min(remain, 0.2))
            if not events:
                if got:
                    break
                continue
            for key, _ in events:
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                except OSError:
                    chunk = b""
                if not chunk:
                    # qemu/make đã thoát
                    self._eof = True
                    break
                self._buf += chunk
                got = True
        if got:
            self._last_read = time.monotonic()
        return got

    def _check_panic(self, since: int | None = None) -> None:
        text = self.raw if since is None else self.raw[since:]
        m = PANIC_RE.search(text)
        if m:
            raise PanicDetected(f"kernel panic: {m.group(0)}")

    def wait_boot(self, timeout: float = 60.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._pump(0.2)
            if self._proc.poll() is not None and not self._buf:
                raise BootError("qemu thoát trước khi boot xong")
            self._check_panic()
            if BOOT_RE.search(self.raw):
                return
        raise BootError(
            f"không thấy 'init: starting sh' sau {timeout}s\n--- serial ---\n"
            f"{_tail(self.raw, 40)}"
        )

    def expect(
        self,
        patterns: list[str] | str,
        timeout: float = 60.0,
        since: int | None = None,
        reject: list[str] | str = (),
    ) -> str:
        """Chờ tới khi TẤT CẢ regex trong `patterns` khớp phần serial mới.

        `since` là offset ký tự bắt đầu quét (mặc định quét toàn bộ output).
        `reject`: nếu khớp thì fail ngay (ví dụ '^FAILED').
        Trả về text đã quét.
        """
        if isinstance(patterns, str):
            patterns = [patterns]
        if isinstance(reject, str):
            reject = [reject]
        compiled = [re.compile(p, re.MULTILINE) for p in patterns]
        rejects = [re.compile(p, re.MULTILINE) for p in reject]
        deadline = time.monotonic() + timeout
        while True:
            text = self.raw if since is None else self.raw[since:]
            self._check_panic(since)
            for r in rejects:
                m = r.search(text)
                if m:
                    raise ExpectTimeout(f"gặp dòng bị cấm: {m.group(0)!r}")
            missing = [p for p, c in zip(patterns, compiled) if not c.search(text)]
            if not missing:
                return text
            if time.monotonic() > deadline:
                raise ExpectTimeout(
                    f"hết {timeout}s, còn thiếu: {missing}\n--- serial mới nhất ---\n"
                    f"{_tail(text, 40)}"
                )
            self._pump(0.2)

    def survive(self, seconds: float, reject: list[str] | str = ()) -> None:
        """Chạy tiếp `seconds` giây mà không panic/không khớp reject."""
        if isinstance(reject, str):
            reject = [reject]
        rejects = [re.compile(p, re.MULTILINE) for p in reject]
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self._pump(0.25)
            self._check_panic()
            for r in rejects:
                m = r.search(self.raw)
                if m:
                    raise ExpectTimeout(f"gặp dòng bị cấm: {m.group(0)!r}")
            if self._proc.poll() is not None:
                raise BootError("qemu thoát trong lúc đang chạy stress")
        self._pump(0.1)

    # -- điều khiển -------------------------------------------------------
    def send(self, line: str) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        data = line.encode()
        if not line.endswith("\n"):
            data += b"\n"
        self._proc.stdin.write(data)
        self._proc.stdin.flush()

    def sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self._pump(0.2)

    # -- dọn dẹp ----------------------------------------------------------
    def kill(self) -> None:
        proc = self._proc
        if proc is None:
            return
        self._proc = None
        try:
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if self._sel is not None:
            try:
                self._sel.close()
            except Exception:
                pass
            self._sel = None
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream:
                    stream.close()
            except Exception:
                pass
