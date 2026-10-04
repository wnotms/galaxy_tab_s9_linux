#!/usr/bin/env python3
"""Qualify native pack producer/session integration; never deploy or contact hardware."""
from pathlib import Path
import difflib
import gzip
import hashlib
import json
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
RECORD = Path(__file__).resolve().parent
OUT = ROOT / 'out/kernel-x710-pack-observation'
BUILD = ROOT / '.work/build/linux-out-x710-308-passive'
TREE = ROOT / '.work/build/linux-src-x710-charging'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config(path):
    result = {}
    for line in path.read_text().splitlines():
        if line.startswith('CONFIG_'):
            key, value = line.split('=', 1)
            result[key] = value
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            result[line.split()[1]] = 'n'
    return result


def normalized(info):
    if info.issym() or info.islnk():
        return None
    info.uid = info.gid = info.mtime = 0
    info.uname = info.gname = 'root'
    return info


def archive_files(path, release):
    with tarfile.open(path) as tar:
        return {str(Path(item.name).relative_to(release)):
                hashlib.sha256(tar.extractfile(item).read()).hexdigest()
                for item in tar.getmembers() if item.isfile()}


def main():
    before = json.loads((RECORD / 'inputs-before.json').read_text())
    for item in before['formal_artifacts'].values():
        assert sha(ROOT / item['path']) == item['sha256'], item['path']
    for group in ('preserved_sources', 'changed_sources'):
        for name, expected in before[group].items():
            assert sha(ROOT / name) == expected, name
    protected = {}
    paths = subprocess.check_output(
        ['git', 'ls-files', 'kernel', 'rootfs-overlay', 'userspace',
         'scripts/build-kernel.sh', 'scripts/prepare-kernel.sh'], cwd=ROOT, text=True)
    for name in paths.splitlines():
        if name in ('kernel/drivers/sm5714-battery.c', 'kernel/drivers/sm5714-stage2.h', 'kernel/drivers/x710-pd-session.c'):
            continue
        expected = subprocess.check_output(['git', 'show', before['base_revision'] + ':' + name], cwd=ROOT)
        assert (ROOT / name).read_bytes() == expected, name
        protected[name] = hashlib.sha256(expected).hexdigest()
    compiled = {}
    for name, folder in [('sm5714_usbpd.c', 'usb/typec/tcpm'),
                         ('sm5714-stage2.h', 'usb/typec/tcpm'),
                         ('sm5714-battery.c', 'power/supply'),
                         ('sm5714-stage2.h', 'power/supply'),
                         ('sm5440-direct.c', 'power/supply'),
                         ('x710-pd-session.c', 'power/supply')]:
        compiled[folder + '/' + name] = ((ROOT / 'kernel/drivers' / name).read_bytes() ==
                                         (TREE / 'drivers' / folder / name).read_bytes())
        assert compiled[folder + '/' + name], name
    current = config(OUT / 'config')
    deltas = {}
    for label, folder in [('Test316', 'kernel-x710-316-fixed-contract'),
                          ('accepted311', 'kernel-x710-308-passive')]:
        prior = ROOT / 'out' / folder / 'config'
        values = config(prior)
        deltas[label] = {key: [values.get(key, 'absent'), current.get(key, 'absent')]
                         for key in sorted(values.keys() | current.keys())
                         if values.get(key) != current.get(key)}
        (RECORD / ('config-vs-' + label + '.diff')).write_text(''.join(
            difflib.unified_diff(prior.read_text().splitlines(True),
                                (OUT / 'config').read_text().splitlines(True),
                                fromfile=str(prior.relative_to(ROOT)),
                                tofile=str((OUT / 'config').relative_to(ROOT)))))
    # Kconfig depends on !X710_CHARGING_POLICY: it disappears rather than
    # retaining a '# ... is not set' line under this existing offline profile.
    assert deltas['Test316'] == {'CONFIG_SM5440_ADC_CONDITION_TEST': ['y', 'absent'],
                                   'CONFIG_X710_CHARGING_POLICY': ['n', 'y']}
    assert deltas['accepted311'] == {'CONFIG_SM5440_ADC_CONDITION_TEST': ['n', 'absent'],
                                    'CONFIG_X710_CHARGING_POLICY': ['n', 'y']}
    assert ((OUT / 'sm8550-samsung-gts9wifi.dtb').read_bytes() ==
            (ROOT / 'out/kernel-x710-308-passive/sm8550-samsung-gts9wifi.dtb').read_bytes())
    assert current['CONFIG_HVC_DCC'] == 'n' and current['CONFIG_X710_CHARGING_POLICY'] == 'y'
    assert 'CONFIG_SM5440_ADC_CONDITION_TEST' not in current
    for key in ('CONFIG_USER_NS', 'CONFIG_POSIX_MQUEUE', 'CONFIG_BATTERY_SM5714',
                'CONFIG_QCOM_SPMI_ADC5_GEN3'):
        assert current[key] == 'y', key
    embedded = subprocess.check_output([str(TREE / 'scripts/extract-ikconfig'), str(OUT / 'Image.gz')])
    assert embedded == (OUT / 'config').read_bytes()
    subprocess.run(['llvm-objcopy', '--dump-section', '.notes=' + str(OUT / 'kernel-notes.bin'),
                    str(BUILD / 'vmlinux'), '/dev/null'], check=True)
    release = (OUT / 'kernel.release').read_text().strip()
    module_dir = OUT / 'modules-root/lib/modules' / release
    modules = {str(p.relative_to(module_dir)): sha(p)
               for p in sorted(module_dir.rglob('*')) if p.is_file()}
    assert len(modules) == 181
    archive = OUT / 'modules-x710.tar.gz'
    # Same normalized archive encoding as scripts/audit-x710-charging-build.py.
    with archive.open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=3) as gz:
            with tarfile.open(fileobj=gz, mode='w|') as tar:
                tar.add(module_dir, arcname=release, filter=normalized)
    assert archive_files(archive, release) == modules
    previous = archive_files(ROOT / 'out/kernel-x710-316-fixed-contract/modules-x710.tar.gz', release)
    assert modules.keys() == previous.keys()
    module_delta = {key: [previous[key], modules[key]] for key in modules
                    if previous[key] != modules[key]}
    symbols = subprocess.check_output(['llvm-nm', str(BUILD / 'vmlinux')], text=True)
    linked = [line for line in symbols.splitlines() if line.split()[-1] in
              ('sm5714_battery_read_pack', '__ksymtab_sm5714_battery_read_pack',
               'sm5714_pd_read_owned_snapshot', '__ksymtab_sm5714_pd_read_owned_snapshot',
               'x710_pd_off_roundtrip', '__ksymtab_x710_pd_off_roundtrip')]
    assert len(linked) == 6
    names = ('Image.gz', 'sm8550-samsung-gts9wifi.dtb', 'config',
             'kernel-notes.bin', 'modules-x710.tar.gz', 'kernel.release')
    artifacts = {name: {'path': str((OUT / name).relative_to(ROOT)),
                        'bytes': (OUT / name).stat().st_size, 'sha256': sha(OUT / name)}
                 for name in names}
    result = dict(valid=True, config_diff=deltas, DTB_diff=[],
                  formal_previous_artifacts_preserved=True, protected_sources=protected,
                  compiled_source_matches=compiled, module_file_count=len(modules),
                  module_set_unchanged=True, module_hash_changes=module_delta, modules=modules,
                  native_producer_consumer_linked_symbols=linked, artifacts=artifacts,
                  pin=subprocess.check_output(['git', '-C', str(TREE), 'rev-parse', 'HEAD'], text=True).strip(),
                  embedded_config_identical=True, pump_activation_available=False,
                  PPS_requests_executed=False, software_ocp_verified=False,
                  physical_test_registered=False)
    (RECORD / 'artifact-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('valid', 'config_diff', 'DTB_diff',
                                                 'module_file_count', 'native_producer_consumer_linked_symbols')}))
    print('Protected:', len(protected), '; changed module metadata:', list(module_delta))


if __name__ == '__main__':
    main()
