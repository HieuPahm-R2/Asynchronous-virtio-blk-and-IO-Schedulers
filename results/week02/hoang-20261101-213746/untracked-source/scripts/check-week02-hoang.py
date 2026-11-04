#!/usr/bin/env python3
"""PTO-12/13/19: isolated real-DMA tests plus independent team selftests.

Never patches fs.img: fixture blocks are written only into disposable copies,
only after checking that mkfs marked every target block free. Flag transitions
always use make clean. Direct QEMU boots cannot silently rebuild without flags.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import signal
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
HW_CASES = [
    'T01 single-read', 'ARGS validation', 'T02 pool-exhaustion',
    'T03 stale-handle', 'T04 release-active', 'T05 complete-before-wait',
    'T06 real-used-gap', 'T07 descriptor-pressure-progress', 'T08 head-reuse',
    'T09 reversed-used-mapping', 'ERROR injected-status',
    'T10 submit-returns-pending', 'T12 stock-async-coexist',
    'T13 FCFS-real-dispatch', 'T11 accounting-10-cycles',
]


def output(cmd):
    return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(outdir, mode, flag=None):
    with (outdir / f'build-{mode}.log').open('w') as log:
        for cmd in (['make', 'clean'], ['make', '-j4', *([flag] if flag else []), 'kernel/kernel', 'fs.img']):
            log.write('$ ' + ' '.join(cmd) + '\n'); log.flush()
            subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    return {'kernel_sha256': sha(ROOT / 'kernel/kernel'), 'fs_sha256': sha(ROOT / 'fs.img')}


def fixture(image, corrupt=False):
    bs = 1024
    with image.open('r+b') as f:
        f.seek(bs)
        magic, size, _, _, _, _, _, bmap = struct.unpack('<8I', f.read(32))
        if magic != 0x10203040 or size != 2000:
            raise RuntimeError('unexpected superblock; refusing fixture')
        for block in range(size - 32, size):
            f.seek((bmap + block // (bs * 8)) * bs + (block % (bs * 8)) // 8)
            if f.read(1)[0] & (1 << (block % 8)):
                raise RuntimeError(f'fixture block {block} allocated; refusing overwrite')
        for block in range(size - 32, size):
            data = bytearray((block * 17 + i * 31 + (i >> 8) * 7) & 255 for i in range(bs))
            if corrupt and block == size - 32:
                data[0] ^= 1
            f.seek(block * bs); f.write(data)
    return {'blocks': [size - 32, size - 1], 'block_size': bs,
            'verified_free': True, 'corrupt_first_byte': corrupt, 'image_sha256': sha(image)}


def boot(logpath, cpus, hw=False, negative=False, timeout=60):
    with tempfile.TemporaryDirectory(prefix='hoang-virtio-') as temp:
        image = Path(temp) / 'fs.img'
        shutil.copyfile(ROOT / 'fs.img', image)
        info = fixture(image, negative) if hw else None
        cmd = ['qemu-system-riscv64', '-machine', 'virt', '-bios', 'none',
               '-kernel', 'kernel/kernel', '-m', '128M', '-smp', str(cpus), '-nographic',
               '-global', 'virtio-mmio.force-legacy=false',
               '-drive', f'file={image},if=none,format=raw,id=x0',
               '-device', 'virtio-blk-device,drive=x0,bus=virtio-mmio-bus.0']
        proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        sel = selectors.DefaultSelector(); sel.register(proc.stdout, selectors.EVENT_READ)
        start = time.monotonic(); data = bytearray(); reached_shell = False
        try:
            while time.monotonic() - start < timeout:
                for key, _ in sel.select(0.2):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        sel.unregister(key.fileobj)
                        break
                    data.extend(chunk)
                text = data.decode(errors='replace')
                if 'init: starting sh' in text:
                    reached_shell = True
                    break
                if re.search(r'(^|\n)panic:', text) or proc.poll() is not None:
                    break
        finally:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL); proc.communicate()
            except ProcessLookupError:
                proc.communicate()
            sel.close()
        text = data.decode(errors='replace').replace('\r', '')
        logpath.write_text(text)
        if not reached_shell or re.search(r'(^|\n)panic:', text):
            raise RuntimeError(f'boot/panic/timeout: {logpath}')
        return text, {'cpus': cpus, 'duration_s': round(time.monotonic()-start, 3),
                      'command': cmd, 'fixture': info, 'log': logpath.name}


def check_hw(text):
    errors = []
    for case in HW_CASES:
        if f'IO-HWTEST: {case} PASS' not in text:
            errors.append('missing ' + case)
    if 'IO-HWTEST: T13 seq=1,2,3,4,5\n' not in text:
        errors.append('FCFS host oracle')
    if 'IO-HWTEST: PASS failures=0' not in text or 'IO-USER-TEST: PASS (rc=0)' not in text:
        errors.append('overall PASS absent')
    if re.search(r'FAIL|panic:', text):
        errors.append('failure marker')
    line = re.search(r'IO-HWTEST: stats (.*)', text)
    stats = dict((k, int(v)) for k,v in re.findall(r'(\w+)=(\d+)', line[1])) if line else {}
    for key, value in {'free_req':16, 'free_desc':8, 'max_inflight':2, 'errors':2}.items():
        if stats.get(key) != value:
            errors.append(f'{key} != {value}')
    if not (stats.get('submitted') == stats.get('completed', -1) + stats.get('errors', -2)
            == stats.get('released') == stats.get('async')):
        errors.append('terminal/released accounting')
    return errors, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repeat', type=int, default=10)
    ap.add_argument('--hw-only', action='store_true', help='skip independent pool/queue suites')
    ap.add_argument('--results-dir', type=Path)
    args = ap.parse_args()
    if args.repeat < 1: ap.error('--repeat must be >= 1')
    stamp = dt.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')
    outdir = (args.results_dir or ROOT / 'results/week02' / ('hoang-' + stamp)).resolve()
    outdir.mkdir(parents=True, exist_ok=False)
    source_paths = sorted([ROOT/'Makefile', *ROOT.glob('kernel/*.[ch]'), *ROOT.glob('user/*.[ch]'),
                           Path(__file__), ROOT/'mk/project.mk', *ROOT.glob('tests/cases/*.py')])
    meta = {'started_at': dt.datetime.now().astimezone().isoformat(), 'host': platform.platform(),
            'head': output(['git','rev-parse','HEAD']), 'branch': output(['git','branch','--show-current']),
            'dirty': output(['git','status','--porcelain']), 'repeat': args.repeat,
            'versions': {exe:output([exe,'--version']).splitlines()[0] for exe in
                         ['qemu-system-riscv64','riscv64-unknown-elf-gcc','make']},
            'source_sha256': {str(p.relative_to(ROOT)):sha(p) for p in source_paths},
            'builds': {}, 'runs': []}
    (outdir/'source.patch').write_text(output(['git','diff','--binary','HEAD'])+'\n')
    # Keep untracked source as well: git diff alone cannot reproduce it.
    (outdir/'untracked-source').mkdir()
    for rel in output(['git','ls-files','--others','--exclude-standard']).splitlines():
        p = ROOT/rel
        if p.is_file() and (rel.startswith('kernel/') or rel.startswith('scripts/')):
            target = outdir/'untracked-source'/rel; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p,target)
    error = None
    try:
        meta['builds']['hardware'] = build(outdir, 'hardware', 'IO_HW_SELFTEST=1')
        for cpus in (1,4):
            for i in range(args.repeat):
                text, record = boot(outdir/f'hw-cpus{cpus}-{i+1:02}.log', cpus, hw=True)
                errs, stats = check_hw(text)
                record.update(mode='real-virtio', status='FAIL' if errs else 'PASS', errors=errs, stats=stats)
                meta['runs'].append(record)
                print(f"real-virtio cpus={cpus} run={i+1}: {record['status']}", flush=True)
                if errs: raise RuntimeError('; '.join(errs))
        text, record = boot(outdir/'negative-corrupt-fixture.log', 1, hw=True, negative=True)
        errs, stats = check_hw(text)
        if not errs or 'IO-HWTEST: FAIL 1024-byte fixture pattern' not in text:
            raise RuntimeError('negative control failed to detect corrupted fixture')
        record.update(mode='negative-control', status='EXPECTED_FAIL', errors=errs, stats=stats)
        meta['runs'].append(record)
        print('corrupt-fixture oracle: EXPECTED_FAIL', flush=True)
        if not args.hw_only:
            meta['builds']['pool'] = build(outdir, 'pool', 'IO_SELFTEST=1')
            for cpus in (1,4):
                text, record = boot(outdir/f'pool-cpus{cpus}.log',cpus)
                if ('IO-SELFTEST: PASS (T02/T03/T04/T11, failures=0)' not in text or
                    'IO-SELFTEST: USER PASS (T03/T04/T05/T06, failures=0)' not in text or
                    'IO-USER-TEST: PASS (rc=0)' not in text or 'FAIL' in text):
                    raise RuntimeError('pool mock/timer suite failed')
                record.update(mode='pool-mock-timer', status='PASS'); meta['runs'].append(record)
                print(f'pool mock/timer cpus={cpus}: PASS',flush=True)
            meta['builds']['queue'] = build(outdir, 'queue', 'EXTRA_CFLAGS=-DIOQ_SELFTEST')
            spec = importlib.util.spec_from_file_location('fcfs_oracle', ROOT/'tests/cases/ioq_fcfs.py')
            oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
            for cpus in (1,4):
                text, record = boot(outdir/f'queue-cpus{cpus}.log',cpus)
                if any(not re.search(p,text,re.M) for p in oracle.CASES[0]['expect']) or 'FAIL' in text:
                    raise RuntimeError('independent queue oracle failed')
                record.update(mode='queue-mock', status='PASS'); meta['runs'].append(record)
                print(f'queue mock cpus={cpus}: PASS',flush=True)
    except Exception as exc:
        error = str(exc); meta['error'] = error
    finally:
        try:
            meta['builds']['production'] = build(outdir, 'production')
            nm = output(['riscv64-unknown-elf-nm','kernel/kernel'])
            hooks = re.findall(r'\b(?:virtio_test_\w+|io_hw_selftest|io_hw_set_wait_hook|io_test_timer_tick)\b',nm)
            if hooks: raise RuntimeError('test hooks leaked into production: '+str(hooks))
            meta['production_hooks_absent'] = True
        except Exception as exc:
            error = str(exc); meta['error'] = error
        meta['finished_at'] = dt.datetime.now().astimezone().isoformat()
        meta['status'] = 'FAIL' if error else 'PASS'
        (outdir/'meta.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n')
        (outdir/'summary.md').write_text('# Hoàng week 02 verification\n\n' +
          f"Status: {meta['status']}\n\n" + '\n'.join(f"- {r['mode']} CPUS={r['cpus']}: {r['status']} ({r['log']})" for r in meta['runs']) +
          '\n\nNegative control is intentionally corrupt; mock/timer tests are not hardware evidence.\n' +
          (f'\nError: {error}\n' if error else ''))
        print(f"{meta['status']}: {outdir}",flush=True)
    return 1 if error else 0

if __name__ == '__main__':
    raise SystemExit(main())
