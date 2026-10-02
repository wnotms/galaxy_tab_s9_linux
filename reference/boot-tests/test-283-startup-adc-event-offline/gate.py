"""Offline bounded startup classification. No device operations or charge grant.

Keep Test275's frozen gates intact. Only INT4 ADC_UPDATED bit0 varies in this
new profile; Samsung sm5440_charger.h and sm5440-hw.h define that bit. Every
other literal/raw/protection/time condition is retained. A current identity
and healthy OFF snapshot are mandatory, not merely a recovery log message.
"""
import importlib.util
import json
from pathlib import Path
import re

_path = Path(__file__).resolve().parent.parent / 'test-275-passive-fresh-acquisition/gate.py'
_spec = importlib.util.spec_from_file_location('frozen275_startup_gate', _path)
frozen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(frozen)
ROOT, baseline, evidence = frozen.ROOT, frozen.baseline, frozen.evidence
require, identity, wifi_address = frozen.require, frozen.identity, frozen.wifi_address
CONTEXT, SYNDROME, PASSIVE_PREFIX = frozen.CONTEXT, frozen.SYNDROME, frozen.PASSIVE_PREFIX

STARTUP_FAULT = re.compile(
    re.escape(PASSIVE_PREFIX) +
    r'passive fault bitmap=0x80 INT=00 00 62 (?P<int4>[0-9a-f]{2}) '
    r'STATUS=00 00 20 00 INT4-disable=00 INT4-wait=01 mode=01/01 '
    r'CNTL2=f2 VBUSCNTL=e7 VBATCNTL=37 PRTNCNTL=fe '
    r'ADC=(?P<adc>(?:[0-9a-f]{2} ){10}[0-9a-f]{2}) '
    r'VBUS=(?P<vbus>\d+)uV VBAT=(?P<vbat>\d+)uV IBUS=0uA die=(?P<die>\d+) deciC')


def _retained_startup(rows, full):
    faults = [r for r in rows if 'sm5440-passive' in r['MESSAGE'] and
              any(w in r['MESSAGE'] for w in ('fault bitmap=', 'ADC fault', 'confirmation failed'))]
    if not faults:
        return None
    require(full and len(faults) == 1, 'new/repeated passive fault')
    fault = faults[0]
    match = STARTUP_FAULT.fullmatch(fault['MESSAGE'])
    require(match is not None and int(fault['PRIORITY']) == 4, 'unclassified passive fault')
    int4 = int(match['int4'], 16)
    # Vendor INT4 ADCUPDATED0 is completion, not watchdog2/timer1. Never
    # generalize to an arbitrary bitmask or ignore reserved/fault bits.
    require(int4 in (0, 1), 'INT4 watchdog/timer/unknown bit')
    waiting = [r for r in rows if r['MESSAGE'] == PASSIVE_PREFIX +
               'passive startup REVBLK awaiting two fresh confirmations']
    done = [r for r in rows if r['MESSAGE'] == PASSIVE_PREFIX +
            'passive startup REVBLK confirmed inactive; event retained']
    require(len(waiting) == len(done) == 1, 'startup confirmation absent/ambiguous')
    require(int(waiting[0]['PRIORITY']) == 4 and int(done[0]['PRIORITY']) == 6,
            'startup confirmation priority')
    t0, tf, t1 = [int(r['_SOURCE_BOOTTIME_TIMESTAMP']) for r in (waiting[0], fault, done[0])]
    require(0 < t0 <= tf <= 1000000 and tf-t0 <= 100000 and 0 < t1-tf <= 5000000,
            'startup confirmation deadline')
    adc = [int(x, 16) for x in match['adc'].split()]
    raw13 = lambda offset: (adc[offset] << 5) | (adc[offset+1] >> 3)
    vbus, vbat, die = (int(match[k]) for k in ('vbus', 'vbat', 'die'))
    require(vbus == 4096000+raw13(0)*1000 and vbat == 2048000+raw13(9)*500 and
            raw13(4) == 0 and die == 225+adc[8]*5, 'startup raw/decoded disagreement')
    require(4500000 <= vbus <= 5500000 and 3500000 <= vbat < 4300000 and
            225 <= die < 420, 'startup unsafe ADC')
    return dict(fault=fault, waiting=waiting[0], confirmed=done[0],
                confirmation_seconds=(t1-tf)/1000000, int4_adc_updated=bool(int4),
                event_retained=True, charging_authorized=False,
                current_healthy_snapshot_required=True)


def journal(raw, boot, known, uptime, current, plan, notes, full=True):
    """Requires the same boot's complete current identity/health packet.

    Test275's journal/CPU/SMMU gates are preserved below, without mutating its
    module globals or weakening the shared production evidence parser.
    """
    identity(current, plan, notes, boot)
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
        kind = ('context' if match and 0xb8000000 <= int(match[1], 16) < 0xbab00000 else
                'syndrome' if message == SYNDROME else None)
        if kind and int(row.get('PRIORITY', 7)) == 3 and 0 <= int(row['_SOURCE_BOOTTIME_TIMESTAMP']) <= 200000:
            counts[kind] += 1
            classified.append(suspect)
        else:
            unknown.append(suspect)
    require(counts['context'] <= 10 and counts['syndrome'] <= 10 and
            counts['context'] == counts['syndrome'], 'startup SMMU diagnostic bound')
    require(not unknown, 'new/unclassified kernel suspect')
    startup = _retained_startup(rows, full)
    scan.update(unresolved_startup_smmu=classified, unresolved_counts=counts,
                diagnostic_attribution_only=True, stability_clean_claim=False,
                retained_startup_confirmation=startup, current_health_verified=True,
                classification_profile='Test283 bounded INT4 ADC_UPDATED only')
    return scan
