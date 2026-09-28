"""Read-only cable-observer state and bounded FunctionFS evidence review.

UDC state is recorded, never used as physical cable presence. Recovery bounds
start at the last confirmed offline command's START, before possible reattach.
"""
from dataclasses import dataclass
import json
import re


def boot_id(value):
    value = value.strip().lower().replace('-', '')
    if not re.fullmatch('[0-9a-f]{32}', value):
        raise ValueError('invalid boot ID')
    return value


@dataclass
class CableCycle:
    expected_boot: str
    expected_pid: int
    expected_sha256: str
    first_off_end: float | None = None
    last_off_start: float | None = None
    first_off_uptime: float | None = None
    last_off_uptime: float | None = None
    return_seen: bool = False
    recovered_at: float | None = None
    previous_end: float | None = None
    last_connected_uptime: float | None = None
    off_source_earliest: float | None = None
    return_uptime: float | None = None

    def identity(self, boot, pid, sha256):
        if boot_id(boot) != boot_id(self.expected_boot):
            raise ValueError('boot changed')
        if int(pid) != self.expected_pid or sha256 != self.expected_sha256:
            raise ValueError('daemon identity changed')

    def sample(self, *, online, native_seen, started, ended, uptime, boot,
               pid, sha256, udc_binding, udc_state):
        self.identity(boot, pid, sha256)
        if udc_binding != 'a600000.usb':
            raise ValueError('UDC binding changed')
        if ended < started or (self.previous_end is not None and started < self.previous_end):
            raise ValueError('non-monotonic capture bounds')
        self.previous_end = ended
        if not online and not native_seen:
            if self.first_off_end is None:
                self.first_off_end = ended
                self.first_off_uptime = uptime
                self.off_source_earliest = self.last_connected_uptime
            self.last_off_start = started
            self.last_off_uptime = uptime
        elif online and self.first_off_end is not None:
            # Includes polling/command duration uncertainty; never subtract an
            # invented polling delay to manufacture a recovery time.
            if self.last_off_start - self.first_off_end < 10:
                raise ValueError('10s physical offline lower bound not established')
            self.return_seen = True
            self.return_uptime = uptime
        elif online and native_seen:
            self.last_connected_uptime = uptime
        return self.return_seen

    def recovered(self, *, native_boot, native_pid, native_sha256, ncm_boot, now):
        if not self.return_seen:
            raise ValueError('no observed physical return')
        self.identity(native_boot, native_pid, native_sha256)
        if boot_id(ncm_boot) != boot_id(self.expected_boot):
            raise ValueError('NCM boot identity changed')
        bound = now - self.last_off_start
        if bound < 0 or bound > 60:
            raise ValueError('60s native shell/NCM recovery upper bound exceeded')
        self.recovered_at = now
        return bound

    def observed(self, now):
        if self.recovered_at is None or now < self.recovered_at:
            raise ValueError('recovery missing or invalid clock')
        return now - self.recovered_at >= 150


DISABLE_WARNING = 'received FUNCTIONFS_DISABLE while not enabled?'
LOG_LINE = re.compile(r'\s(\d+)\s+(\d+)\s+([IWEF])\s+gts9-adbd-reconnect: (\S+):\d+ (.*)$')


def review_adbd(raw, *, expected_boot, expected_pid, source_floor,
                allow_pre_enable_disable=False, warning_source_range=None):
    """Review complete raw JSON; allowance is opt-in and not a blanket warning filter.

One exact pre-enable DISABLE warning must share its monitor TID with a preceding
spawn and DISABLE, followed <=5s by ENABLE and <=1s by a worker. Other new W/E/F
messages, missing context, duplicates and wrong boot/PID stop. This diagnoses
the source's recoverable teardown branch, not device/global health.
"""
    lines = raw.splitlines()
    if not lines:
        raise ValueError('empty adbd journal')
    events = []
    previous_seconds = -1
    for line in lines:
        row = json.loads(line)
        if boot_id(row['_BOOT_ID']) != boot_id(expected_boot):
            raise ValueError('adbd journal boot changed')
        seconds = int(row['__MONOTONIC_TIMESTAMP']) / 1e6
        if seconds < previous_seconds:
            raise ValueError('adbd journal timestamps out of order')
        previous_seconds = seconds
        match = LOG_LINE.search(row['MESSAGE'])
        if seconds <= source_floor:
            continue
        if match:
            pid, tid, level, location, message = match.groups()
            if int(pid) != expected_pid or int(row['_PID']) != expected_pid:
                raise ValueError('adbd journal PID changed')
            events.append(dict(source_seconds=seconds, tid=tid, level=level,
                               location=location, message=message))
        elif int(row.get('PRIORITY', 7)) <= 4:
            raise ValueError('new unclassified service warning/error')
    warnings = []
    for i, event in enumerate(events):
        if event['level'] == 'I':
            continue
        if (not allow_pre_enable_disable or event['level'] != 'W' or
                event['location'] != 'usb.cpp' or event['message'] != DISABLE_WARNING):
            raise ValueError('new unclassified adbd warning/error: ' + event['message'])
        prior = events[:i]
        at = event['source_seconds']
        if warning_source_range is not None and not warning_source_range[0] <= at <= warning_source_range[1]:
            raise ValueError('pre-enable DISABLE outside physical transition')
        for text in ('UsbFfs-monitor thread spawned', 'USB event: FUNCTIONFS_DISABLE'):
            if not any(e['tid'] == event['tid'] and e['message'] == text and
                       0 <= at - e['source_seconds'] <= 1 for e in prior):
                raise ValueError('pre-enable DISABLE context missing')
        enable = next((e for e in events[i+1:] if e['message'] == 'USB event: FUNCTIONFS_ENABLE'), None)
        if enable is None or not 0 <= enable['source_seconds'] - at <= 5:
            raise ValueError('pre-enable DISABLE did not reach ENABLE within5s')
        worker = next((e for e in events[i+1:] if e['message'] == 'UsbFfs-worker thread spawned' and
                       e['source_seconds'] >= enable['source_seconds']), None)
        if worker is None or worker['source_seconds'] - enable['source_seconds'] > 1:
            raise ValueError('ENABLE worker missing')
        warnings.append(dict(warning_source_seconds=at, enable_source_seconds=enable['source_seconds'],
                             worker_source_seconds=worker['source_seconds'], monitor_tid=event['tid']))
    if len(warnings) > 1:
        raise ValueError('multiple pre-enable DISABLE warnings in one physical cycle')
    return dict(new_pre_enable_disable_warnings=warnings,
                classification='bounded-pre-enable-disable' if warnings else 'no-new-adbd-warning')
