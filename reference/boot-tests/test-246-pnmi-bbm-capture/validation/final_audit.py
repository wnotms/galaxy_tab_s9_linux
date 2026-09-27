"""Read-only audit of the closed test246 archive; never contacts the tablet."""
import ast
import json
import re
from pathlib import Path

P = Path(__file__).resolve().parents[1]

def read_json(path):
    return json.loads((P / path).read_text())

def manifest(name):
    result = {}
    for line in (P / 'validation' / name).read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        assert name not in result
        result[name] = digest
    assert len(result) == 181
    return result

summary = {'hardware_contacted': False, 'cpu_stall_repair_established': False}
for phase, transport, name, expected_boot in (
    ('target-run', 'target-transport', 'candidate-module-checksums.txt',
     '2de14bb7-4cd7-4b76-a78c-ad3766d187fa'),
    ('production', 'production', 'original-module-checksums.txt',
     'f231faf9-fd13-468d-b6ec-58b8ade46d8e'),
):
    verdict = read_json(phase + '/verdict.json')
    assert verdict['verdict'] == 'clean_window'
    assert verdict['boot_id'] == expected_boot
    assert 120 <= verdict['uptime'] < 121
    assert verdict['failed_units'] == []
    assert verdict['overall_health_passed'] is True
    lines = (P / phase / 'module-hashes.txt').read_text().splitlines()
    assert lines[0] == lines[-1] == expected_boot
    actual = {row.split()[1].removeprefix('/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty/'): row.split()[0]
              for row in lines if re.match(r'^[a-f0-9]{64}\s', row)}
    assert actual == manifest(name)
    rows = [json.loads(line) for line in (P / phase / 'final-json.txt').read_text().splitlines()]
    assert len(rows) == verdict['final_rows'] == verdict['source_timestamp_rows']
    assert all(row['_BOOT_ID'] == expected_boot.replace('-', '') and
               '_SOURCE_BOOTTIME_TIMESTAMP' in row for row in rows)
    services = (P / transport / 'transport-services.txt').read_text().splitlines()
    assert services[0] == expected_boot and services[2:6] == ['active'] * 4
    assert any(row.startswith('usb0 ') and '169.254.42.1/16' in row for row in services)
    assert read_json(transport + '/transport-services.json')['status'] == 0
    assert read_json(transport + '/ssh-banner.json')['status'] == 0
    assert (P / transport / 'ssh-banner.txt').read_text().startswith('SSH-2.0-')
    summary[phase] = {'boot_id': expected_boot, 'uptime': verdict['uptime'],
                      'module_files_verified': len(actual), 'journal_rows': len(rows),
                      'services_active': 4, 'ssh_banner': True,
                      'authenticated_ssh_shell_tested': False}

expected = {
    'boot': '71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d',
    'vendor_boot': '49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9',
    'init_boot': '1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0',
    'dtbo': 'c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3',
    'vbmeta': '9844859b45716a2a098c96cd38b15bb378e784dab34843d1edcd2704236d36e4',
}
restored = read_json('restore/images-verified.json')
assert restored['restore'] is True and restored['all_five_hashes'] == expected
raw = (P / 'restore/all-partitions.txt').read_text()
for name, digest in expected.items():
    assert any(line.split()[0] == digest and line.split()[1].endswith('/' + name)
               for line in raw.splitlines())
assert read_json('module-restore/modules-verified.json')['restore'] is True
assert (P / 'module-restore/swap.txt').read_text().count(': OK') == 362
assert (P / 'module-cleanup/verified-remove.txt').read_text().count(': OK') == 181
assert read_json('module-cleanup/verified-remove.json')['status'] == 0
assert (P / 'production/profile.txt').read_text().splitlines() == ['0'] * 5 + ['helper_absent=0']
notes = read_json('target/loaded-module-notes-check.json')
assert notes['boot_id'] == summary['target-run']['boot_id']
assert len(notes['modules']) == 3 and all(row['matches_candidate_note'] for row in notes['modules'])
for source in (P / 'runner').glob('*.py'):
    ast.parse(source.read_text(), filename=str(source))
summary['original_partitions_verified'] = list(expected)
summary['original_profile_restored'] = True
summary['candidate_directory_verified_before_removal'] = True
summary['runner_syntax_passed'] = True
print(json.dumps(summary, indent=2))
