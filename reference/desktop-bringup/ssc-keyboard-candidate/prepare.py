#!/usr/bin/env python3
"""Offline-only assembly from frozen Escape kernel and signed ADSP artifacts."""
import ast
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'out/boot-bundle-ssc-keyboard'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(path, expected):
    assert digest(path) == expected, str(path)
    return path


def run(argv):
    result = subprocess.run([str(x) for x in argv], cwd=ROOT, check=True,
                            capture_output=True, text=True)
    commands.append({'argv': [str(x) for x in argv], 'stdout': result.stdout,
                     'stderr': result.stderr, 'returncode': result.returncode})
    return result.stdout


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mock_loader(path, profile, config, notes, pen, touch):
    """Exercise actual staged loader without weakening its real identity profile."""
    module = load(path, path.stem)
    checks = []
    with tempfile.TemporaryDirectory(prefix='gts9-pair-gate-') as tmp:
        root = Path(tmp)
        files = {
            'proc/sys/kernel/random/boot_id': b'host-fixture-not-a-device\n',
            'sys/firmware/devicetree/base/compatible': b'samsung,gts9wifi\0',
            'proc/cmdline': b'console=tty0\n',
            'proc/config.gz': gzip.compress(config),
            'sys/kernel/notes': notes,
            'sys/bus/i2c/devices/6-0056/of_node/compatible': b'wacom,w90xx\0',
            'sys/bus/i2c/devices/7-0049/of_node/compatible': b'st,fts1ba90a\0',
            'sys/class/power_supply/sm5714-battery/health': b'Good\n',
            'sys/class/power_supply/sm5714-battery/temp': b'250\n',
            'usr/local/lib/gts9-desktop/wacom-wez01.ko': pen,
            'usr/local/lib/gts9-desktop/fts1ba90a-palm.ko': touch,
        }
        for name, data in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (root / 'sys/module').mkdir()
        def inspect():
            return module.inspect(root, machine='aarch64', release=profile['release'])
        assert inspect()['status'] == 'ready'
        checks.append('exact kernel/config/modules ready')
        for name, replacement, expected in (
            ('proc/config.gz', gzip.compress(b'old-config\n'), 'skipped'),
            ('sys/kernel/notes', b'old-notes', 'skipped'),
            ('proc/cmdline', b'sm5440_direct.direct_charge=1\n', 'skipped'),
            ('usr/local/lib/gts9-desktop/wacom-wez01.ko', b'corrupt', 'error'),
            ('sys/class/power_supply/sm5714-battery/temp', b'420\n', 'error'),
        ):
            (root / name).write_bytes(replacement)
            assert inspect()['status'] == expected, name
            (root / name).write_bytes(files[name])
            checks.append(name + ' alteration rejected')
    return checks


commands = []


