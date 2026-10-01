#!/usr/bin/env python3
"""Strict loss-aware trace attribution, never ADC/charging/timing acceptance."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from collector import WORK, PROBES, boot_id, symbols, stats, profile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def records(raw, names):
    require(raw.endswith('\n'), 'truncated trace')
    reverse = {v: k for k, v in names.items()}
    result = []
    for line in raw.splitlines():
        if line.startswith('#'):
            continue
        match = re.fullmatch(r'\s*.+-(\d+)\s+\[(\d+)\]\s+(?:\S+\s+)?(\d+)\.(\d{6,9}):\s+(\w+):\s*(.*)', line)
        require(match is not None, 'malformed/unrecognized trace record')
        pid, cpu, sec, frac, event, data = match.groups()
        stamp = int(sec) * 10**9 + int(frac.ljust(9, '0'))
        require(not result or stamp >= result[-1]['ns'], 'clock reversal/unordered records')
        event = reverse.get(event, event)
        require(event in set(WORK) | set(PROBES), 'unexpected event')
        row = {'ns': stamp, 'pid': int(pid), 'cpu': 'cpu' + str(int(cpu)), 'event': event}
        if event in WORK:
            pointer = re.search(r'work struct[= ]((?:0x)?[0-9a-fA-F]+)(?=[: ])', data)
            require(pointer is not None and 0 < int(pointer[1], 16) < 2**64, 'invalid work pointer')
            require(re.search(r'function[= ]sm5440_poll(?:\s|$)', data) is not None, 'wrong work function')
            row['work'] = pointer[1].lower().removeprefix('0x')
        elif event == 'request_return':
            ret = re.search(r'\bret=(-?\d+)\s*$', data)
            require(ret is not None and -(2**31) <= int(ret[1]) < 2**31, 'invalid signed return')
            row['ret'] = int(ret[1])
        result.append(row)
    require(result, 'empty trace')
    return result


def pair(rows):
    pending, active, polls, requests = {}, {}, {}, {}
    workers, completed = [], []
    for row in rows:
        kind, pid, stamp = row['event'], row['pid'], row['ns']
        if kind == 'workqueue_queue_work':
            work = row['work']
            require(work not in pending, 'ambiguous repeated queue/cancellation')
            pending[work] = row
        elif kind == 'workqueue_execute_start':
            work = row['work']
            require(work not in active, 'overlapping same work pointer')
            active[work] = {'work': work, 'pid': pid, 'start_ns': stamp,
                            'queue_ns': pending.pop(work)['ns'] if work in pending else None}
        elif kind == 'poll_enter':
            require(pid not in polls, 'nested/unpaired poll entry')
            matches = [v for v in active.values() if v['pid'] == pid]
            require(len(matches) == 1, 'poll lacks unique work start')
            polls[pid] = matches[0]
            matches[0]['poll_entry_ns'] = stamp
        elif kind == 'poll_return':
            require(pid in polls, 'poll return without entry')
            polls.pop(pid)['poll_return_ns'] = stamp
        elif kind == 'workqueue_execute_end':
            work = row['work']
            require(work in active, 'work end without start')
            worker = active.pop(work)
            require(worker['pid'] == pid and 'poll_return_ns' in worker, 'worker/poll PID or pairing mismatch')
            require(worker['start_ns'] <= worker['poll_entry_ns'] <= worker['poll_return_ns'] <= stamp, 'poll order')
            worker.update(end_ns=stamp, worker_elapsed_ns=stamp - worker['start_ns'],
                          queue_delay_ns=None if worker['queue_ns'] is None else worker['start_ns'] - worker['queue_ns'])
            workers.append(worker)
        elif kind == 'request_enter':
            require(pid not in requests, 'nested request')
            requests[pid] = stamp
        elif kind == 'request_return':
            require(pid in requests, 'request return without entry')
            entry = requests.pop(pid)
            completed.append({'pid': pid, 'entry_ns': entry, 'return_ns': stamp,
                              'elapsed_ns': stamp - entry, 'return_code': row['ret']})
    require(not requests and not polls and not active and not pending, 'incomplete request/work/queue at boundary')
    require(1 <= len(completed) <= 8, 'unexpected fresh call count')
    require(len({v['pid'] for v in completed}) == 1, 'unexpected fresh caller')
    require(all(v['return_code'] <= 0 for v in completed), 'unexpected positive API return')
    require(all(v['return_code'] == 0 for v in completed[:-1]), 'request after first refusal')
    for request in completed:
        entry, end = request['entry_ns'], request['return_ns']
        request['overlapping_workers'] = [
            {'worker_index': i, 'already_running_at_entry': w['start_ns'] < entry,
             'queued_during_request': w['queue_ns'] is not None and entry <= w['queue_ns'] <= end,
             'completed_before_return': w['end_ns'] <= end}
            for i, w in enumerate(workers) if w['start_ns'] <= end and w['end_ns'] >= entry]
        request['timeout_branch'] = 'UNKNOWN' if request['return_code'] == -110 else 'not_identified_by_trace'
        request['causal_worker_assignment'] = None
    return completed, workers


def analyse(root):
    root = Path(root)
    report = {'verdict': 'UNKNOWN', 'hardware_acceptance': False, 'adc_duration_ns': None,
              'request_timeout_branch': 'UNKNOWN', 'uninstrumented_timing_acceptance': False}
    try:
        manifest = json.loads((root / 'manifest.json').read_text())
        require(isinstance(manifest, dict), 'manifest is not an object')
        require(manifest['collection_complete'] is True and manifest['collection_error'] is None and manifest['cleanup_errors'] == [], 'collection/cleanup failed')
        require(boot_id(manifest['boot_before']) == boot_id(manifest['boot_after']), 'boot changed')
        require(manifest['clock'] == 'boot', 'wrong clock metadata')
        names = manifest['probes']
        require(isinstance(names, dict), 'probe map is not an object')
        require(set(names) == set(PROBES) and all(v == manifest['group'] + '_' + k for k, v in names.items()), 'unexpected probe names')
        require(re.fullmatch(r'gts9t279_[a-f0-9]{12}', manifest['group']) is not None, 'invalid group')
        cpus = manifest['cpus']
        require(cpus and len(cpus) == len(set(cpus)) and all(re.fullmatch(r'cpu\d+', c) for c in cpus), 'invalid CPU inventory')
        files = manifest['files']
        require(isinstance(files, dict), 'file seal is not an object')
        for name, identity in files.items():
            require(Path(name).name == name, 'unsafe evidence name')
            raw = (root / name).read_bytes()
            require(len(raw) == identity['bytes'] and hashlib.sha256(raw).hexdigest() == identity['sha256'], 'evidence hash mismatch: ' + name)
        def read(name):
            require(name in files, 'unsealed evidence: ' + name)
            return (root / name).read_text()
        require('[boot]' in read('clock.txt'), 'boot clock not selected')
        require(symbols(read('kallsyms.txt')) == manifest['symbols'], 'runtime symbols changed')
        expected_events = {'workqueue:' + e for e in WORK} | {manifest['group'] + ':' + n for n in names.values()}
        require(set(read('enabled-events.txt').split()) == expected_events, 'enabled events mismatch')
        for event in WORK:
            fmt = read(event + '.format')
            require(all(re.search(r'field:[^;]*\b' + f + ';', fmt) for f in ('work', 'function')), 'unexpected work format')
            match = re.fullmatch(r'\s*function == (0x[0-9a-f]+|\d+)\s*', read(event + '.filter'))
            require(match is not None and int(match[1], 0) == int(manifest['symbols']['sm5440_poll'], 16), 'wrong work filter')
        for kind in PROBES:
            fmt = read(kind + '.format')
            if kind == 'request_return':
                require(re.search(r'field:s32 ret;[^\n]*signed:1;', fmt), 'wrong return format')
        before, after = profile(read('profile-before.txt'), names), profile(read('profile-after.txt'), names)
        require(all(hits == 0 for hits, _ in before.values()), 'preexisting probe hits')
        require(all('/' + n not in read('global-probes-after.txt') for n in names.values()), 'probe cleanup incomplete')
        rows = records(read('trace.txt'), names)
        counts = Counter(r['cpu'] for r in rows)
        require(set(counts) <= set(cpus), 'unknown trace CPU')
        for cpu in cpus:
            require(stats(read(cpu + '-before.stats'))['entries'] == 0, 'preexisting events')
            require(stats(read(cpu + '-after.stats'))['entries'] == counts[cpu], 'trace entry mismatch/truncation')
        hits = Counter(r['event'] for r in rows)
        for kind, name in names.items():
            require(after[name][0] == hits[kind], 'probe hits not fully represented')
        requests, workers = pair(rows)
        report.update(verdict='BOUNDED_TRACE_ATTRIBUTED', boot_id=manifest['boot_before'],
                      clock='boot', requests=requests, workers=workers,
                      displayed_timestamp_precision='6..9 decimal seconds; no sub-display precision inferred',
                      queue_boundaries_complete=all(w['queue_ns'] is not None for w in workers),
                      causal_assignment='not established; temporal overlap only',
                      limitations=['worker includes I2C/waits/scheduling; not ADC duration',
                                   'tracing adds overhead', 'timeout branch remains unknown'])
    except (ValueError, OSError, KeyError, TypeError) as exc:
        report['reason'] = str(exc)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = analyse(args.capture)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(report['verdict'])
    raise SystemExit(0 if report['verdict'] == 'BOUNDED_TRACE_ATTRIBUTED' else 1)


if __name__ == '__main__':
    main()
