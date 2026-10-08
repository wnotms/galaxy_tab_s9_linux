#!/usr/bin/env python3
"""Pure duration-bound native proof for future SM5440 registrations.

Derived from the accepted immutable Test345 native parser. No hardware access.
The caller supplies the registered window; never infer authorization from a log.
Historical Test345 scripts/semantics remain unchanged.
"""
import re

FAIL = re.compile(r'one-shot parked settle failed:|one-shot (?:pack )?range rejected:|one-shot pump stopped:|direct-charge start failed|fixed fallback failed|stopping direct charge|retained fault=|failed to refresh PPS|latched fault:|Kernel panic|soft lockup|hard LOCKUP|rcu.*stall|CSD.*(?:stall|non-responsive)|\bOops:|\bBUG:|Internal error|SError|blocked for more than|workqueue lockup|WARNING: CPU:|I2C.*(?:error|timeout)', re.I)


def native_proof(rows, boot, *, expected_window_ms, required=False):
    """Full journal, kernel source time, one attempt with paired parked refreshes."""
    if type(expected_window_ms) is not int or expected_window_ms not in (30000, 300000, 1200000):
        raise ValueError('unregistered bounded duration')
    if not rows or any(r.get('_BOOT_ID') != boot for r in rows) or min(int(r['__MONOTONIC_TIMESTAMP']) for r in rows) > 5000000:
        raise ValueError('incomplete/mixed kernel journal')
    # Failed cleanup can return fixed9 with an outstanding parked refresh.
    # Prefer the explicit native STOP over a later derived order rejection.
    # This scan never promotes a failed transaction to completion.
    for r in rows:
        msg = str(r.get('MESSAGE', ''))
        if FAIL.search(msg):
            raise ValueError('first native/kernel fault: ' + msg)
    starts, fixed, terminal, direct = [], [], [], []
    direct_target = None
    parked = None
    refreshes = 0
    settled = None
    zero_proofs = 0
    deferred = None
    previous = -1
    for r in rows:
        msg = str(r.get('MESSAGE', ''))
        if FAIL.search(msg):
            raise ValueError('first native/kernel fault: ' + msg)
        if not any(x in msg for x in ('one-shot ', 'fixed return verified:', 'direct charge started:')):
            continue
        stamp = int(r['_SOURCE_MONOTONIC_TIMESTAMP'])
        if stamp < previous:
            raise ValueError('native timestamp order')
        previous = stamp
        if 'one-shot pump started:' in msg:
            m = re.search(r'target=(\d+)mV/(\d+)mA deadline=(\d+)ms max_ms=(\d+) no_restart=1$', msg)
            if not m or starts:
                raise ValueError('invalid/repeated native start')
            mv, ma, deadline, window = map(int, m.groups())
            if not 8200 <= mv <= 10500 or mv % 20 or ma != 1800 or window != expected_window_ms or not expected_window_ms-1000 <= deadline-stamp//1000 <= expected_window_ms:
                raise ValueError('native target/deadline')
            if direct_target != (mv, ma):
                raise ValueError('native entry/start target mismatch')
            starts.append((stamp, mv, ma, deadline))
        elif 'one-shot parked settled:' in msg:
            m = re.search(r'samples=(\d+) waited=(\d+)ms raw_ibus=0 pump_OFF=1$', msg)
            if not m or settled is not None or fixed or terminal or deferred is not None or ((starts and parked is None) or (direct and not starts)):
                raise ValueError('invalid/duplicate parked-current proof')
            count, waited = map(int, m.groups())
            if not 3 <= count <= 30 or waited < 100:
                raise ValueError('parked-current settling bounds')
            settled = stamp
            zero_proofs += 1
        elif 'direct charge started:' in msg:
            if settled is None or stamp <= settled:
                raise ValueError('initial zero-current proof missing')
            settled = None
            m = re.search(r'PPS (\d+) mV/(\d+) mA, ibus limit (\d+) mA$', msg)
            if not m:
                raise ValueError('native hardware-current witness missing')
            mv, ma, hardware_ma = map(int, m.groups())
            if not 8200 <= mv <= 10500 or mv % 20 or ma != 1800 or hardware_ma != 1700:
                raise ValueError('native hardware/PPS current mismatch')
            direct_target = (mv, ma)
            direct.append(stamp)
            if len(direct) > 1:
                raise ValueError('second entry')
        elif 'one-shot refresh parked:' in msg:
            if not starts or parked is not None or terminal or deferred is not None or 'pump_OFF=1' not in msg:
                raise ValueError('unpaired park')
            parked = stamp
        elif 'one-shot refresh resumed:' in msg:
            m = re.search(r'target=(\d+)mV/(\d+)mA deadline=(\d+)ms$', msg)
            if not m or parked is None or settled is None or not parked < settled < stamp or stamp-parked > 2000000 or terminal:
                raise ValueError('unpaired/late refresh')
            mv, ma, deadline = map(int, m.groups())
            if not 8200 <= mv <= 10500 or mv % 20 or ma != 1800 or deadline != starts[0][3] or stamp >= deadline*1000:
                raise ValueError('refresh bounds/deadline')
            parked = None
            settled = None
            refreshes += 1
        elif 'one-shot refresh deferred:' in msg:
            m = re.search(r'remaining=(\d+)ms deadline=(\d+)ms pump_unchanged=1$', msg)
            if not m or not starts or parked is not None or settled is not None or fixed or terminal or deferred is not None:
                raise ValueError('invalid/repeated/out-of-phase final refresh deferral')
            remaining, deadline = map(int, m.groups())
            if not 0 < remaining <= 2000 or deadline != starts[0][3] or not deadline*1000-2100000 <= stamp < deadline*1000 or abs(deadline-stamp//1000-remaining) > 100:
                raise ValueError('final refresh deferral timing/deadline')
            deferred = stamp
        elif 'fixed return verified:' in msg:
            if not starts or fixed or terminal or parked is not None:
                raise ValueError('invalid fixed-return order')
            m = re.search(r'vbus=(\d+)uV samples=(\d+) range=(\d+)\.\.(\d+)mV settled=(\d+)ms raw_ibus=0 pump_off=1$', msg)
            if not m:
                raise ValueError('fixed physical proof missing')
            vbus, count, low, high, settle = map(int, m.groups())
            if not 8550 <= low <= high <= 9450 or high-low > 100 or not low*1000 <= vbus <= high*1000 or count < 3 or settle < 100:
                raise ValueError('fixed physical bounds')
            fixed.append(stamp)
        elif 'one-shot pump complete:' in msg:
            m = re.search(r'lease=0 fixed_return=1 positive_samples=(\d+) no_restart=1$', msg)
            if not m or int(m[1]) <= 0 or not starts or not fixed or terminal or parked is not None:
                raise ValueError('invalid completion/charge proof')
            if stamp < starts[0][3]*1000 or stamp-starts[0][3]*1000 > 3000000:
                raise ValueError('completion deadline/cleanup latency')
            terminal.append(stamp)
    if terminal:
        if len(direct) != 1 or not 0 < starts[0][0]-direct[0] < 100000 or not 1 <= refreshes <= expected_window_ms//4000 or zero_proofs != refreshes+1:
            raise ValueError('missing entry/refresh proof')
        return dict(window_ms=expected_window_ms, target_mv=starts[0][1], target_ma=1800, hardware_input_ma=1700, deadline_ms=starts[0][3],
                    started_us=starts[0][0], completed_us=terminal[0], refreshes=refreshes,
                    fixed_return=True, pump_ON_observed=True, no_restart=True, parked_zero_proofs=zero_proofs,
                    refresh_deferrals=int(deferred is not None))
    if required:
        raise ValueError('native transaction incomplete')
    return None

