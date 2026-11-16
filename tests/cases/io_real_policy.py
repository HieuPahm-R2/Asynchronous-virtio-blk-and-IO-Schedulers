"""W4-H01: check real-DMA traces against Hieu's independent contract model.

The measured pre-switch state and request arrivals are inputs, not expected
output. No completion order or kernel-selected candidate is used as an oracle.
The bounded fixture guarantees either all young or all expired through drain.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ioq_w4_model as M

SCENARIOS = [(p, p, 0) for p in M.POLICIES]
SCENARIOS += [(a, b, 0) for a in M.POLICIES for b in M.POLICIES if a != b]
SCENARIOS += [(M.DL, M.DL, 1)]


def values(text):
    return {key: int(value) for key, value in re.findall(r'(\w+)=(-?\d+)', text)}


def check(text):
    errors, cases = [], {}
    for line in text.splitlines():
        match = re.fullmatch(r'IO-REAL: case=(\d+) (INIT|INPUT|EV|END) (.+)', line)
        if not match:
            continue
        number, kind, body = int(match[1]), match[2], match[3]
        case = cases.setdefault(number, {'inputs': [], 'events': []})
        if kind in ('INIT', 'END'):
            if kind in case:
                errors.append(f'case {number}: duplicate {kind}')
            case[kind] = values(body)
        elif kind == 'INPUT':
            case['inputs'].append(values(body))
        else:
            case['events'].append(body)
    if set(cases) != set(range(len(SCENARIOS))):
        errors.append('missing/extra real-DMA cases')
    if len(re.findall(r'^IO-REAL: DONE cases=10 fail=0$', text, re.M)) != 1:
        errors.append('missing unique successful DONE marker')
    if 'IO-USER-TEST: PASS (rc=0)' not in text or re.search(r'FAIL|panic:', text):
        errors.append('failure/panic/missing user PASS')
    for number, (source, target, expired) in enumerate(SCENARIOS):
        try:
            case = cases[number]
            initial, end, inputs = case['INIT'], case['END'], case['inputs']
            if (initial['src'], initial['dst'], initial['expired']) != (source, target, expired):
                raise ValueError('incorrect scenario parameters')
            if initial['pol'] != source or initial['q'] != 5 or initial['i'] != 2:
                raise ValueError('must switch with two real INFLIGHT and five QUEUED')
            if initial['has'] != 1 or initial['last'] != 1979:
                raise ValueError('last dispatch must be the second anchor block')
            if source == M.SCAN and (initial['head'], initial['dir']) != (1979, M.UP):
                raise ValueError('SCAN anchor state is incorrect')
            if len(inputs) != 5 or len({r['seq'] for r in inputs}) != 5:
                raise ValueError('need five distinct input requests')
            if [r['blk'] for r in inputs] != [1996, 1970, 1988, 1968, 1983]:
                raise ValueError('fixture input blocks do not match published workload')
            ages_start = [M.signed_age(initial['tick'], r['tick']) for r in inputs]
            ages_end = [M.signed_age(end['tick'], r['tick']) for r in inputs]
            if min(ages_start) < 0 or (expired and min(ages_start) < M.EXPIRE):
                raise ValueError('expired fixture was not old enough')
            if not expired and max(ages_end) >= M.EXPIRE:
                raise ValueError('young fixture crossed expiry; no deterministic oracle claim')
            sim = M.Sim(source, initial['tick'])
            sim.head, sim.dir, sim.batch = initial['head'], initial['dir'], initial['bat']
            sim.epoch = initial['ep']
            sim.last = initial['last'] if initial['has'] else None
            sim.queue = [[r['seq'], r['blk'], r['tick']] for r in inputs]
            sim.switch(target)
            sim.dispatch()
            while sim.queue or sim.inflight():
                sim._complete()
            if case['events'] != sim.events:
                errors.append(f'case {number}: dispatch/state/epoch mismatch; expected={sim.events}; actual={case["events"]}')
            accepted = (number + 1) * 7
            expected = {'S': accepted, 'C': accepted, 'E': 0, 'R': accepted,
                        'F': 16, 'fd': 8, 'ovf': 0, 'n': len(sim.events), 'fail': 0}
            for key, value in expected.items():
                if end.get(key) != value:
                    errors.append(f'case {number}: {key}={end.get(key)}, expected {value}')
        except (KeyError, ValueError, TypeError) as exc:
            errors.append(f'case {number}: {exc}')
    return errors


if __name__ == '__main__':
    errs = check(Path(sys.argv[1]).read_text())
    print('\n'.join(errs) if errs else 'PASS: real FCFS/SCAN/deadline and all six loaded switches')
    sys.exit(bool(errs))
