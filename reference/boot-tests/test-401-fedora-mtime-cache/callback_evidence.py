"""Independent cache-write observation; historical immutable gates unchanged."""
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


old = load('ssc401_old_callbacks', ROOT/'reference/boot-tests/test-400-fedora-adsp-comparison/callback_evidence.py')
mutation = load('ssc401_mutation', ROOT/'userspace/sensors/registry_mutation_evidence.py')


def validate_before(before, boot, manifest):
    # Empty replay compares every installed byte/mode/mtime before any launch.
    after = dict(before, phase='after')
    frames = dict(complete=True, boot_id=UUID(boot).hex, streams=[])
    result = mutation.replay(frames, boot, before, after, manifest)
    if not result['complete']:
        raise ValueError('before snapshot qualification failed')
    return result


def inspect(raw, boot, metadata, manifest, before, after):
    stats = old.stat.inspect(raw, boot, metadata)
    qualified = {e['virtual_path'] for e in metadata['entries']}
    for index, row in enumerate(json.loads(line) for line in raw.splitlines() if line.strip()):
        if row.get('_SYSTEMD_UNIT') != old.stat.UNIT:
            continue
        match = old.stat.STAT.fullmatch(row.get('MESSAGE', ''))
        if match and match[1].startswith('/vendor/etc/sensors/config/') and match[1] not in qualified:
            stats['faults'].append(dict(row=index, path=match[1], reason='config stat outside unchanged reference'))
    if stats['faults']:
        stats.update(complete=False, verdict='RPC_CONFIG_METADATA_INCOMPLETE_OR_FAILED')
    frames = old.returned.inspect(raw, boot)
    directories = old.readdir.inspect(frames)
    content = mutation.replay(frames, boot, before, after, manifest)
    status = old.statuses(frames)
    faults = [dict(source=name, detail=f) for name, section in
              [('metadata', stats), ('framing', frames), ('content', content), ('status', status)]
              for f in section['faults']]
    faults += [dict(source='readdir', detail=f) for f in directories['faults']
               if f != 'no successful readdir/EOF coverage']
    complete = frames['complete'] and content['complete'] and not faults
    return dict(verdict='OBSERVED_MUTABLE_CALLBACKS_VALID' if complete else 'STOP_CALLBACK_EVIDENCE',
                complete=complete, faults=faults, boot_id=str(UUID(boot)),
                metadata=stats, returned=frames, readdir=directories, contents=content, status=status,
                old_call_totals_required=False, SSC_publication_proved=False,
                metadata_coverage_complete=stats['complete'],
                readdir_EOF_coverage_complete=directories['complete'],
                full_file_read_coverage_claimed=False,
                physical_persist_accessed=False)
