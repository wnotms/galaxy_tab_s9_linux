#!/usr/bin/env python3
"""Bounded boot-owned SMP2P/GLINK observation; no DSP or SMEM operation."""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import signal
from uuid import UUID

spec = importlib.util.spec_from_file_location(
    'ssc_provider_geometry', Path(__file__).with_name('glink_trace_382.py'))
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)

INSTANCE = 'gts9_ssc_provider'
SMP2P_EVENTS = ('smp2p_negotiate', 'smp2p_notify_in', 'smp2p_ssr_ack', 'smp2p_update_bits')
EVENTS = tuple('qcom_glink:' + name for name in geometry.EVENTS) + tuple(
    'qcom_smp2p:' + name for name in SMP2P_EVENTS)
ARG = 'trace_instance=' + INSTANCE + ',' + ','.join(EVENTS)
BOOT_ARGS = ARG + ' trace_buf_size=128K'
# Actual accepted-kernel formats, with only dynamic event ID excluded.
FORMAT_HASHES = {
    'smp2p_negotiate': '841a4580fa3ad0ba935fb59ef5cd6e83da8693776c8c56cbd50bb4fc006c3deb',
    'smp2p_notify_in': '30cd7aae2155f7f97c6b96c0d3113ee3f1abec0bd14fa208bf6fb96fda5b4040',
    'smp2p_ssr_ack': '4411f3802dcc3719ced98823b6549d604fa9aa703ff21d98f021de49f9eda2ea',
    'smp2p_update_bits': '1730cefd1b7eb7f6606c6117f397211f273bbe432de6ccb3701f6a7e6694a66d',
}
ROW = re.compile(r'\s*\S.*\[(\d{3})\]\s+\S{5}\s+(\d+\.\d+):\s+(\w+): (.*)')
HEADER = re.compile(r'# entries-in-buffer/entries-written: (\d+)/(\d+)\s+#P:8')


def format_hash(raw):
    if len(re.findall(r'^ID: \d+$', raw, re.M)) != 1:
        raise ValueError('missing/duplicate native event ID')
    canonical = re.sub(r'^ID: \d+\n', '', raw, flags=re.M).strip() + '\n'
    return hashlib.sha256(canonical.encode()).hexdigest()


def number(raw, bits, base=16):
    value = int(raw, base)
    if not 0 <= value < 1 << bits:
        raise ValueError('trace integer width')
    return value


def decode_event(name, payload):
    if name in geometry.EVENTS:
        if name.endswith(('version', 'version_ack')):
            match = re.fullmatch(r'(tx|rx) remote: (\S+) version: (\d+) features: (0x[0-9a-fA-F]+)', payload)
            if not match:
                raise ValueError('malformed GLINK version')
            direction, remote, version, features = match.groups()
            return dict(direction=direction, remote=remote,
                        version=number(version, 32, 10), features=number(features, 32))
        match = re.fullmatch(r'(tx|rx) remote: (\S+) channel: ([^\s\[\]]+)\[(\d+)/(\d+)\]', payload)
        if not match:
            raise ValueError('malformed GLINK channel')
        direction, remote, channel, local, peer = match.groups()
        return dict(direction=direction, remote=remote, channel=channel,
                    local=number(local, 16, 10), peer=number(peer, 16, 10))
    if name == 'smp2p_negotiate':
        match = re.fullmatch(r'(\S+): state=open out_features=(.*)', payload)
        # trace_print_flags_seq emits an EMPTY string for zero flags. Only
        # SSR_ACK is offered by this pinned driver's SMP2P_ALL_FEATURES.
        if not match or match[2] not in ('', 'SMP2P_FEATURE_SSR_ACK'):
            raise ValueError('malformed SMP2P negotiation')
        return dict(device=match[1], features=1 if match[2] else 0)
    if name == 'smp2p_ssr_ack':
        match = re.fullmatch(r'(\S+): SSR detected', payload)
        if not match:
            raise ValueError('malformed SMP2P SSR')
        return dict(device=match[1])
    if name == 'smp2p_notify_in':
        match = re.fullmatch(r'(\S+): (\S+): status:(0x[0-9a-fA-F]+) val:(0x[0-9a-fA-F]+)', payload)
        if not match:
            raise ValueError('malformed SMP2P inbound notification')
        return dict(device=match[1], client=match[2], status=number(match[3], 64), value=number(match[4], 32))
    if name == 'smp2p_update_bits':
        match = re.fullmatch(r'(\S+): (\S+): orig:(0x[0-9a-fA-F]+) new:(0x[0-9a-fA-F]+)', payload)
        if not match:
            raise ValueError('malformed SMP2P outbound update')
        return dict(device=match[1], client=match[2], original=number(match[3], 32), value=number(match[4], 32))
    raise ValueError('unregistered trace event: ' + name)


