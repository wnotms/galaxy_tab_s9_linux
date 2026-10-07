"""Pure Test336 evidence gates; no device operations or charging policy writes."""
import math
import re

from ordinary_charge_window import ChargeWindow, validate_safety


FAULT = re.compile(r'\b(?:Kernel panic|BUG:|Oops:|Internal error:|SError|soft lockup|hard LOCKUP|rcu.*(?:detected.*stall|INFO:.*stall)|blocked for more than|non-responsive|workqueue lockup|CSD.*(?:stall|non.response)|WARNING: CPU:)', re.I)
FAILED = ('PPS OFF return failed:', 'PPS OFF check stopped:', 'fixed fallback failed:',
          'fixed return check failed:', 'direct charging is not holding')
NEGOTIATED = re.compile(r'PPS OFF negotiated: source=(\d+) lease=(\d+) target=(\d+)mV/(\d+)mA pump_ON=0$')
SAMPLED = re.compile(r'PPS OFF sampled: target=(\d+)mV/(\d+)mA observed=(\d+)mV range=(\d+)\.\.(\d+)mV samples=(\d+) settled=(\d+)ms raw_ibus=0 pump_ON=0$')
FIXED = re.compile(r'fixed return verified: source=(\d+) lease=(\d+) vbus=(\d+)uV samples=(\d+) range=(\d+)\.\.(\d+)mV settled=(\d+)ms raw_ibus=0 pump_off=1$')
COMPLETE = re.compile(r'PPS OFF return complete: target=(\d+)mV/(\d+)mA lease=0 fixed_return=1 pump_ON=0$')
EVENTS = (('PPS OFF negotiated:', NEGOTIATED), ('PPS OFF sampled:', SAMPLED),
          ('fixed return verified:', FIXED), ('PPS OFF return complete:', COMPLETE))


def native_proof(rows, boot, required=False):
    """Accept only a unique, ordered, bounded native transaction in a full boot.

    Pending prefixes are allowed while collecting; malformed/duplicate/error
    evidence is immediately rejected. A late observer cannot erase early faults.
    The owned PPS API transaction may contain several TCPM protocol Requests.
    """
    if not rows or min(int(r['__MONOTONIC_TIMESTAMP']) for r in rows) > 5000000:
        raise ValueError('missing/empty/incomplete kernel journal')
    found = []
    for r in rows:
        if r.get('_BOOT_ID') != boot:
            raise ValueError('journal boot attribution')
        msg = str(r.get('MESSAGE', '')).strip()
        if FAULT.search(msg) or any(s in msg for s in FAILED) or re.search(r'pump_ON=[1-9]', msg):
            raise ValueError('native/kernel first failure: ' + msg)
        for number, (label, pattern) in enumerate(EVENTS):
            if label in msg:
                match = pattern.search(msg)
                if not match or number != len(found):
                    raise ValueError('duplicate/malformed/out-of-order native proof')
                stamp = int(r['__MONOTONIC_TIMESTAMP'])
                if stamp < 0 or (found and stamp < found[-1][0]):
                    raise ValueError('native source timestamp order')
                found.append((stamp, tuple(map(int, match.groups()))))
    if found:
        source, lease, target, ma = found[0][1]
        if not source or not lease or not 8200 <= target <= 10500 or target % 20 or ma != 1800 or found[0][0] > 330000000:
            raise ValueError('native negotiated bounds/deadline')
    if len(found) >= 2:
        mv, current, observed, low, high, count, settled = found[1][1]
        if (mv, current) != (target, ma) or not target-500 <= low <= observed <= high <= min(target+500, 10800) or high-low > 100 or not 3 <= count <= 30 or not 100 <= settled <= 1500 or found[1][0]-found[0][0] > 2000000:
            raise ValueError('PPS physical sample bounds')
    if len(found) >= 3:
        fs, fl, vbus, count, low, high, settled = found[2][1]
        if fs < source or fl != lease or not 8550 <= low <= high <= 9450 or high-low > 100 or not low*1000 <= vbus <= high*1000 or count < 3 or settled < 100 or found[2][0]-found[1][0] > 20000000:
            raise ValueError('fixed physical return/source/lease bounds')
    if len(found) == 4:
        if found[3][1] != (target, ma) or found[3][0]-found[2][0] > 2000000:
            raise ValueError('terminal fixed return/release')
        return dict(source=source, lease=lease, target_mv=target, target_ma=ma,
                    pps_observed_mv=observed, fixed_vbus_uv=vbus,
                    timestamps_us=[x[0] for x in found], pump_ON=False, lease_released=True)
    if required:
        raise ValueError('native transaction incomplete')
    return None


