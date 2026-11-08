#!/usr/bin/env python3
"""W3-H02: Multi-producer async READ stress harness with full 1024-byte verification.

Runs >= 2 real user processes (4 forked workers in init under -DIO_STRESS_SELFTEST),
each performing 120 real virtio-blk READs (480 READs total per boot) across the
32 verified-free fixture blocks on CPUS=1 and CPUS=4. Verifies pool exhaustion
recovery, watchdog non-hang, full 1024-byte block pattern, post-drain resource
invariants (16 slots, 8 descriptors, Q=I=D=X=0), 1-byte corrupt fixture negative
control, and clean production restore with zero leaked test symbols.
"""
from __future__ import annotations
import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import platform
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('check_w2', ROOT / 'scripts/check-week02-hoang.py')
check_w2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_w2)

resolve_toolchain = check_w2.resolve_toolchain
build = check_w2.build
boot = check_w2.boot
output = check_w2.output
HOOK_REGEX = check_w2.HOOK_REGEX
KERNEL_ELF = check_w2.KERNEL_ELF

WORKER_RE = re.compile(
    r'IO-STRESS: worker=(\d+) pid=(\d+) submitted=(\d+) completed=(\d+) '
    r'eagain_pool=(\d+) poll_hits=(\d+) data_err=(\d+) watchdog=(\d+) fail=(\d+) '
    r'first=(\d+)/(-?\d+)/(\d+)/(\d+) last=(\d+)/(-?\d+)/(\d+)/(\d+) hash=(0x[0-9a-fA-F]+)'
)


def _parse_workers(text: str) -> dict[int, dict]:
    workers: dict[int, dict] = {}
    for m in WORKER_RE.finditer(text):
        wid = int(m.group(1))
        workers[wid] = {
            'worker': wid,
            'pid': int(m.group(2)),
            'submitted': int(m.group(3)),
            'completed': int(m.group(4)),
            'eagain_pool': int(m.group(5)),
            'poll_hits': int(m.group(6)),
            'data_err': int(m.group(7)),
            'watchdog': int(m.group(8)),
            'fail': int(m.group(9)),
            'first': {
                'worker': int(m.group(10)),
                'id': int(m.group(11)),
                'gen': int(m.group(12)),
                'block': int(m.group(13)),
            },
            'last': {
                'worker': int(m.group(14)),
                'id': int(m.group(15)),
                'gen': int(m.group(16)),
                'block': int(m.group(17)),
            },
            'hash': m.group(18),
        }
    return workers


def _validate_worker_entry(wid: int, winfo: dict, min_reads: int) -> list[str]:
    errs: list[str] = []
    if winfo['completed'] < min_reads or winfo['submitted'] != winfo['completed']:
        errs.append(f"worker {wid} incomplete reads ({winfo['submitted']}/{winfo['completed']})")
    if winfo['data_err'] != 0 or winfo['watchdog'] != 0 or winfo['fail'] != 0:
        errs.append(f"worker {wid} error/watchdog/fail")
    if not (0 <= winfo['first']['id'] < 16 and winfo['first']['gen'] >= 1):
        errs.append(f"worker {wid} invalid first handle")
    if not (0 <= winfo['last']['id'] < 16 and winfo['last']['gen'] >= 1):
        errs.append(f"worker {wid} invalid last handle")
    return errs


def _validate_stats_dict(stats: dict[str, int], expected_workers: int, total_expected: int) -> list[str]:
    if not stats:
        return ['missing global IO-STRESS stats line']
    errs: list[str] = []
    expected_map = {
        'workers': expected_workers,
        'total_reads': total_expected,
        'free_req': 16,
        'free_desc': 8,
        'queued': 0,
        'inflight': 0,
        'done': 0,
        'error': 0,
        'errors': 0,
        'data_errors': 0,
        'max_inflight': 2,
    }
    for k, v in expected_map.items():
        if stats.get(k) != v:
            errs.append(f'{k}={stats.get(k)} != {v}')
    if not (
        stats.get('submitted')
        == stats.get('completed', -1) + stats.get('errors', -2)
        == stats.get('released')
        == stats.get('q_enqueued')
        == stats.get('q_dispatched')
    ):
        errs.append('cumulative accounting mismatch after drain')
    if stats.get('eagain_pool', 0) <= 0:
        errs.append('eagain_pool == 0 (pool contention not exercised)')
    return errs


