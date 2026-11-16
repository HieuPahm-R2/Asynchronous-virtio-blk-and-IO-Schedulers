#!/usr/bin/env python3
"""W4-H01/H02: real READ policies and four-producer loaded policy switching.

Each scenario uses an isolated, verified-free fixture image. Builds are serial
and clean across flags. --repeat applies to stress boots per CPU; the real
policy matrix (10 scenarios/boot) runs once per CPU, including a real expiry.
Always restore production and check absence of test hooks, even after failure.
"""
from __future__ import annotations
import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import platform
import re
import shutil
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = load('w4_hardware', 'scripts/check-week02-hoang.py')
S = load('w4_stress', 'scripts/check-week03-stress.py')
R = load('w4_real_oracle', 'tests/cases/io_real_policy.py')
HOOKS = H.HOOK_REGEX + r'|\b(?:io_policy_hw_selftest|ioq_hw_trace_reset_locked_for_test)\b'
TARGETS = [1, 2, 1, 0, 2, 0]


def check_switch_stress(text):
    errors, stats, workers = S.check_stress_output(text)
    transitions = re.findall(r'^IO-SWITCH: phase=(\d+) old=(\d+) new=(\d+) q=(\d+) i=(\d+) ep=(\d+) begin_disp=(\d+)$', text, re.M)
    ends = re.findall(r'^IO-SWITCH: phase=(\d+) END reads=(\d+) selected=(\d+) pol=(\d+) ep=(\d+)$', text, re.M)
    if len(transitions) != 6 or len(ends) != 6:
        errors.append('need exactly six loaded switch phases and drain records')
    old = 0
    for phase, row in enumerate(transitions):
        number, source, target, queued, inflight, epoch, dispatched = map(int, row)
        if phase >= 6 or (number, source, target, inflight, epoch, dispatched) != (
                phase, old, TARGETS[phase], 2, phase + 1, phase * 80 + 2) or queued <= 0:
            errors.append(f'phase {phase}: incorrect loaded transition {row}')
        old = target
    for phase, row in enumerate(ends):
        if phase >= 6 or tuple(map(int, row)) != (phase, 80, 78, TARGETS[phase], phase + 1):
            errors.append(f'phase {phase}: no verified dispatch under target policy {row}')
    if len(re.findall(r'^IO-SWITCH: DONE phases=6 fail=0$', text, re.M)) != 1:
        errors.append('missing unique controller completion')
    if 'IO-SWITCH: FAIL' in text:
        errors.append('controller failed')
    return errors, stats, workers


