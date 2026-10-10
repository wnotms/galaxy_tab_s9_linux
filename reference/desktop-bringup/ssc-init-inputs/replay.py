#!/usr/bin/env python3
"""Offline Test389 initialization-input replay; writes only a new host directory."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[3]
TEST = ROOT / 'reference/boot-tests/test-389-ssc-rpc-return-capacity'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replay(output):
    seal = json.loads((TEST / 'RESULT_SHA256.json').read_text())
    inputs = {}

    def original(name):
        path = TEST / name
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if seal[name] != sha:
            raise ValueError('original evidence hash mismatch: ' + name)
        inputs[str(path.relative_to(ROOT))] = sha
        return data

    evidence_module = load('init_return_evidence', ROOT / 'userspace/sensors/rpc_return_evidence.py')
    mapping_module = load('init_socinfo', ROOT / 'userspace/sensors/map-socinfo.py')
    for path in ('userspace/sensors/rpc_return_evidence.py', 'userspace/sensors/map-socinfo.py'):
        inputs[path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    snapshot = json.loads(original('candidate-acceptance/current-state.txt'))['native_socinfo']
    mapped = mapping_module.translate(snapshot)
    if mapped != json.loads(original('candidate-acceptance/native-mapping.json')):
        raise ValueError('native mapping differs from original')
    raw = original('runtime-discovery/discovery-unit-journal.txt').decode()
    frames = evidence_module.inspect(raw, snapshot['boot_id'])
    if not frames['complete']:
        raise ValueError('original journal cannot be attributed/decoded completely')

    def identity(data):
        return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    expected = {'/sys/devices/soc0/' + name: identity(value.encode())
                for name, value in mapped.items()}
    package = json.loads(original('PACKAGE.json'))
    asset = package['artifacts']['sensor-assets.tar.gz']
    archive = ROOT / asset['path']
    archive_id = identity(archive.read_bytes())
    if archive_id != {key: asset[key] for key in ('bytes', 'sha256')}:
        raise ValueError('registered stock asset archive changed')
    inputs[asset['path']] = archive_id['sha256']
    manifest = json.loads(original('asset-manifest.json'))
    prefix = 'usr/share/qcom/sm8550/Samsung/gts9wifi/sensors/'
    with tarfile.open(archive) as tar:
        for leaf, virtual in (
                ('sns_reg.conf', '/vendor/etc/sensors/sns_reg_config'),
                ('sns_reg_version', '/mnt/vendor/persist/sensors/registry/sns_reg_version')):
            members = [m for m in tar.getmembers() if m.name == prefix + leaf]
            if len(members) != 1 or not members[0].isfile():
                raise ValueError('missing/duplicate/nonregular initialization asset')
            data = tar.extractfile(members[0]).read()
            expected[virtual] = identity(data)
            if expected[virtual] != {key: manifest[prefix + leaf][key]
                                     for key in ('bytes', 'sha256')}:
                raise ValueError('initialization asset does not match registered manifest')

    result = evidence_module.file_contents(frames, expected)
    registry = evidence_module.registry_contents(frames, manifest)
    if not registry['complete'] or registry['expected_nonempty_groups'] != 178:
        raise ValueError('existing exact registry replay regressed')
    result.update(boot_id=snapshot['boot_id'], device_operations=False,
                  inputs_sha256=inputs, expected=expected,
                  matching_returned_inputs=sum(s['returned_bytes_match'] for s in result['sessions']),
                  completed_input_sessions=sum(s['content_matches'] for s in result['sessions']),
                  registry_replay=registry,
                  verdict='INIT_BYTES_MATCH_CONFIG_SESSION_UNCLOSED_SSC_NOT_PROVED')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.output)
    print(json.dumps({key: result[key] for key in (
        'verdict', 'matching_returned_inputs', 'completed_input_sessions', 'complete')}))