def check_stress_output(text: str, expected_workers: int = 4, min_reads_per_worker: int = 100):
    errors: list[str] = []
    workers = _parse_workers(text)
    if len(workers) != expected_workers:
        errors.append(f'expected {expected_workers} workers, saw {len(workers)}')

    pids = {winfo['pid'] for winfo in workers.values()}
    for wid, winfo in sorted(workers.items()):
        errors.extend(_validate_worker_entry(wid, winfo, min_reads_per_worker))
    if len(pids) != len(workers):
        errors.append('worker PIDs are not distinct processes')

    stats_lines = [ln for ln in text.splitlines() if ln.startswith('IO-STRESS: stats ')]
    stats = {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', stats_lines[-1])} if stats_lines else {}
    total_expected = sum(w['completed'] for w in workers.values())
    errors.extend(_validate_stats_dict(stats, expected_workers, total_expected))

    if 'IO-STRESS: PASS failures=0' not in text or 'IO-USER-TEST: PASS (rc=0)' not in text:
        errors.append('missing overall PASS marker')
    if re.search(r'IO-STRESS: FAIL|panic:', text):
        errors.append('failure/panic marker present')

    return errors, stats, workers


def _run_stress_matrix(outdir: Path, tc: dict, args, meta: dict) -> None:
    stress_flags = ['IO_STRESS_SELFTEST=1', f'EXTRA_CFLAGS=-DIO_STRESS_SEED={hex(args.seed)}U']
    meta['builds']['stress'] = build(outdir, 'stress', tc, stress_flags)
    for cpus in (1, 4):
        for i in range(args.repeat):
            logpath = outdir / f'stress-cpus{cpus}-{i+1:02}.log'
            text, record = boot(logpath, cpus, hw=True, negative=False, timeout=args.timeout)
            errs, stats, workers = check_stress_output(text)
            record.update(
                mode='stress-multi-producer',
                status='FAIL' if errs else 'PASS',
                errors=errs,
                stats=stats,
                workers=workers,
            )
            meta['runs'].append(record)
            print(f"stress-multi-producer cpus={cpus} run={i+1}: {record['status']}", flush=True)
            if errs:
                raise RuntimeError('; '.join(errs))

    neg_log = outdir / 'negative-corrupt-fixture.log'
    text, record = boot(neg_log, 4, hw=True, negative=True, timeout=args.timeout)
    errs, stats, workers = check_stress_output(text)
    if not errs or 'IO-STRESS: FAIL 1024-byte fixture pattern' not in text:
        raise RuntimeError('negative control failed to detect 1-byte corrupted fixture in stress test')
    record.update(
        mode='negative-control-1byte',
        status='EXPECTED_FAIL',
        errors=errs,
        stats=stats,
        workers=workers,
    )
    meta['runs'].append(record)
    print('stress negative-control (1-byte corrupt fixture): EXPECTED_FAIL', flush=True)


def _restore_production(outdir: Path, tc: dict, meta: dict) -> None:
    meta['builds']['production'] = build(outdir, 'production', tc)
    nm = output([tc['nm'], KERNEL_ELF])
    hooks = re.findall(HOOK_REGEX, nm)
    if hooks:
        raise RuntimeError('test hooks leaked into production: ' + str(hooks))
    meta['production_hooks_absent'] = True
    smoke_log = outdir / 'production-smoke.log'
    _, smoke_rec = boot(smoke_log, 1, hw=False, negative=False, timeout=30)
    smoke_rec.update(mode='production-restore-smoke', status='PASS')
    meta['runs'].append(smoke_rec)
    print('production restore + smoke: PASS', flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repeat', type=int, default=2, help='runs per CPU config (default: 2)')
    ap.add_argument('--seed', type=lambda s: int(s, 0), default=0x26128003,
                    help='deterministic fixture block sequence seed (default: 0x26128003)')
    ap.add_argument('--timeout', type=int, default=60, help='watchdog timeout in seconds per boot')
    ap.add_argument('--toolprefix', type=str, default=None, help='RISC-V toolchain prefix')
    ap.add_argument('--results-dir', type=Path, default=None)
    args = ap.parse_args()
    if args.repeat < 1:
        ap.error('--repeat must be >= 1')

    try:
        tc = resolve_toolchain(args.toolprefix)
    except RuntimeError as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        return 2

    stamp = dt.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')
    outdir = (args.results_dir or ROOT / 'results/week03/stress' / f'hoang-{stamp}').resolve()
    outdir.mkdir(parents=True, exist_ok=False)

    xv6_pin = (ROOT / '.xv6-commit').read_text().strip() if (ROOT / '.xv6-commit').is_file() else 'unknown'
    meta = {
        'started_at': dt.datetime.now().astimezone().isoformat(),
        'host': platform.platform(),
        'head': output(['git', 'rev-parse', 'HEAD']),
        'branch': output(['git', 'branch', '--show-current']),
        'xv6_pin': xv6_pin,
        'dirty': output(['git', 'status', '--porcelain']),
        'repeat': args.repeat,
        'seed': hex(args.seed),
        'timeout_s': args.timeout,
        'toolchain': tc,
        'versions': {
            exe: output([exe, '--version']).splitlines()[0]
            for exe in ['qemu-system-riscv64', tc['cc'], tc['nm'], 'make']
        },
        'builds': {},
        'runs': [],
    }

    error = None
    try:
        _run_stress_matrix(outdir, tc, args, meta)
    except Exception as exc:
        error = str(exc)
        meta['error'] = error
    finally:
        try:
            _restore_production(outdir, tc, meta)
        except Exception as exc:
            error = str(exc)
            meta['error'] = error
        meta['finished_at'] = dt.datetime.now().astimezone().isoformat()
        meta['status'] = 'FAIL' if error else 'PASS'
        (outdir / 'meta.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n')
        (outdir / 'summary.md').write_text(
            '# W3-H02 Multi-producer async READ stress verification\n\n'
            + f"- Status: **{meta['status']}**\n"
            + f"- HEAD: `{meta['head']}` (`{meta['branch']}`)\n"
            + f"- Seed: `{meta['seed']}`\n"
            + f"- Toolchain: `{tc['toolprefix']}` (`{tc['cc_realpath']}`)\n"
            + f"- Production hooks absent: `{meta.get('production_hooks_absent', False)}`\n\n"
            + '## Runs\n\n'
            + '\n'.join(f"- {r['mode']} CPUS={r['cpus']}: **{r['status']}** (`{r['log']}`)" for r in meta['runs'])
            + '\n'
            + (f'\nError: {error}\n' if error else '')
        )
        print(f"{meta['status']}: {outdir}", flush=True)
    return 1 if error else 0


if __name__ == '__main__':
    raise SystemExit(main())
