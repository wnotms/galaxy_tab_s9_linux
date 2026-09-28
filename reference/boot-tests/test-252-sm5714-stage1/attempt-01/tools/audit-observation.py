"""Reconcile archived Test252 telemetry and full journals; never access a device."""
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path('scripts').resolve()))
import production_reboot_stability as p

p.P = p.TEST250_ROOT / 'attempt-05'
base = p.baseline()
root = Path('reference/boot-tests/test-252-sm5714-stage1/attempt-01')
phase = sys.argv[1]
folder = root / phase
summary = json.loads((folder / 'summary.json').read_text())
assert summary['verdict'].startswith('bounded observation completed')
boot = json.loads((root / 'boot/acceptance/summary.json').read_text())['boot_id']
samples = json.loads((folder / 'samples.json').read_text())
observed = []
known_gpu_count = 0
for index, sample in enumerate(samples, 1):
    stem = folder / f'sample-{index:03d}'
    command = json.loads(stem.with_suffix('.command.json').read_text())
    assert command['status'] == 0
    assert sample['utc'] == command['utc']
    raw = stem.with_suffix('.txt').read_text()
    sections = {}
    for name in ('boot', 'uptime', 'battery', 'usb', 'failed', 'journal'):
        remaining = raw.split('__' + name + '__\n', 1)[1]
        sections[name] = re.split(r'^__[a-z]+__\n', remaining, maxsplit=1, flags=re.M)[0].strip()
    assert p.evidence.canonical_boot_id(sections['boot']) == sample['boot_id'] == boot
    assert not sections['failed']
    assert float(sections['uptime'].split()[0]) == sample['uptime_s']
    props = dict(line.split('=', 1) for name in ('battery', 'usb')
                 for line in sections[name].splitlines() if '=' in line)
    for key, prop in {'online': 'ONLINE', 'current_ua': 'CURRENT_NOW',
                      'voltage_uv': 'VOLTAGE_NOW', 'temp_deciC': 'TEMP',
                      'soc': 'CAPACITY', 'input_limit_ua': 'INPUT_CURRENT_LIMIT'}.items():
        assert int(props['POWER_SUPPLY_' + prop]) == sample[key]
    assert props['POWER_SUPPLY_STATUS'] == sample['status']
    assert props['POWER_SUPPLY_HEALTH'] == sample['health'] == 'Good'
    assert props['POWER_SUPPLY_PRESENT'] == '1'
    assert 100 <= sample['temp_deciC'] < 420
    assert 3400000 <= sample['voltage_uv'] <= 4440000
    assert 0 <= sample['soc'] <= 100
    if index > 1:
        assert abs(sample['soc'] - samples[index - 2]['soc']) <= 3
    scan = p.inspect(sections['journal'], boot, base, sample['uptime_s'])
    assert scan['rows'] == sample['kernel_rows'] and not scan['fault_counts']
    gpu = 'adreno 3d00000.gpu: [drm:adreno_request_fw] *ERROR* failed to load a740_sqe.fw'
    assert all(s['message'] == gpu for s in scan['suspects'])
    if scan['suspects']:
        rows = [json.loads(line) for line in sections['journal'].splitlines()]
        positions = [i for i, row in enumerate(rows) if row['MESSAGE'] == gpu]
        assert len(positions) == 1 and positions[0] > 0
        assert rows[positions[0] - 1]['MESSAGE'] == 'adreno 3d00000.gpu: Direct firmware load for qcom/a740_sqe.fw failed with error -2'
        known_gpu_count += 1
    if 'observation_s' in sample:
        observed.append(sample)

target = 1200 if phase == 'charging' else 150
assert observed and summary['window_s'] >= target
assert observed[-1]['observation_s'] >= target
assert all(s['online'] == (1 if phase == 'charging' else 0) for s in observed)
elapsed = (dt.datetime.fromisoformat(observed[-1]['utc']) - dt.datetime.fromisoformat(observed[0]['utc'])).total_seconds()
assert elapsed >= target - 2 and observed[-1]['uptime_s'] - observed[0]['uptime_s'] >= target - 2
report = dict(phase=phase, verdict='passed bounded observation and raw evidence reconciliation',
              boot_id=boot, window_s=summary['window_s'], raw_sample_span_s=round(elapsed, 3),
              samples=len(samples), observation_samples=len(observed), first=observed[0], last=observed[-1],
              kernel_fault_counts={}, failed_units=[], raw_journal_samples_verified=len(samples),
              known_optional_gpu_missing_firmware_samples=known_gpu_count)
for field in ('current_ua', 'voltage_uv', 'temp_deciC', 'soc'):
    report[field + '_range'] = [min(s[field] for s in observed), max(s[field] for s in observed)]
if phase == 'charging':
    assert all(s['status'] in ('Charging', 'Full') for s in observed)
    assert sum(s['current_ua'] for s in observed) > 0
    assert observed[0]['soc'] < 100 and observed[-1]['soc'] > observed[0]['soc']
    discharge = json.loads((root / 'battery-only/acceptance.json').read_text())
    assert discharge['current_ua_range'][1] < 0
    report.update(current_sign='negative discharge -> positive net charging',
                  positive_current_samples=sum(s['current_ua'] > 0 for s in observed),
                  soc_rise=observed[-1]['soc'] - observed[0]['soc'],
                  actual_pd_contract_measured=False, measured_vbus_ibus_available=False,
                  plug_out_and_final_acceptance_pending=True)
else:
    assert all(s['status'] == 'Discharging' and s['current_ua'] < 0 for s in observed)
    report['current_sign'] = 'negative=actual unplugged discharge'
out = folder / 'raw-evidence-audit.json'
assert not out.exists()
p.write_json(out, report)
print(json.dumps(report, indent=2))
