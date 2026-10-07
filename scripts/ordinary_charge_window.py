"""Pure fixed9 charging admission/continuity; no device or kernel operations.

The caller owns enrolled transport, kernel identity, native completion, journal
and service gates. Those gates and validate_safety run before every update.
Only ordinary status/current settling is allowed before observation begins.
"""
from dataclasses import dataclass
import math


def validate_safety(d, plan):
    if d['boot'] != plan['boot_id'] or d['boot_end'] != d['boot']:
        raise ValueError('unexpected/mixed boot')
    if d['direct'] not in ('N', '0') or not 0 <= d['pump'] <= 255 or d['pump'] & 12:
        raise ValueError('direct/pump not OFF')
    b, u, p = d['battery'], d['usb'], d['tcpm']
    if b.get('POWER_SUPPLY_HEALTH') != 'Good' or b.get('POWER_SUPPLY_PRESENT') != '1' or b.get('POWER_SUPPLY_VOLTAGE_MAX_DESIGN') != '4440000':
        raise ValueError('battery health/design')
    for key, low, high in [('CAPACITY', plan['soc_min'], plan['soc_max_exclusive']),
                           ('VOLTAGE_NOW', plan['vbat_min_uv'], plan['vbat_max_exclusive_uv']),
                           ('TEMP', plan['temp_min_decic'], plan['temp_max_exclusive_decic'])]:
        if not low <= int(b['POWER_SUPPLY_' + key]) < high:
            raise ValueError('pack ' + key)
    if d['pack']['mode'] != 'enabled' or abs(int(d['pack']['temp']) - 100 * int(b['POWER_SUPPLY_TEMP'])) > 500 or not plan['temp_min_decic'] * 100 <= int(d['pack']['temp']) < plan['temp_max_exclusive_decic'] * 100:
        raise ValueError('pack sensor')
    online = p.get('POWER_SUPPLY_ONLINE')
    # TCPM USB_TYPE describes source capabilities, including at fixed ONLINE=1.
    # ONLINE=2 identifies programmable operation; a PPS-capable source is valid.
    if online not in ('0', '1'):
        raise ValueError('non-fixed/unknown source')
    if online == '1':
        mv = int(p['POWER_SUPPLY_VOLTAGE_NOW'])
        if mv not in (5000000, 9000000) or int(p['POWER_SUPPLY_VOLTAGE_MAX']) != mv or d['roles'] != ['[sink]', '[device]']:
            raise ValueError('fixed voltage/roles')
        limit = int(u['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])
        ceiling = 1800000 if mv == 5000000 else plan['fixed9_input_max_ua']
        if not 100000 <= limit <= min(ceiling, int(p['POWER_SUPPLY_CURRENT_MAX'])) or (limit - 100000) % 25000:
            raise ValueError('input/source ceiling')


def fixed9(d):
    return d['tcpm'].get('POWER_SUPPLY_ONLINE') == '1' and int(d['tcpm'].get('POWER_SUPPLY_VOLTAGE_NOW', 0)) == 9000000


def charging_ready(d):
    return (fixed9(d) and d['usb'].get('POWER_SUPPLY_ONLINE') == '1' and
            '[PD]' in d['usb'].get('POWER_SUPPLY_USB_TYPE', '') and
            d['battery'].get('POWER_SUPPLY_STATUS') == 'Charging' and
            int(d['battery']['POWER_SUPPLY_CURRENT_NOW']) > 0)


@dataclass
class ChargeWindow:
    plan: dict
    armed_at: float
    settling_seconds: float = 10
    first_fixed_at: float | None = None
    started_at: float | None = None
    previous_at: float | None = None
    stopped: bool = False

    def __post_init__(self):
        if not 0 < self.settling_seconds <= 10 or not 0 < self.plan['wait_seconds'] <= 240 or self.plan['charge_seconds'] < 30:
            raise ValueError('unbounded/shortened window')

    def advance(self, d):
        if self.stopped:
            raise ValueError('first-stop latch')
        try:
            validate_safety(d, self.plan)
            now = d['monotonic']
            if not math.isfinite(now) or now < self.armed_at or (self.previous_at is not None and not 0 < now - self.previous_at <= self.plan['sample_gap_max_seconds']):
                raise ValueError('response/clock gap')
            self.previous_at = now
            if self.started_at is not None:
                if not charging_ready(d):
                    raise ValueError('charging lost during observation')
            else:
                if self.first_fixed_at is None:
                    if now - self.armed_at > self.plan['wait_seconds']:
                        raise TimeoutError('fixed9 wait expired')
                    if fixed9(d):
                        self.first_fixed_at = now
                if self.first_fixed_at is not None:
                    if not fixed9(d):
                        raise ValueError('fixed9 lost during settling')
                    if now - self.first_fixed_at > self.settling_seconds:
                        raise TimeoutError('healthy charging did not settle')
                    if charging_ready(d):
                        self.started_at = now
            seconds = 0 if self.started_at is None else now - self.started_at
            return dict(state='OBSERVE' if self.started_at is not None else ('SETTLING' if self.first_fixed_at is not None else 'WAIT'), observation_seconds=seconds, complete=seconds >= self.plan['charge_seconds'])
        except Exception:
            self.stopped = True
            raise