def main():
    if OUT.exists():
        raise ValueError('output already exists; do not overwrite a frozen candidate')
    audit = json.loads((HERE.parent / 'keyboard-escape-driver/BUILD_AUDIT.json').read_text())
    kernel = ROOT / 'out/kernel-x710-esc-driver'
    for name, item in audit['artifacts'].items():
        checked(ROOT / name, item['sha256'])
    provider = ROOT / '.work/build/linux-out-x710-308-passive'
    after = json.loads((HERE.parent / 'keyboard-escape-driver/PROVIDER_AFTER.json').read_text())
    for name, expected in after['hashes'].items():
        checked(ROOT / name, expected)
    config = (kernel / 'config').read_bytes()
    notes = (kernel / 'kernel-notes.bin').read_bytes()
    release = (kernel / 'kernel.release').read_text().strip()
    assert b'# CONFIG_HVC_DCC is not set\n' in config
    for symbol in ('USER_NS', 'POSIX_MQUEUE', 'KEYBOARD_SAMSUNG_POGO', 'QCOM_SOCINFO'):
        assert ('CONFIG_' + symbol + '=y\n').encode() in config

    # The native pair's exact source and binary are unchanged. Requalify imports
    # against the current provider rather than claiming old provider admission.
    prior = json.loads((HERE.parent / 'native-socinfo-kernel/INPUT_PAIR_BUILD.json').read_text())
    symbols = {}
    for path in (provider / 'Module.symvers', ROOT / 'out/ssc-native-input-pair/pen/Module.symvers'):
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
        path_string, expected = next(iter(item['modules'].items()))
        path = checked(ROOT / path_string, expected)
        imports = run(['modprobe', '--dump-modversions', path]).splitlines()
        assert imports
        for line in imports:
            crc, symbol = line.split()
            assert symbols.get(symbol) == int(crc, 16), symbol
        vermagic = run(['modinfo', '-F', 'vermagic', path]).strip()
        assert vermagic == release + ' SMP preempt mod_unload modversions aarch64'
        modules[item['label']] = {'path': path_string, 'sha256': expected,
                                 'imports_checked': len(imports), 'vermagic': vermagic}

    # Reuse the exact accepted ADSP vendor image, including all headers/addresses,
    # signed firmware and bootconfig. Build only boot with the new kernel.
    prior_bundle = json.loads((HERE.parent / 'ssc-early-firmware/BUNDLE.json').read_text())
    for item in prior_bundle['artifacts'].values():
        checked(ROOT / item['path'], item['sha256'])
    OUT.mkdir()
    mkboot = ROOT / '.work/tools/mkbootimg.py'
    avb = ROOT / '.work/tools/avbtool.py'
    unpack = ROOT / '.work/tools/unpack_bootimg.py'
    with tempfile.TemporaryDirectory(prefix='gts9-ssc-escape-') as tmp:
        tmp = Path(tmp)
        payload = (kernel / 'Image.gz').read_bytes() + (kernel / 'sm8550-samsung-gts9wifi.dtb').read_bytes()
        (tmp / 'kernel').write_bytes(payload)
        boot = OUT / 'boot.img'
        run(['python3', mkboot, '--kernel', tmp / 'kernel', '--cmdline', '',
             '--header_version', '4', '--os_version', '13', '--os_patch_level', '2025-07', '-o', boot])
        run(['python3', avb, 'add_hash_footer', '--image', boot, '--partition_name', 'boot',
             '--partition_size', '100663296', '--salt', digest(boot)])
        run(['python3', avb, 'verify_image', '--image', boot])
        new_header = run(['python3', unpack, '--boot_img', boot, '--out', tmp / 'new'])
        old_header = run(['python3', unpack, '--boot_img', ROOT / prior_bundle['artifacts']['boot.img']['path'], '--out', tmp / 'old'])
        assert (tmp / 'new/kernel').read_bytes() == payload
        assert not (tmp / 'new/ramdisk').exists() or (tmp / 'new/ramdisk').stat().st_size == 0
        # The sole reported header difference is the deliberately different size
        # of the compressed kernel; other Android boot metadata stays exact.
        def metadata(text):
            return [line for line in text.splitlines() if not line.startswith('kernel_size:')]
        assert metadata(new_header) == metadata(old_header), (new_header, old_header)
        assert boot.stat().st_size == 100663296

    loaders = {}
    for label in ('pen', 'palm'):
        template = ROOT / 'userspace/gnome' / label / 'load.py'
        tree = ast.parse(template.read_text())
        node = next(x for x in tree.body if isinstance(x, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'PROFILE' for t in x.targets))
        profile = ast.literal_eval(node.value)
        profile.update(release=release, config_sha256=digest(kernel / 'config'),
                       notes_sha256=digest(kernel / 'kernel-notes.bin'))
        if label == 'pen':
            profile['module_sha256'] = modules['pen']['sha256']
        else:
            profile.update(pen_sha256=modules['pen']['sha256'],
                           touch_sha256=modules['palm-touch']['sha256'])
        lines = template.read_text().splitlines(keepends=True)
        lines[node.lineno-1:node.end_lineno] = ['PROFILE = ' + repr(profile) + '\n']
        staged = HERE / (label + '-loader.py')
        staged.write_text(''.join(lines))
        other = ast.parse(staged.read_text())
        original = copy.deepcopy(tree)
        def without_profile(value):
            value.body = [x for x in value.body if not (isinstance(x, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'PROFILE' for t in x.targets))]
            return ast.dump(value)
        assert without_profile(original) == without_profile(other)
        checks = mock_loader(staged, profile, config, notes,
                             (ROOT / modules['pen']['path']).read_bytes(),
                             (ROOT / modules['palm-touch']['path']).read_bytes())
        loaders[label] = {'profile': profile, 'sha256': digest(staged),
                          'template_sha256': digest(template),
                          'AST_delta_only_PROFILE': True, 'mock_checks': checks}
    result = {'verdict': 'OFFLINE_ASSEMBLED_NOT_REGISTERED_OR_DEPLOYED',
              'kernel_build_reused': True, 'device_operations': [],
              'boot': {'path': str(boot.relative_to(ROOT)), 'sha256': digest(boot), 'bytes': boot.stat().st_size},
              'vendor_boot_reused': prior_bundle['artifacts']['vendor_boot.img'],
              'exact_new_payload': True, 'AVB_verified': True, 'boot_metadata_unchanged': True,
              'config_sha256': digest(kernel / 'config'), 'notes_sha256': digest(kernel / 'kernel-notes.bin'),
              'DTB_sha256': digest(kernel / 'sm8550-samsung-gts9wifi.dtb'),
              'paired_modules': modules, 'staged_loaders': loaders, 'commands': commands,
              'remaining': ['independent Test366 runner/registration', 'XKB transition and rollback integration',
                            'namespace-explicit recovery integration', 'bounded FastRPC trace/QRTR capture',
                            'device rescue/preflight and actual SSC/input acceptance']}
    (HERE / 'QUALIFICATION.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('verdict', 'boot', 'paired_modules', 'remaining')}, indent=2))


if __name__ == '__main__':
    main()
