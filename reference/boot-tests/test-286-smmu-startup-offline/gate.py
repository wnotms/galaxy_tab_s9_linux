"""Bounded display-stream startup attribution, not stability/charging approval.

Source provenance and exact DTB mapping are recorded alongside this profile.
Frozen Test275/283 and the shared production parser remain unchanged.
"""
import importlib.util
import json
from pathlib import Path
import re

_path = Path(__file__).resolve().parent.parent / 'test-283-startup-adc-event-offline/gate.py'
_spec = importlib.util.spec_from_file_location('frozen283_smmu_gate', _path)
frozen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(frozen)
baseline, evidence = frozen.baseline, frozen.evidence
require, identity, wifi_address = frozen.require, frozen.identity, frozen.wifi_address

PREFIX = 'arm-smmu 15000000.iommu: '
CONTEXT = re.compile(re.escape(PREFIX) +
    r'Unhandled context fault: fsr=0x402, iova=(0x[0-9a-f]+), '
    r'fsynr=(0x[0-9a-f]+), cbfrsynra=0x1c00, cb=9')
FSR = PREFIX + 'FSR    = 00000402 [Format=2 TF], SID=0x1c00'
SYNDROME = re.compile(re.escape(PREFIX) +
    r'FSYNR0 = ([0-9a-f]{8}) \[S1CBNDX=(\d+) PNU PLVL=1\]')
# 98/99 were already in the shared startup profile; 102 in Test275/283;
# 103 is the independently recorded Test284 restored-baseline value.
OBSERVED_TAGS = frozenset((98, 99, 102, 103))


def startup_triplets(rows, full):
    records = [(i + 1, row) for i, row in enumerate(rows)
               if 'arm-smmu' in row['MESSAGE'] and any(word in row['MESSAGE']
                   for word in ('Unhandled context fault:', 'FSR    =', 'FSYNR0 ='))]
    if not records:
        return []
    require(full and len(records) % 3 == 0 and len(records) <= 30,
            'startup SMMU incomplete/count/incremental')
    triplets, tags = [], set()
    for offset in range(0, len(records), 3):
        group = records[offset:offset + 3]
        context = CONTEXT.fullmatch(group[0][1]['MESSAGE'])
        syndrome = SYNDROME.fullmatch(group[2][1]['MESSAGE'])
        require(context is not None and group[1][1]['MESSAGE'] == FSR and syndrome is not None,
                'startup SMMU stream/fields/order')
        iova, fsynr = (int(value, 16) for value in context.groups())
        tag = fsynr >> 16
        require(tag in OBSERVED_TAGS and fsynr == (tag << 16) | 0x21 and
                int(syndrome[1], 16) == fsynr and int(syndrome[2]) == tag,
                'startup SMMU tag/flags disagreement')
        require(0xb8000000 <= iova < 0xbab00000, 'startup SMMU outside splash')
        times = [int(row['_SOURCE_BOOTTIME_TIMESTAMP']) for _, row in group]
        require(all(int(row['PRIORITY']) == 3 for _, row in group) and
                0 <= times[0] <= times[1] <= times[2] <= 200000 and
                times[2] - times[0] <= 1000, 'startup SMMU time/priority')
        if triplets:
            require(times[0] >= triplets[-1]['last_source_us'], 'startup SMMU chronology')
        tags.add(tag)
        require(len(tags) == 1, 'startup SMMU mixed tags')
        triplets.append(dict(rows=[i for i, _ in group], iova=hex(iova),
                             fsynr=hex(fsynr), s1cbndx=tag, first_source_us=times[0],
                             last_source_us=times[2], raw=[row for _, row in group],
                             subsystem='MDSS display stream', root_cause='UNKNOWN'))
    return triplets


def journal(raw, boot, known, uptime, current, plan, notes, full=True):
    identity(current, plan, notes, boot)
    scan = evidence.inspect_journal(raw, boot, known, require_start=full,
        accepted_startup_variants=True, startup_iova_range=(0xb8000000, 0xbab00000),
        accepted_qca_cycles=True, observed_uptime=uptime)
    require(not scan['fault_counts'], 'CPU/kernel failure')
    rows = [json.loads(line) for line in raw.splitlines()]
    triplets = startup_triplets(rows, full)
    classified_rows = {number for triplet in triplets for number in triplet['rows']}
    require(all(suspect['row'] in classified_rows for suspect in scan['suspects']),
            'new/unclassified kernel suspect')
    startup = frozen._retained_startup(rows, full)
    scan.update(unresolved_startup_smmu=scan['suspects'],
                unresolved_counts={'context': len(triplets), 'syndrome': len(triplets)},
                smmu_triplets=triplets, diagnostic_attribution_only=True,
                stability_clean_claim=False, retained_startup_confirmation=startup,
                current_health_verified=True, charging_authorized=False,
                classification_profile='Test286 complete bounded display startup triplets')
    return scan