def capture_source(outdir, meta):
    meta['head'] = H.output(['git', 'rev-parse', 'HEAD'])
    meta['branch'] = H.output(['git', 'branch', '--show-current'])
    meta['dirty'] = H.output(['git', 'status', '--porcelain'])
    meta['xv6_pin'] = (ROOT / '.xv6-commit').read_text().strip()
    paths = sorted([ROOT / 'Makefile', ROOT / 'mk/project.mk',
                    *ROOT.glob('kernel/*.[ch]'), *ROOT.glob('user/*.[ch]'),
                    *ROOT.glob('scripts/*.py'), *ROOT.glob('tests/cases/*.py')])
    meta['source_sha256'] = {str(p.relative_to(ROOT)): H.sha(p) for p in paths}
    (outdir / 'source.patch').write_text(H.output(['git', 'diff', '--binary', 'HEAD']) + '\n')
    for name in H.output(['git', 'ls-files', '--others', '--exclude-standard']).splitlines():
        source = ROOT / name
        if source.is_file() and name.startswith(('kernel/', 'scripts/', 'tests/')):
            target = outdir / 'untracked-source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def run_boot(outdir, meta, stem, cpus, checker, negative=False):
    path = outdir / f'{stem}-cpus{cpus}.log'
    text, record = H.boot(path, cpus, hw=True, negative=negative, timeout=90)
    result = checker(text)
    errs = result[0] if isinstance(result, tuple) else result
    if negative:
        caught = bool(errs) and 'FAIL 1024-byte fixture pattern' in text
        status = 'EXPECTED_FAIL' if caught else 'FAIL'
        if not caught:
            errs = ['negative control did not detect the corrupted fixture byte'] + errs
    else:
        status = 'FAIL' if errs else 'PASS'
    record.update(mode=stem, status=status, errors=errs)
    if isinstance(result, tuple):
        record.update(stats=result[1], workers=result[2])
    meta['runs'].append(record)
    print(f'{stem} CPU{cpus}: {status}', flush=True)
    if status == 'FAIL':
        raise RuntimeError('; '.join(errs[:4]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=['all', 'real', 'stress'], default='all')
    ap.add_argument('--repeat', type=int, default=5)
    ap.add_argument('--cpus', nargs='+', type=int, choices=[1, 4], default=[1, 4])
    ap.add_argument('--toolprefix')
    ap.add_argument('--results-dir', type=Path)
    args = ap.parse_args()
    if args.repeat < 1 or len(set(args.cpus)) != len(args.cpus):
        ap.error('repeat must be positive and CPUs must be unique')
    try:
        tc = H.resolve_toolchain(args.toolprefix)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    stamp = dt.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')
    outdir = (args.results_dir or ROOT / 'results/week04/hoang' / f'{socket.gethostname()}-{stamp}').resolve()
    outdir.mkdir(parents=True, exist_ok=False)
    meta = {'started_at': dt.datetime.now().astimezone().isoformat(),
            'machine': socket.gethostname(), 'host': platform.platform(),
            'arguments': vars(args) | {'results_dir': str(outdir)},
            'toolchain': tc, 'versions': {x: H.output([x, '--version']).splitlines()[0]
                                        for x in [tc['cc'], tc['nm'], 'qemu-system-riscv64', 'make']},
            'expiry_ticks': 50, 'batch_limit': 4, 'seed': '0x26128003',
            'builds': {}, 'runs': []}
    capture_source(outdir, meta)
    errors = []
    try:
        if args.mode in ('all', 'real'):
            meta['builds']['real'] = H.build(outdir, 'real', tc,
                ['IO_HW_SELFTEST=1', 'EXTRA_CFLAGS=-DIO_POLICY_HW_SELFTEST'])
            for cpus in args.cpus:
                run_boot(outdir, meta, 'real-policy', cpus, R.check)
            run_boot(outdir, meta, 'real-negative', args.cpus[-1], R.check, True)
        if args.mode in ('all', 'stress'):
            meta['builds']['stress'] = H.build(outdir, 'stress', tc,
                ['IO_STRESS_SELFTEST=1', 'EXTRA_CFLAGS=-DIO_POLICY_STRESS_SELFTEST'])
            for cpus in args.cpus:
                for repeat in range(args.repeat):
                    run_boot(outdir, meta, f'switch-stress-{repeat + 1:02}', cpus, check_switch_stress)
            run_boot(outdir, meta, 'stress-negative', args.cpus[-1], check_switch_stress, True)
    except Exception as exc:
        errors.append(str(exc))
        print('ERROR:', exc, flush=True)
    finally:
        try:
            meta['builds']['production'] = H.build(outdir, 'production', tc)
            symbols = H.output([tc['nm'], H.KERNEL_ELF])
            leaked = re.findall(HOOKS, symbols)
            if leaked:
                raise RuntimeError('production test hooks leaked: ' + str(leaked))
            meta['production_hooks_absent'] = True
            _, record = H.boot(outdir / 'production-smoke.log', 1)
            record.update(mode='production-restore-smoke', status='PASS')
            meta['runs'].append(record)
        except Exception as exc:
            errors.append('restore: ' + str(exc))
        meta.update(status='FAIL' if errors else 'PASS', errors=errors,
                    finished_at=dt.datetime.now().astimezone().isoformat())
        (outdir / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
        summary = ['# W4-H01/H02 real policy and loaded switch verification', '',
                   f'- Status: {meta["status"]}', f'- HEAD: `{meta["head"]}`',
                   f'- Dirty/source snapshot: {bool(meta["dirty"])} (see meta.json/source.patch)',
                   '- Real device: QEMU virtio-blk READ; tick is not physical seek latency.', '']
        summary += [f'- {r["mode"]} CPUS={r["cpus"]}: {r["status"]}' for r in meta['runs']]
        summary += ['', '## Errors', *errors] if errors else []
        (outdir / 'summary.md').write_text('\n'.join(summary) + '\n')
        print(meta['status'] + ': ' + str(outdir), flush=True)
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
