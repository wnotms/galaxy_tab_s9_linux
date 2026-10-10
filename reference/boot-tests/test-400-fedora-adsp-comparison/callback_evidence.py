"""Validate observed new-firmware callbacks without predicting old call totals.

All byte, framing, status, metadata and deterministic-reply checks remain.
Unrequested reference files are coverage gaps, not fabricated callback faults.
Historical parsers and their stricter original completeness policy are unchanged.
"""
import importlib.util
import json
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stat = load('ssc400_stat', ROOT/'userspace/sensors/rpc_stat_evidence.py')
returned = load('ssc400_return', ROOT/'userspace/sensors/rpc_return_evidence.py')
readdir = load('ssc400_readdir', ROOT/'userspace/sensors/rpc_readdir_evidence.py')
missing = load('ssc400_known_missing', ROOT/'reference/boot-tests/test-399-ssc-smp2p-provider/missing_file_evidence.py')


def statuses(frames):
    faults, known = [], []
    for stream in frames['streams']:
        for call in stream['calls']:
            req = call.get('response_to')
            if req is None:
                continue
            target = (stream['unit'] == 'hexagonrpcd-adsp-sensorspd.service' and
                      req.get('handle') == 1 and req.get('scalars') == 0x13050100 and
                      req.get('buffers_hex') == missing.EXPECTED and
                      req.get('output_capacities') == [4])
            if target and call['status'] == 69 and call['transport_return'] == 0:
                known.append(dict(sequence=call['sequence'], pid=stream['pid'], status=69))
            elif target or call['status'] or call['transport_return']:
                faults.append(dict(sequence=call['sequence'], status=call['status'],
                                   transport_return=call['transport_return'],
                                   reason='unqualified failed callback'))
    return dict(complete=not faults, faults=faults, known_missing_calls=known,
                known_missing_exercised=bool(known), observed_known_missing_count=len(known))


def inspect(raw, boot, metadata, manifest):
    UUID(boot)
    stats = stat.inspect(raw, boot, metadata)
    qualified = {entry['virtual_path'] for entry in metadata['entries']}
    for index, row in enumerate(json.loads(line) for line in raw.splitlines() if line.strip()):
        if row.get('_SYSTEMD_UNIT') != stat.UNIT:
            continue
        message = row.get('MESSAGE', '')
        match = stat.STAT.fullmatch(message)
        if match and match[1].startswith('/vendor/etc/sensors/config/') and match[1] not in qualified:
            stats['faults'].append(dict(row=index, path=match[1], reason='config stat outside unchanged reference'))
    if stats['faults']:
        stats.update(complete=False, verdict='RPC_CONFIG_METADATA_INCOMPLETE_OR_FAILED')
    frames = returned.inspect(raw, boot)
    directories = readdir.inspect(frames)
    content = returned.registry_contents(frames, manifest)
    status = statuses(frames)
    faults = ([dict(source='metadata', detail=f) for f in stats['faults']]
              + [dict(source='framing', detail=f) for f in frames['faults']]
              + [dict(source='content', detail=f) for f in content['faults']]
              + [dict(source='status', detail=f) for f in status['faults']])
    for fault in directories['faults']:
        if fault != 'no successful readdir/EOF coverage':
            faults.append(dict(source='readdir', detail=fault))
    # Metadata/content completeness retains the full unchanged reference. Do
    # not rewrite it to only requested files to make the coverage look complete.
    complete = frames['complete'] and not faults
    return dict(verdict='OBSERVED_CALLBACKS_VALID' if complete else 'STOP_CALLBACK_EVIDENCE',
                complete=complete, faults=faults, boot_id=str(UUID(boot)),
                metadata=stats, returned=frames, readdir=directories,
                contents=content, status=status,
                old_call_totals_required=False, SSC_publication_proved=False,
                metadata_coverage_complete=stats['complete'],
                registry_coverage_complete=content['complete'],
                readdir_EOF_coverage_complete=directories['complete'])
