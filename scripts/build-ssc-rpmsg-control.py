#!/usr/bin/env python3
"""Build unmodified upstream RPMSG control against the accepted Test370 provider.
This is offline preparation only. It never contacts a device or changes .config.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT / '.work/build/linux-src-x710-charging'
PROVIDER = ROOT / '.work/build/linux-out-x710-308-passive'
STAGE = ROOT / '.work/build/ssc-rpmsg-control'
OUT = ROOT / 'out/ssc-rpmsg-control'
PIN = 'a13c140cc289c0b7b3770bce5b3ad42ab35074aa'
CONFIG = '599ca47ab41a29469c3d5830e475049fca9f33bd2ab0923ad014e5ba3fa6ec6c'
NOTES = '5c0e82337affafefff586613d4a84c4f1388c9716ce251fe69d3c70aad18a518'
SYMVERS = '4781ff5d1f2fd060688496e2f1056568e6b3383c9eddb3291fcea4414797679d'
SOURCES = ('rpmsg_ctrl.c', 'rpmsg_char.h', 'rpmsg_internal.h')
FROZEN = ('.config', 'Module.symvers', 'vmlinux', 'System.map',
          'include/generated/autoconf.h', 'include/generated/utsrelease.h',
          'include/generated/compile.h', 'include/config/kernel.release')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def call(argv, **kwargs):
    return subprocess.check_output(argv, text=True, **kwargs)


def provider_identity():
    if sha(PROVIDER / '.config') != CONFIG or sha(PROVIDER / 'Module.symvers') != SYMVERS:
        raise ValueError('accepted provider config/symbol identity changed')
    text = (PROVIDER / '.config').read_text()
    for expected in ('CONFIG_RPMSG=y', 'CONFIG_RPMSG_CHAR=y',
                     '# CONFIG_RPMSG_CTRL is not set', '# CONFIG_HVC_DCC is not set',
                     'CONFIG_MODVERSIONS=y'):
        if expected not in text.splitlines():
            raise ValueError('provider prerequisite: ' + expected)
    if call(['git', '-C', str(TREE), 'rev-parse', 'HEAD']).strip() != PIN:
        raise ValueError('Linux pin changed')
    for name in SOURCES:
        path = 'drivers/rpmsg/' + name
        frozen = subprocess.check_output(['git', '-C', str(TREE), 'show', PIN + ':' + path])
        if (TREE / path).read_bytes() != frozen:
            raise ValueError('upstream source modified: ' + name)
    with tempfile.TemporaryDirectory(prefix='ssc-rpmsg-notes-') as temp:
        notes = Path(temp) / 'notes'
        subprocess.run(['llvm-objcopy', '--dump-section', '.notes=' + str(notes),
                        str(PROVIDER / 'vmlinux'), '/dev/null'], check=True)
        if sha(notes) != NOTES:
            raise ValueError('provider ELF notes mismatch')
    return {name: sha(PROVIDER / name) for name in FROZEN}


def imported_versions(module, symvers):
    observed = {}
    for line in call(['modprobe', '--show-modversions', str(module)]).splitlines():
        crc, name = line.split()
        if name in observed:
            raise ValueError('duplicate imported symbol')
        observed[name] = crc.lower()
    expected = {row.split()[1]: row.split()[0].lower()
                for row in symvers.read_text().splitlines()}
    if not observed or any(expected.get(name) != crc for name, crc in observed.items()):
        raise ValueError('module import CRCs do not match accepted provider')
    return observed


def main():
    before = provider_identity()
    STAGE.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        shutil.copyfile(TREE / 'drivers/rpmsg' / name, STAGE / name)
    shutil.copyfile(ROOT / 'kernel/diagnostics/ssc-rpmsg-control/Makefile', STAGE / 'Makefile')
    env = os.environ | {'CCACHE_DIR': str(ROOT / '.work/ccache'),
                        'CCACHE_BASEDIR': str(ROOT / '.work')}
    command = ['make', '-C', str(TREE), 'O=' + str(PROVIDER), 'ARCH=arm64',
               'LLVM=1', 'CC=ccache clang', 'W=1', '-j8', 'M=' + str(STAGE), 'modules']
    subprocess.run(command, check=True, env=env)
    after = {name: sha(PROVIDER / name) for name in FROZEN}
    if after != before:
        raise ValueError('provider mutated by external build; preserve evidence, do not deploy')
    module = STAGE / 'rpmsg_ctrl.ko'
    imports = imported_versions(module, PROVIDER / 'Module.symvers')
    header = call(['llvm-readelf', '-h', str(module)])
    if 'AArch64' not in header:
        raise ValueError('not an ARM64 module')
    modinfo = call(['modinfo', str(module)])
    if '7.2.0-rc3-gts9wifi-dirty' not in modinfo:
        raise ValueError('module vermagic mismatch')
    with tempfile.TemporaryDirectory(prefix='ssc-rpmsg-module-notes-') as temp:
        note = Path(temp) / 'build-id-note'
        subprocess.run(['llvm-objcopy', '--dump-section', '.note.gnu.build-id=' + str(note),
                        str(module), '/dev/null'], check=True)
        module_note_sha256 = sha(note)
    shutil.copyfile(module, OUT / module.name)
    report = dict(kernel_build_executed=False, external_module_build_executed=True,
                  upstream_unmodified=True, Linux_pin=PIN, device_operations=False,
                  provider=str(PROVIDER.relative_to(ROOT)), provider_inputs=before,
                  provider_unchanged=True, config_sha256=CONFIG, notes_sha256=NOTES,
                  source_sha256={name: sha(STAGE / name) for name in SOURCES},
                  module_path=str((OUT / module.name).relative_to(ROOT)),
                  module_sha256=sha(module), module_build_id_note_sha256=module_note_sha256,
                  imported_versions=imports,
                  command=command, modinfo=modinfo,
                  scope='temporary upstream control interface only; no DIAG endpoint or protocol packets')
    (OUT / 'BUILD.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(verdict='OFFLINE_MODULE_PAIRED_NOT_DEPLOYED',
                         module_sha256=sha(module), imported_symbols=len(imports))))


if __name__ == '__main__':
    main()
