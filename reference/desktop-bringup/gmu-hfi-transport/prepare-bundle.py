#!/usr/bin/env python3
"""Offline GPU/native-Escape bundle; keep the accepted non-ADSP vendor image."""
import ast
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'out/boot-bundle-x710-gmu-rpmh'
KERNEL = ROOT / 'out/kernel-x710-gmu-rpmh'
PROVIDER = ROOT / '.work/build/linux-out-x710-308-passive'
commands = []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(path, expected):
    if digest(path) != expected:
        raise ValueError('artifact changed: ' + str(path))
    return path


def run(argv):
    result = subprocess.run(list(map(str, argv)), cwd=ROOT, check=True,
                            capture_output=True, text=True)
    commands.append(dict(argv=list(map(str, argv)), stdout=result.stdout,
                         stderr=result.stderr, returncode=result.returncode))
    return result.stdout


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_assignment(template, staged, name, value):
    source = template.read_text()
    before = ast.parse(source)
    assignment = next(node for node in before.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == name for t in node.targets))
    lines = source.splitlines(keepends=True)
    lines[assignment.lineno-1:assignment.end_lineno] = [name + ' = ' + repr(value) + '\n']
    staged.write_text(''.join(lines))
    def without(tree):
        tree = copy.deepcopy(tree)
        tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == name for t in node.targets))]
        return ast.dump(tree)
    assert without(before) == without(ast.parse(staged.read_text()))
    return dict(path=str(staged.relative_to(ROOT)), sha256=digest(staged),
                template_sha256=digest(template), AST_only_assignment=name)


