#!/usr/bin/env python3
"""PTO-41: verify one real virtio used entry per merged command on QEMU."""
import argparse
import json
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]
H = runpy.run_path(str(ROOT / 'scripts/check-week02-hoang.py'))
MERGE_SYMBOLS = r'\b(?:virtio_disk_try_submit_merged_read|\w*merge_selftest|\w*merge_test_\w+)\b'
CASES = (
    r'read children=2 reverse=0 published=1 used=1 head=\d+ PASS',
    r'read children=3 reverse=1 published=1 used=1 head=\d+ PASS',
    r'read children=4 reverse=1 published=1 used=1 head=\d+ PASS',
    r'injected-EIO children=4 reverse=0 published=1 used=1 head=\d+ PASS',
    r'device-EIO children=4 reverse=0 published=1 used=1 head=\d+ PASS',
    r'bounce-pressure EAGAIN retry=OK PASS',
    r'descriptor-pressure EAGAIN retry=OK PASS',
    r'gap duplicate EINVAL recovery=OK PASS',
)
SUCCESS_BLOCKS = [
    1968, 1969, 1972, 1971, 1970, 1976, 1975, 1974, 1973,
    1984, 1985, 1986, 1987, 1989, 1988,
    1984, 1986, 1989, 1988, 1992, 1993,
]


def verify_serial(serial):
    for case in CASES:
        if len(re.findall(rf'^IO-MERGE: {case}$', serial, flags=re.M)) != 1:
            raise RuntimeError(f'missing or repeated case: {case}')

    expected = []
    for block in SUCCESS_BLOCKS:
        checksum = 2166136261
        for i in range(1024):
            byte = (block * 17 + i * 31 + (i // 256) * 7) % 256
            checksum = ((checksum ^ byte) * 16777619) % (1 << 32)
        expected.append((block, 1024, checksum))
    children = re.findall(r'^IO-MERGE: child block=(\d+) bytes=(\d+) fnv1a=([0-9a-fA-F]+)$',
                          serial, flags=re.M)
    actual = [(int(block), int(length), int(checksum, 16))
              for block, length, checksum in children]
    if actual != expected:
        raise RuntimeError('serial child sequence or checksum mismatch')
    for line in (
        'IO-MERGE: drain done=21 error=8 released=29 free_req=16 free_desc=8 free_bounce=2',
        'IO-MERGE: PASS',
        'IO-USER-TEST: PASS (rc=0)',
    ):
        if line not in serial.splitlines():
            raise RuntimeError(f'missing: {line}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, required=True)
    parser.add_argument('--toolprefix')
    args = parser.parse_args()
    out = args.outdir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tc = H['resolve_toolchain'](args.toolprefix)
    qemu = H['output'](['qemu-system-riscv64', '--version']).splitlines()[0]
    gcc = H['output']([tc['cc'], '--version']).splitlines()[0]
    evidence = {
        'source_commit': H['output'](['git', 'rev-parse', 'HEAD']),
        'source_tree_dirty': bool(H['output'](['git', 'status', '--porcelain'])),
        'qemu': qemu, 'gcc': gcc, 'boots': [],
    }
    source_image = ROOT / H['FS_IMG']

    try:
        evidence['test_build'] = H['build'](out, 'merge', tc, 'IO_MERGE_SELFTEST=1')
        for cpus in (1, 4):
            serial, boot = H['boot'](out / f'merge-cpu{cpus}.log', cpus,
                                     hw=True, trim_tail_blocks=4)
            verify_serial(serial)
            evidence['boots'].append(boot)
            print(f'PTO-41: {cpus} vCPU, 8 cases and 21 child checksums PASS')
        if H['sha'](source_image) != evidence['test_build']['fs_sha256']:
            raise RuntimeError('original fs.img changed')
        evidence['backend_build'] = H['build'](out, 'backend', tc, 'IO_MERGE_READ=1')
        symbols = H['output']([tc['nm'], 'kernel/kernel'])
        if ('virtio_disk_try_submit_merged_read' not in symbols or
                re.search(r'\b\w*merge_(?:selftest|test_\w+)\b|' + H['HOOK_REGEX'], symbols)):
            raise RuntimeError('backend-only build has missing backend or test hooks')
        serial, boot = H['boot'](out / 'backend-cpu3.log', 3)
        if 'IO-MERGE:' in serial or 'IO-USER-TEST:' in serial:
            raise RuntimeError('merge selftest ran in backend-only build')
        evidence['backend_boot'] = boot
        print('PTO-41: backend-only kernel boots and excludes test hooks')
    finally:
        evidence['production_build'] = H['build'](out, 'production', tc)
        symbols = H['output']([tc['nm'], 'kernel/kernel'])
        if re.search(MERGE_SYMBOLS + '|' + H['HOOK_REGEX'], symbols):
            raise RuntimeError('merge backend or test hooks leaked into default kernel')

    serial, boot = H['boot'](out / 'production-cpu3.log', 3)
    if 'IO-MERGE:' in serial or 'IO-USER-TEST:' in serial:
        raise RuntimeError('merge selftest ran in default build')
    evidence['production_boot'] = boot
    evidence['status'] = 'PASS'
    (out / 'manifest.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('PTO-41: default kernel boots and excludes merge backend and test hooks')


if __name__ == '__main__':
    main()
