"""Test275 evidence only; never grants charging permission or accesses hardware."""
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_stability_evidence as evidence

spec = importlib.util.spec_from_file_location('passive_baseline_gate', ROOT / 'reference/boot-tests/test-271-baseline-passive-startup/gate.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

CONTEXT = re.compile(r'arm-smmu 15000000.iommu: Unhandled context fault: fsr=0x402, iova=(0x[0-9a-f]+), fsynr=0x660021, cbfrsynra=0x1c00, cb=9')
SYNDROME = 'arm-smmu 15000000.iommu: FSYNR0 = 00660021 [S1CBNDX=102 PNU PLVL=1]'
HEADER = dict(format='sm5440-fresh-observer-v1', maximum_calls='8', interval_ms='1000', PPS_authorized='0', pump_ON_authorized='0', independently_calibrated='0')
FIELDS = {'row', 'request_ms', 'return_ms', 'provider_status', 'status', 'usable', 'acquisition_ms', 'raw_vbus_uv', 'raw_vbat_uv', 'raw_ibus_ua', 'raw_die_decic', 'raw_online'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identity(sec, plan, notes, boot=None):
    current = evidence.canonical_boot_id(sec['boot'])
    require(boot is None or current == boot, 'boot changed')
    ids = sec['identity'].splitlines()
    require(len(ids) == 2 and ids[0].split()[0] == plan['config_sha256'] and ids[1].split()[0] == notes, 'config/notes identity')
    require(sec['cmdline'].strip() == plan['runtime_cmdline'], 'runtime cmdline')
    require(sec['services'].splitlines() == ['active'] * 3 and not sec['failed'].strip(), 'service failure')
    require(sec['dcc'].strip() == 'absent', 'DCC missing/restored')
    require('usb0' in sec['network'] and '169.254.42.1/16' in sec['network'], 'device NCM absent')
    value = baseline.diagnostic_sample(sec)
    require(all(value['snapshot'][k] == v for k, v in plan['protection'].items()), 'protection changed')
    return current, value


def observer(raw):
    header, rows = {}, []
    for line in raw.splitlines():
        if line.startswith('row='):
            pairs = [x.split('=', 1) for x in line.split()]
            require(len(pairs) == len(FIELDS) and {x[0] for x in pairs} == FIELDS, 'row fields')
            rows.append({k: int(v) for k, v in pairs})
        else:
            k, sep, v = line.partition('=')
            require(sep and k not in header, 'header malformed/duplicate')
            header[k] = v
    require(set(header) == set(HEADER) | {'state', 'count'} and all(header[k] == v for k, v in HEADER.items()), 'observer contract')
    state, count = int(header['state']), int(header['count'])
    require(state in (0, 1, 2, 3) and 0 <= count <= 8 and count == len(rows), 'state/count')
    failures = []
    for i, row in enumerate(rows, 1):
        require(row['row'] == i and row['request_ms'] > 0 and row['return_ms'] >= row['request_ms'], 'row chronology')
        if i > 1:
            require(row['request_ms'] >= rows[i-2]['return_ms'] + 1000, 'call interval')
        require(row['provider_status'] <= 0 and row['status'] <= 0 and row['usable'] == int(row['status'] == 0), 'signed status/usable')
        if row['provider_status']:
            require(row['status'] == row['provider_status'], 'provider refusal masked')
        if row['status']:
            failures.append(i)
            require(i == count and state == 2, 'request after first refusal')
        else:
            require(row['provider_status'] == 0 and row['return_ms'] - row['request_ms'] <= 100, 'delivery deadline')
            require(row['request_ms'] <= row['acquisition_ms'] <= row['return_ms'] and row['return_ms'] - row['acquisition_ms'] <= 100, 'fresh acquisition')
            require(row['raw_online'] == 1 and row['raw_ibus_ua'] == 0, 'OFF sample')
            # Test275 uses PC 5V only; provider's generic upper bound is 9.5V.
            require(4500000 <= row['raw_vbus_uv'] <= 5500000 and 3500000 <= row['raw_vbat_uv'] < 4300000 and 225 <= row['raw_die_decic'] < 420, 'sample bound')
    require((state != 1 or count == 8) and (state != 2 or failures), 'terminal state inconsistent')
    durations = [r['return_ms'] - r['request_ms'] for r in rows if r['status'] == 0]
    return dict(state=state, count=count, rows=rows, first_refusal=failures[0] if failures else None,
                successful_calls=len(durations), delivery_ms_min=min(durations, default=None), delivery_ms_max=max(durations, default=None),
                acquisition_outcome='REFUSED' if failures else 'EIGHT_FRESH_DELIVERIES' if state == 1 else 'INCOMPLETE',
                independently_calibrated=False, charging_authorized=False)


def journal(raw, boot, known, uptime, full=True):
    # Keep the global parser strict. Local attribution is diagnostic scope only:
    # <=10 context + <=10 syndrome messages, priority3, first200ms, same known
    # SID/context/range. Preserve all original suspects and never call them fixed.
    scan = evidence.inspect_journal(raw, boot, known, require_start=full,
        accepted_startup_variants=True, startup_iova_range=(0xb8000000, 0xbab00000),
        accepted_qca_cycles=True, observed_uptime=uptime)
    require(not scan['fault_counts'], 'CPU/kernel failure')
    rows = [json.loads(line) for line in raw.splitlines()]
    classified, counts, unknown = [], {'context': 0, 'syndrome': 0}, []
    for suspect in scan['suspects']:
        row = rows[suspect['row'] - 1] if suspect['row'] is not None else {}
        message = row.get('MESSAGE', '')
        match = CONTEXT.fullmatch(message)
        kind = ('context' if match and 0xb8000000 <= int(match[1], 16) < 0xbab00000 else 'syndrome' if message == SYNDROME else None)
        if kind and int(row.get('PRIORITY', 7)) == 3 and 0 <= int(row['_SOURCE_BOOTTIME_TIMESTAMP']) <= 200000:
            counts[kind] += 1
            classified.append(suspect)
        else:
            unknown.append(suspect)
    require(counts['context'] <= 10 and counts['syndrome'] <= 10 and counts['context'] == counts['syndrome'], 'startup SMMU diagnostic bound')
    require(not unknown, 'new/unclassified kernel suspect')
    require(not any('sm5440-passive' in row['MESSAGE'] and any(word in row['MESSAGE'] for word in ('fault bitmap=', 'ADC fault', 'confirmation failed')) for row in rows), 'passive fault')
    scan.update(unresolved_startup_smmu=classified, unresolved_counts=counts,
                diagnostic_attribution_only=True, stability_clean_claim=False)
    return scan