def main():
    if OUT.exists():
        raise ValueError('bundle exists; never overwrite frozen output')
    audit = json.loads((HERE / 'BUILD_AUDIT.json').read_text())
    for name, item in audit['artifacts'].items():
        checked(ROOT / name, item['sha256'])
    checked(PROVIDER / 'Module.symvers', audit['export_CRC_table_sha256'])
    config, notes = (KERNEL / 'config').read_bytes(), (KERNEL / 'kernel-notes.bin').read_bytes()
    release = (KERNEL / 'kernel.release').read_text().strip()
    assert b'# CONFIG_HVC_DCC is not set\n' in config
    for symbol in ('USER_NS', 'POSIX_MQUEUE', 'KEYBOARD_SAMSUNG_POGO', 'BATTERY_SM5714'):
        assert ('CONFIG_' + symbol + '=y\n').encode() in config
    prior = json.loads((HERE.parent / 'native-socinfo-kernel/INPUT_PAIR_BUILD.json').read_text())
    symbols = {}
    for path in (PROVIDER / 'Module.symvers', ROOT / 'out/ssc-native-input-pair/pen/Module.symvers'):
        for line in path.read_text().splitlines():
            fields = line.split()
            crc, symbol = int(fields[0], 16), fields[1]
            assert symbol not in symbols or symbols[symbol] == crc
            symbols[symbol] = crc
    modules = {}
    for item in prior['results']:
        directory = ROOT / 'out/ssc-native-input-pair' / item['label']
        for name, expected in item['source_hashes'].items():
            checked(directory / name, expected)
        name, expected = next(iter(item['modules'].items()))
        module = checked(ROOT / name, expected)
        imports = run(['modprobe', '--dump-modversions', module]).splitlines()
        assert imports
        for line in imports:
            crc, symbol = line.split()
            assert symbols.get(symbol) == int(crc, 16), symbol
        vermagic = run(['modinfo', '-F', 'vermagic', module]).strip()
        assert vermagic == release + ' SMP preempt mod_unload modversions aarch64'
        modules[item['label']] = dict(path=name, sha256=expected,
                                     imports_checked=len(imports), vermagic=vermagic)

    # Reuse only the pure fixture function; never execute/mutate the old plan.
    fixtures = load(HERE.parent / 'ssc-keyboard-candidate/prepare.py', 'pair_fixtures')
    loaders = {}
    for label in ('pen', 'palm'):
        template = ROOT / 'userspace/gnome' / label / 'load.py'
        profile = load(template, 'template_' + label).PROFILE.copy()
        profile.update(release=release, config_sha256=digest(KERNEL / 'config'),
                       notes_sha256=digest(KERNEL / 'kernel-notes.bin'))
        if label == 'pen':
            profile['module_sha256'] = modules['pen']['sha256']
        else:
            profile.update(pen_sha256=modules['pen']['sha256'],
                           touch_sha256=modules['palm-touch']['sha256'])
        staged = HERE / (label + '-loader.py')
        entry = replace_assignment(template, staged, 'PROFILE', profile)
        entry['profile'] = profile
        entry['mock_checks'] = fixtures.mock_loader(staged, profile, config, notes,
            (ROOT / modules['pen']['path']).read_bytes(),
            (ROOT / modules['palm-touch']['path']).read_bytes())
        loaders[label] = entry

    template = ROOT / 'userspace/gnome/keyboard/select-driver.py'
    identities = load(template, 'mapping_template').IDENTITIES.copy()
    identities['native'] = (digest(KERNEL / 'config'), digest(KERNEL / 'kernel-notes.bin'))
    staged_mapping = HERE / 'select-driver.py'
    mapping = replace_assignment(template, staged_mapping, 'IDENTITIES', identities)
    mapping['identities'] = identities
    # Existing behavioural tests exercise the staged helper, not a rewritten mock.
    existing = load(ROOT / 'tests/test_keyboard_driver_mapping.py', 'mapping_test_source')
    class StagedMappingTests(existing.MappingTests):
        def setUp(self):
            self.m = load(staged_mapping, 'staged_mapping')
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(StagedMappingTests))
    assert result.wasSuccessful() and result.testsRun == 9
    mapping['behavioural_tests'] = dict(tests=9, failures=0, errors=0, skipped=0)
    # Test real candidate identity without replacing the gate constants.
    with tempfile.TemporaryDirectory(prefix='gts9-gmu-mapping-') as tmp:
        root = Path(tmp)
        files = {'proc/sys/kernel/random/boot_id': b'fixture',
                 'etc/machine-id': b'3c2a1b8f2d624db4b5ffdc836050fcf6',
                 'sys/firmware/devicetree/base/compatible': b'samsung,gts9wifi\0',
                 'proc/config.gz': gzip.compress(config), 'sys/kernel/notes': notes}
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        helper = load(staged_mapping, 'exact_mapping')
        kwargs = dict(root=root, machine='aarch64', release=release)
        helper.identity('native', 'fixture', **kwargs)
        for name, bad in (('sys/kernel/notes', (ROOT / 'out/kernel-x710-esc-driver/kernel-notes.bin').read_bytes()),
                          ('proc/config.gz', gzip.compress(b'wrong-config\n')),
                          ('proc/sys/kernel/random/boot_id', b'other')):
            path = root / name
            path.write_bytes(bad)
            try:
                helper.identity('native', 'fixture', **kwargs)
            except ValueError:
                pass
            else:
                raise AssertionError('identity gate accepted ' + name)
            path.write_bytes(files[name])
    mapping['exact_identity_checks'] = ['candidate accepted', 'old notes rejected',
                                        'wrong config rejected', 'changed boot rejected']

    old_boot = checked(ROOT / 'out/boot-bundle-x710-fedora-snapshot-fix/boot.img',
        '025ebea4282524751bace461ce96beef85c01ea65a4d2b117106c7cdfe0ab815')
    vendor = checked(ROOT / 'out/boot-bundle-x710-263-passive/vendor_boot.img',
        'efddf31cfac5da0fab55b44029629155076977cb2d7695a384d446dd4b5ad0d1')
    OUT.mkdir()
    boot = OUT / 'boot.img'
    with tempfile.TemporaryDirectory(prefix='gts9-gmu-boot-') as tmp:
        tmp = Path(tmp)
        payload = (KERNEL / 'Image.gz').read_bytes() + (KERNEL / 'sm8550-samsung-gts9wifi.dtb').read_bytes()
        (tmp / 'kernel').write_bytes(payload)
        run(['python3', ROOT / '.work/tools/mkbootimg.py', '--kernel', tmp / 'kernel',
             '--cmdline', '', '--header_version', '4', '--os_version', '13',
             '--os_patch_level', '2025-07', '-o', boot])
        run(['python3', ROOT / '.work/tools/avbtool.py', 'add_hash_footer', '--image', boot,
             '--partition_name', 'boot', '--partition_size', '100663296', '--salt', digest(boot)])
        run(['python3', ROOT / '.work/tools/avbtool.py', 'verify_image', '--image', boot])
        new_header = run(['python3', ROOT / '.work/tools/unpack_bootimg.py', '--boot_img', boot, '--out', tmp / 'new'])
        old_header = run(['python3', ROOT / '.work/tools/unpack_bootimg.py', '--boot_img', old_boot, '--out', tmp / 'old'])
        assert (tmp / 'new/kernel').read_bytes() == payload
        assert not (tmp / 'new/ramdisk').exists() or (tmp / 'new/ramdisk').stat().st_size == 0
        def metadata(text):
            return [line for line in text.splitlines() if not line.startswith('kernel_size:')]
        assert metadata(new_header) == metadata(old_header)
        assert boot.stat().st_size == 100663296
    qualification = dict(verdict='OFFLINE_ASSEMBLED_NOT_DEPLOYED', device_operations=[],
        boot=dict(path=str(boot.relative_to(ROOT)), sha256=digest(boot), bytes=boot.stat().st_size),
        vendor_boot=dict(path=str(vendor.relative_to(ROOT)), sha256=digest(vendor),
                         reused_accepted_Test331=True, early_ADSP=False),
        AVB_verified=True, exact_payload=True, boot_metadata_unchanged=True,
        paired_modules=modules, staged_loaders=loaders, mapping=mapping, commands=commands)
    (HERE / 'BUNDLE.json').write_text(json.dumps(qualification, indent=2) + '\n')
    print(json.dumps({k: qualification[k] for k in ('verdict', 'boot', 'vendor_boot')}))


if __name__ == '__main__':
    main()
