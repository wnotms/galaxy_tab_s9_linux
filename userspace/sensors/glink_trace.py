#!/usr/bin/env python3
"""Test381-owned boot trace only: no ADSP start, bus/USB operation or DIAG send."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import signal
import time
from uuid import UUID

INSTANCE = 'gts9_test381'
EVENTS = tuple('qcom_glink_cmd_' + name for name in
               ('version', 'version_ack', 'open', 'open_ack', 'close', 'close_ack'))
ARG = 'trace_instance=' + INSTANCE + ',' + ','.join('qcom_glink:' + n for n in EVENTS)
BOOT_ARGS = ARG + ' trace_buf_size=128K'
CONFIG = '599ca47ab41a29469c3d5830e475049fca9f33bd2ab0923ad014e5ba3fa6ec6c'
NOTES = '5c0e82337affafefff586613d4a84c4f1388c9716ce251fe69d3c70aad18a518'
MACHINE = '3c2a1b8f2d624db4b5ffdc836050fcf6'
MAX_BYTES = 2 * 1024 * 1024
BOOT_DEADLINE = 300


def parse_stats(raw):
    fields = {}
    for line in raw.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            fields[key.strip()] = value.strip()
    for key in ('overrun', 'commit overrun', 'dropped events'):
        if key not in fields or not fields[key].isdecimal() or int(fields[key]):
            raise ValueError('trace loss or incomplete statistics: ' + key)
    return fields


class Trace:
    def __init__(self, root=Path('/')):
        self.root = root
        self.path = root / ('sys/kernel/tracing/instances/' + INSTANCE)
        self.boot = self.read('proc/sys/kernel/random/boot_id')
        UUID(self.boot)

    def read(self, name):
        return (self.root / name).read_text().strip()

    def same_boot(self, expected=None):
        if self.read('proc/sys/kernel/random/boot_id') != self.boot or (expected and UUID(expected) != UUID(self.boot)):
            raise ValueError('trace boot attribution mismatch')

    def admit(self):
        self.same_boot()
        cmdline = self.read('proc/cmdline').split()
        if cmdline.count(ARG) != 1 or cmdline.count('trace_buf_size=128K') != 1:
            raise ValueError('trace not enrolled by exact boot arguments')
        if (self.read('etc/machine-id') != MACHINE or
                hashlib.sha256(gzip.decompress((self.root / 'proc/config.gz').read_bytes())).hexdigest() != CONFIG or
                hashlib.sha256((self.root / 'sys/kernel/notes').read_bytes()).hexdigest() != NOTES):
            raise ValueError('trace kernel/machine identity')
        if (self.path.is_symlink() or not self.path.is_dir() or
                (self.path / 'current_tracer').read_text().strip() != 'nop' or
                (self.path / 'buffer_size_kb').read_text().strip() != '128'):
            raise ValueError('owned trace instance/buffer identity')
        expected = {'qcom_glink:' + n for n in EVENTS}
        if set((self.path / 'set_event').read_text().split()) != expected:
            raise ValueError('trace event set changed')
        for name in EVENTS:
            if (self.path / 'events/qcom_glink' / name / 'enable').read_text().strip() != '1':
                raise ValueError('expected trace event disabled')
        self.same_boot()

    def stop(self):
        # The only kernel runtime write: stop this exact boot-owned instance.
        # No write to the global instance, clocks, filters or event enable files.
        self.same_boot()
        if self.path.is_symlink() or not self.path.is_dir():
            raise ValueError('owned trace disappeared')
        (self.path / 'tracing_on').write_text('0\n')
        self.same_boot()

    def inventory(self):
        result = []
        for device in sorted((self.root / 'sys/bus/rpmsg/devices').glob('*')):
            row = dict(path=str(device), resolved=str(device.resolve()))
            for name in ('name', 'src', 'dst', 'modalias'):
                try: row[name] = (device / name).read_text().strip()
                except OSError: row[name] = None
            row['driver'] = str((device / 'driver').resolve()) if (device / 'driver').exists() else None
            result.append(row)
        return result

    def collect(self, expected):
        self.same_boot(expected)
        self.admit()
        self.stop()
        raw_stats = {p.parent.name: p.read_text()
                     for p in sorted((self.path / 'per_cpu').glob('cpu*/stats'))}
        stats, faults = {}, []
        for cpu, raw in raw_stats.items():
            try: stats[cpu] = parse_stats(raw)
            except ValueError as exc: faults.append(dict(cpu=cpu, reason=str(exc)))
        if len(raw_stats) != 8:
            faults.append(dict(reason='incomplete per-CPU trace statistics'))
        with (self.path / 'trace').open('rb') as stream:
            payload = stream.read(MAX_BYTES // 2 + 1)
        if len(payload) > MAX_BYTES // 2:
            payload = payload[:MAX_BYTES // 2]
            faults.append(dict(reason='trace exceeds registered raw byte limit; prefix only'))
        trace = payload.decode()
        if not re.search(r'qcom_glink_cmd_(version|open).*remote: lpass', trace):
            faults.append(dict(reason='no actual early ADSP GLINK event'))
        output = dict(boot_id=self.boot, uptime_seconds=float(self.read('proc/uptime').split()[0]),
                      trace_clock=(self.path / 'trace_clock').read_text().strip(),
                      per_cpu_stats=stats, raw_per_cpu_stats=raw_stats,
                      complete=not faults, faults=faults,
                      trace_bytes=len(payload), trace_sha256=hashlib.sha256(payload).hexdigest(),
                      trace=trace, rpmsg=self.inventory(), trace_stopped=True,
                      diagnostic_only=True, SSC_publication_proved=False)
        self.same_boot(expected)
        if len(json.dumps(output).encode()) > MAX_BYTES:
            raise ValueError('trace evidence exceeds registered byte limit')
        return output

    def watch(self):
        self.admit()
        while (self.path / 'tracing_on').read_text().strip() == '1':
            self.same_boot()
            if float(self.read('proc/uptime').split()[0]) >= BOOT_DEADLINE:
                self.stop()
                return dict(boot_id=self.boot, stopped=True, reason='boot-time trace deadline')
            time.sleep(1)
        return dict(boot_id=self.boot, stopped=True, reason='host stopped owned trace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('watch', 'collect', 'inventory'))
    parser.add_argument('--boot-id')
    args = parser.parse_args()
    observer = Trace()
    if args.mode == 'watch':
        observer.admit()
        def stop_signal(signum, frame):
            observer.stop()
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, stop_signal)
        signal.signal(signal.SIGINT, stop_signal)
        try: result = observer.watch()
        except BaseException:
            # Never disable another boot's trace after an attribution failure.
            observer.same_boot()
            observer.stop()
            raise
    elif args.mode == 'collect':
        if not args.boot_id: parser.error('collect requires --boot-id')
        result = observer.collect(args.boot_id)
    else:
        observer.same_boot(args.boot_id)
        result = dict(boot_id=observer.boot, rpmsg=observer.inventory())
        observer.same_boot(args.boot_id)
    print(json.dumps(result, indent=2))
    if result.get('complete') is False:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