def validate_native_sample(d, plan):
    """PPS permitted only before terminal proof; pack/OFF gates never relaxed."""
    if d['boot'] != plan['boot_id'] or d['boot_end'] != d['boot'] or d['direct'] not in ('N', '0') or d['fixed_check'] not in ('N', '0') or d['pps_check'] not in ('Y', '1'):
        raise ValueError('boot/diagnostic flags')
    if not isinstance(d['pump'], int) or not 0 <= d['pump'] <= 255 or d['pump'] & 12 or d['config_data_written'] is not False:
        raise ValueError('pump OFF/register access')
    b, u, p = d['battery'], d['usb'], d['tcpm']
    if b.get('POWER_SUPPLY_HEALTH') != 'Good' or b.get('POWER_SUPPLY_PRESENT') != '1' or b.get('POWER_SUPPLY_VOLTAGE_MAX_DESIGN') != '4440000':
        raise ValueError('pack health/design')
    for key, lo, hi in [('CAPACITY', 20, 80), ('VOLTAGE_NOW', 3500000, 4300000), ('TEMP', 200, 380)]:
        if not lo <= int(b['POWER_SUPPLY_'+key]) < hi:
            raise ValueError('pack ' + key)
    if d['pack']['mode'] != 'enabled' or not 20000 <= int(d['pack']['temp']) < 38000 or abs(int(d['pack']['temp'])-100*int(b['POWER_SUPPLY_TEMP'])) > 500:
        raise ValueError('real pack sensor')
    if d['roles'] != ['[sink]', '[device]']:
        raise ValueError('Type-C role')
    online = p.get('POWER_SUPPLY_ONLINE')
    if online == '2':
        voltage = int(p['POWER_SUPPLY_VOLTAGE_NOW'])
        # CURRENT_MAX is the source APDO ceiling, CURRENT_NOW the negotiated
        # request. Advertising >1.8A does not authorize requesting that current.
        if '[PD_PPS]' not in p.get('POWER_SUPPLY_USB_TYPE', '') or not 8200000 <= voltage <= 10500000 or voltage % 20000 or not 0 < int(p['POWER_SUPPLY_CURRENT_NOW']) <= min(1800000, int(p['POWER_SUPPLY_CURRENT_MAX'])) or not int(p['POWER_SUPPLY_VOLTAGE_MIN']) <= voltage <= int(p['POWER_SUPPLY_VOLTAGE_MAX']):
            raise ValueError('PPS selected budget')
        if not 100000 <= int(u['POWER_SUPPLY_INPUT_CURRENT_LIMIT']) <= 1500000:
            raise ValueError('switching ceiling during lease')
    elif online == '1':
        validate_safety(d, plan)
    else:
        raise ValueError('detach/unknown source during native transaction')


class RoundWindow:
    """Native admission then full ordinary window; first error permanently stops."""
    def __init__(self, plan, armed_at):
        self.plan, self.armed_at = plan, armed_at
        self.previous = None
        self.proof = None
        self.ordinary = None
        self.stopped = False

    def advance(self, d, rows):
        if self.stopped:
            raise ValueError('first-stop latch')
        try:
            validate_native_sample(d, self.plan)
            now = d['monotonic']
            if not math.isfinite(now) or now < self.armed_at or (self.previous is not None and not 0 < now-self.previous <= self.plan['sample_gap_max_seconds']):
                raise ValueError('response/clock gap')
            self.previous = now
            proof = native_proof(rows, self.plan['boot_id'])
            if self.proof and proof != self.proof:
                raise ValueError('native proof drift')
            if proof:
                self.proof = proof
                if self.ordinary is None:
                    self.ordinary = ChargeWindow(self.plan, now)
                # Terminal release requires fixed9 immediately; only ordinary
                # status/current are allowed to settle afterwards.
                if d['tcpm'].get('POWER_SUPPLY_ONLINE') != '1' or int(d['tcpm']['POWER_SUPPLY_VOLTAGE_NOW']) != 9000000:
                    raise ValueError('fixed9 lost after native completion')
                return dict(self.ordinary.advance(d), native=proof)
            if d['uptime'] > 330 or now-self.armed_at > 240:
                raise TimeoutError('native completion deadline')
            return dict(state='WAIT_NATIVE', observation_seconds=0, complete=False)
        except Exception:
            self.stopped = True
            raise