def analyze(evidence, expected_boot, adsp_device='smp2p-adsp'):
    """Derive facts only from complete attributed raw records and all CPU stats."""
    if (UUID(evidence['boot_id']) != UUID(expected_boot) or
            evidence.get('complete') is not True or evidence.get('trace_stopped') is not True):
        raise ValueError('incomplete/stale provider evidence')
    raw = evidence['trace']
    payload = raw.encode()
    if (len(payload) != evidence['trace_bytes'] or
            hashlib.sha256(payload).hexdigest() != evidence['trace_sha256'] or
            len(payload) > geometry.MAX_BYTES // 2 or not re.fullmatch(r'[\w.,@/-]+', adsp_device)):
        raise ValueError('raw provider trace identity/size')
    cpus = {'cpu' + str(i) for i in range(8)}
    raw_stats = evidence['raw_per_cpu_stats']
    if set(raw_stats) != cpus or set(evidence['per_cpu_stats']) != cpus:
        raise ValueError('missing/extra CPU trace statistics')
    stats = {cpu: geometry.parse_stats(value) for cpu, value in raw_stats.items()}
    if stats != evidence['per_cpu_stats']:
        raise ValueError('derived statistics mismatch')
    entries = {}
    for cpu, state in stats.items():
        if (not state.get('entries', '').isdecimal() or
                state.get('read events') != '0'):
            raise ValueError('missing entries or trace already consumed')
        entries[cpu] = int(state['entries'])
    records, headers, last_time = [], [], {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith('#'):
            if line.startswith('# entries-in-buffer/'):
                header = HEADER.fullmatch(line)
                if not header:
                    raise ValueError('malformed trace count header')
                headers.append(tuple(map(int, header.groups())))
            continue
        match = ROW.fullmatch(line)
        if not match:
            raise ValueError('unparsed trace record')
        cpu, timestamp, event, data = match.groups()
        if int(cpu) > 7 or len(records) >= 4096 or event not in (*geometry.EVENTS, *SMP2P_EVENTS):
            raise ValueError('unregistered CPU/event or record limit')
        clock = Decimal(timestamp)
        # The qualified clock is local: validate within a CPU, not ordering
        # across CPUs. Preserve original timestamps and merged record order.
        if clock < last_time.get(cpu, Decimal(0)):
            raise ValueError('per-CPU timestamp reversal')
        if clock > Decimal(str(evidence['uptime_seconds'])):
            raise ValueError('trace after collection boundary')
        last_time[cpu] = clock
        records.append(dict(cpu=int(cpu), timestamp=timestamp, event=event, **decode_event(event, data)))
    counts = Counter('cpu' + str(row['cpu']) for row in records)
    if (headers != [(len(records), len(records))] or
            {cpu: counts[cpu] for cpu in cpus} != entries):
        raise ValueError('raw/header/per-CPU event count mismatch')
    glink = [row for row in records if row.get('remote') == 'lpass']
    if not any(row['event'] in ('qcom_glink_cmd_version', 'qcom_glink_cmd_open') for row in glink):
        raise ValueError('no early ADSP GLINK boundary')
    adsp = [row for row in records if row.get('device') == adsp_device]
    negotiated = [row for row in adsp if row['event'] == 'smp2p_negotiate']
    return dict(boot_id=str(UUID(expected_boot)), complete=True, diagnostic_only=True,
                record_count=len(records), glink_adsp_count=len(glink), adsp_device=adsp_device,
                native_smp2p_devices=sorted({row['device'] for row in records if 'device' in row}),
                adsp_events=adsp, adsp_negotiation_observed=bool(negotiated),
                negotiation_timestamps=[row['timestamp'] for row in negotiated],
                ssr_ack_count=sum(row['event'] == 'smp2p_ssr_ack' for row in adsp),
                observation='NEGOTIATION_OBSERVED' if negotiated else 'NEGOTIATION_NOT_OBSERVED',
                absent_event_proves_negotiation_failure=False, SSC_publication_proved=False,
                unconfigured_remote_entries_inventoried=False)


class Trace(geometry.Trace):
    def __init__(self, root=Path('/')):
        super().__init__(root)
        self.path = root / ('sys/kernel/tracing/instances/' + INSTANCE)

    def describe(self):
        return super().describe() | {'instance': INSTANCE}

    def admit(self):
        self.same_boot()
        cmdline = self.read('proc/cmdline').split()
        if (cmdline.count(ARG) != 1 or cmdline.count('trace_buf_size=128K') != 1 or
                sum(arg.startswith('trace_instance=') for arg in cmdline) != 1):
            raise ValueError('provider trace boot enrollment')
        if (self.read('etc/machine-id') != geometry.MACHINE or
                hashlib.sha256(gzip.decompress((self.root / 'proc/config.gz').read_bytes())).hexdigest() != geometry.CONFIG or
                hashlib.sha256((self.root / 'sys/kernel/notes').read_bytes()).hexdigest() != geometry.NOTES):
            raise ValueError('provider trace kernel/machine identity')
        state = self.describe()
        if (state['instance_symlink'] or not state['instance_exists'] or
                state['current_tracer'] != 'nop' or '[local]' not in state['trace_clock']):
            raise ValueError('provider trace instance/clock')
        geometry.validate_geometry(state)
        actual = (self.path / 'set_event').read_text().split()
        if len(actual) != len(EVENTS) or set(actual) != set(EVENTS):
            raise ValueError('provider trace event set')
        for event in EVENTS:
            group, name = event.split(':')
            directory = self.path / 'events' / group / name
            if (directory / 'enable').read_text().strip() != '1' or (directory / 'filter').read_text().strip() != 'none':
                raise ValueError('provider event disabled/filtered')
            if group == 'qcom_smp2p' and format_hash((directory / 'format').read_text()) != FORMAT_HASHES[name]:
                raise ValueError('native provider event format changed')
        self.same_boot()

    def collect(self, expected):
        result = super().collect(expected)
        try:
            result['provider'] = analyze(result, expected)
        except (ValueError, KeyError, TypeError) as exc:
            result['complete'] = False
            result['faults'].append(dict(reason='provider analysis: ' + str(exc)))
        self.same_boot(expected)
        if len(json.dumps(result).encode()) > geometry.MAX_BYTES:
            raise ValueError('provider evidence exceeds byte limit')
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('watch', 'collect', 'inventory', 'state'))
    parser.add_argument('--boot-id')
    args = parser.parse_args()
    observer = Trace()
    if args.mode == 'watch':
        print(json.dumps(dict(event='PROVIDER_ADMISSION_STATE', **observer.describe())), flush=True)
        observer.admit()

        def stop_signal(signum, frame):
            observer.stop()
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, stop_signal)
        signal.signal(signal.SIGINT, stop_signal)
        try:
            result = observer.watch()
        except BaseException:
            observer.same_boot()
            observer.stop()
            raise
    elif args.mode in ('collect', 'state'):
        if not args.boot_id:
            parser.error(args.mode + ' requires --boot-id')
        observer.same_boot(args.boot_id)
        result = observer.collect(args.boot_id) if args.mode == 'collect' else observer.describe()
        observer.same_boot(args.boot_id)
    else:
        observer.same_boot(args.boot_id)
        result = dict(boot_id=observer.boot, rpmsg=observer.inventory())
        observer.same_boot(args.boot_id)
    print(json.dumps(result, indent=2))
    if result.get('complete') is False:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
