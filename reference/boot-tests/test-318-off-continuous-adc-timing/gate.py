"""Pure OFF timing evidence parser; never grants charging/protection capability."""
import importlib.util
from pathlib import Path
import re

R = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('timing318_ordinary', R.parent / 'test-313-adc-condition-comparison/ordinary-gate.py')
ordinary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ordinary)
values = ordinary.values
battery_entry = ordinary.battery_entry


def require(ok, message):
    if not ok:
        raise ValueError(message)


def octets(s, key, count, separator=' '):
    fields = s[key].split(separator)
    require(len(fields) == count and all(re.fullmatch('[0-9a-fA-F]{2}', x) for x in fields), 'raw octets: ' + key)
    return [int(x, 16) for x in fields]


def numbers(s, key, count):
    fields = s[key].split('/')
    require(len(fields) == count, 'tuple size: ' + key)
    return [int(x) for x in fields]


def fault_free(v):
    return not (v[0] & 27 or v[1] & 3 or v[2] & 159 or v[3] & 6)


def timing(raw, port):
    s, p = values(raw), values(port)
    n = lambda key: int(s[key], 0)
    require(s['format'] == 'sm5440-passive-v1' and s['registers_are_cached'] == '1'
            and s['independently_calibrated'] == s['pump_enable_supported'] == '0', 'cached OFF diagnostic identity')
    for key, expected in {'timing_test': 1, 'timing_attempted': 1, 'timing_count': 8,
                          'timing_restored': 1, 'timing_admission_error': 0, 'timing_exit_error': 0,
                          'timing_error': 0, 'timing_cleanup_error': 0, 'timing_off_attempted': 0,
                          'timing_off_error': 0, 'fault': 0, 'stopped': 0,
                          'startup_pending': 0, 'last_sample_error': 0}.items():
        require(n(key) == expected, 'terminal diagnostic state: ' + key)
    require(1 <= n('timing_polls') <= 450 and 1 <= n('timing_readiness_checks') <= 20, 'bounded acquisition/readiness')
    require(n('timing_first_readiness_error') in (0, -11, -16), 'unexpected readiness fault')
    start, disabled, enabled, end = [n('timing_' + key + '_ms') for key in ('started', 'disabled', 'enabled', 'completed')]
    require(0 < start <= disabled <= enabled <= end and enabled - disabled >= 50 and end - start <= 2000, 'diagnostic transaction times')
    before, channels, restored, restored_channels = octets(s, 'timing_controls', 4, '/')
    require(before == restored and channels == restored_channels and not before & 1, 'exact disabled converter restore')
    initial_int = octets(s, 'timing_initial_int', 4)
    initial_status = octets(s, 'timing_initial_status', 4)
    require(fault_free(initial_int) and fault_free(initial_status) and initial_status[2] & 32
            and not initial_status[2] & 64, 'initial attached OFF faults/status')
    sources = [numbers(s, 'timing_source' + str(i), 8) for i in range(2)]
    packs = [numbers(s, 'timing_pack' + str(i), 7) for i in range(2)]
    require(sources[0][:3] == sources[1][:3] and all(x > 0 for x in sources[0][:3]), 'source epochs')
    require(packs[0][:2] == packs[1][:2] and all(x > 0 for x in packs[0][:2]), 'pack epochs')
    for source, pack in zip(sources, packs):
        require(0 < source[3] <= source[4] and source[4] - source[3] <= 500
                and source[5:] == [5000, source[6], 1] and 0 < source[6] <= 1800, 'native PC fixed5 source')
        require(0 < pack[2] <= pack[3] and pack[3] - pack[2] <= 500
                and 5 <= pack[4] < 80 and 3500000 <= pack[5] < 4300000
                and 200 <= pack[6] < 380, 'native real pack')
    require(sources[0][4] <= start and packs[0][3] <= start
            and end <= sources[1][3] and end <= packs[1][2], 'native fact/ADC chronology')
    require(p['format'] == 'sm5714-current-port-v1' and int(p['ret']) == 0
            and int(p['online']) == 1 and int(p['charge_requested']) == 1
            and [int(p[k]) for k in ('instance', 'source_generation', 'budget_generation')] == sources[0][:3]
            and int(p['budget_mv']) == 5000 and int(p['voltage_uv']) == 5000000
            and int(p['budget_ma']) == sources[0][6] == sources[1][6]
            and int(p['current_ua']) == sources[1][6] * 1000, 'current fixed5 source/epoch')
    require(sources[1][4] <= int(p['started_ms']) <= int(p['completed_ms'])
            and int(p['completed_ms']) - int(p['started_ms']) <= 500, 'current source bracket')
    samples, previous = [], None
    for i in range(8):
        prefix = 'timing_sample' + str(i)
        clear, ready_begin, ready_end, adc_begin, adc_end = numbers(s, prefix + '_times', 5)
        require(enabled <= clear <= ready_begin <= ready_end <= adc_begin <= adc_end <= end, 'READY/raw-read chronology')
        deadline = enabled if previous is None else previous
        require(0 < ready_end - deadline <= 500, 'new bounded READY')
        event = octets(s, prefix + '_int', 4)
        require(event[3] & 1 and fault_free(event) and n(prefix + '_faults') == 0, 'new READY/no consumed fault')
        for suffix in ('_status', '_status_after'):
            status = octets(s, prefix + suffix, 4)
            require(fault_free(status) and status[2] & 32 and not status[2] & 64, 'live attached fault-free status')
        mode, control, ch = octets(s, prefix + '_controls', 3, '/')
        require(not mode & 12 and control == (before & ~11) | 11 and ch == 223, 'OFF/continuous AVG32 controls')
        a = octets(s, prefix + '_adc', 11)
        code = lambda h, l: (h << 5) | (l >> 3)
        vbus, vbat, ibus, die = 4096000 + code(a[0], a[1]) * 1000, 2048000 + code(a[9], a[10]) * 500, code(a[4], a[5]) * 625, 225 + a[8] * 5
        require(4500000 <= vbus <= 9500000 and 3500000 <= vbat < 4440000
                and ibus == 0 and die < 420, 'decoded physical bounds')
        samples.append(dict(ready_gap_software_ms=ready_end-deadline, ready_read_bracket_ms=[ready_begin, ready_end],
                            ADC_read_bracket_ms=[adc_begin, adc_end], vbus_uv=vbus, vbat_uv=vbat, ibus_ua=ibus, die_decic=die))
        previous = ready_end
    return dict(verdict='OFF_CONTINUOUS_READY_CAPTURED', samples=samples, source_epoch=sources[0][:3],
                source_calibrated=False, software_ocp_verified=False, pump_ON=False, PPS=False,
                ADC_active_100ms_gate_qualified=False, coherent_channels_qualified=False)
