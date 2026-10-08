#!/usr/bin/env python3
"""Validate a local GNOME cache; explicit execution installs with GDM masked."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import uuid

import prepare


FIRMWARE = ('lib/firmware/qcom/a740_sqe.fw',
            'lib/firmware/qcom/gmu_gen70200.bin',
            'lib/firmware/qcom/a740_zap.mdt')
GDM_UNITS = ('gdm.service', 'gdm3.service', 'display-manager.service')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan(manifest, cache, firmware):
    rows = prepare.validate(manifest)
    names = [r['package'] for r in rows]
    if (len(set(names)) != len(names) or
            any(not re.fullmatch(r'[a-z0-9][a-z0-9+.-]+', name) for name in names) or
            any(not isinstance(r['version'], str) or not r['version'] or
                any(c.isspace() for c in r['version']) for r in rows)):
        raise ValueError('invalid package names/versions')
    for row in rows:
        if not prepare.matches(cache / row['filename'], row):
            raise ValueError('package cache mismatch: ' + row['filename'])
    info = json.loads((firmware / 'PREPARED.json').read_text())
    blobs = info['files']
    if len(blobs) != 3 or {r['destination'] for r in blobs} != set(FIRMWARE):
        raise ValueError('unexpected GPU firmware destinations')
    for row in blobs:
        path = firmware / row['destination']
        if path.is_symlink() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('GPU firmware cache mismatch')
    return dict(packages=rows, firmware=blobs, execute=False,
                device_operations=False, gdm_units_to_mask=list(GDM_UNITS))


def verify_simulation(text, rows, installed):
    """Allow only new exact manifest packages; reject removals/upgrades/extras."""
    expected = {r['package']: r['version'] for r in rows}
    for name, version in expected.items():
        if name in installed and installed[name] != version:
            raise ValueError('installed package version drift: ' + name)
    needed = {k: v for k, v in expected.items() if k not in installed}
    actual = {}
    for line in text.splitlines():
        if line.startswith('Remv '):
            raise ValueError('APT removal forbidden')
        if line.startswith('Inst '):
            match = re.match(r'^Inst (\S+)( \[[^]]+\])? \((\S+) ', line)
            if not match:
                raise ValueError('unknown APT install record: ' + line)
            name = match[1].removesuffix(':arm64').removesuffix(':all')
            if match[2] or name in installed or name in actual:
                raise ValueError('APT upgrade/reinstall/duplicate forbidden: ' + name)
            actual[name] = match[3]
    if actual != needed:
        raise ValueError('APT plan differs from exact local package manifest')
    return len(actual)


@contextmanager
def deny_service_actions(directory):
    """Restore the original policy, including symlink, mode and ownership."""
    policy = directory / 'policy-rc.d'
    backup = directory / 'policy-rc.d.gts9-gnome-backup'
    if backup.exists() or backup.is_symlink():
        raise ValueError('unfinished earlier policy transaction; inspect backup')
    existed = policy.exists() or policy.is_symlink()
    if existed:
        policy.rename(backup)
    try:
        with policy.open('x') as stream:
            stream.write('#!/bin/sh\n# Temporary gts9 GNOME package-install policy.\nexit 101\n')
        policy.chmod(0o755)
        yield
    finally:
        policy.unlink(missing_ok=True)
        if existed:
            backup.rename(policy)


def mask_gdm(directory):
    # Preflight every destination before writing any mask. Do not replace an
    # existing operator override or a previous interrupted installation guard.
    targets = [directory / name for name in GDM_UNITS]
    if any(p.exists() or p.is_symlink() for p in targets):
        raise ValueError('existing display-manager override/mask; inspect first')
    directory.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for path in targets:
            path.symlink_to('/dev/null')
            created.append(path)
    except BaseException:
        for path in created:
            path.unlink()
        raise
    return [str(p) for p in targets]


def target_identity(expected_boot):
    if platform.machine() != 'aarch64' or os.geteuid() != 0:
        raise ValueError('requires root on native X710 Debian')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    compatible = Path('/proc/device-tree/compatible').read_bytes()
    if ('gts9wifi' not in compatible.decode(errors='replace') or
            uuid.UUID(boot) != uuid.UUID(expected_boot)):
        raise ValueError('requires root on the expected X710 Debian boot')
    cmdline = Path('/proc/cmdline').read_text().split()
    for item in cmdline:
        name, _, value = item.partition('=')
        if name.replace('-', '_').startswith('sm5440') and name.split('.')[-1] in (
                'direct_charge', 'direct_charge_once', 'fixed_return_check', 'pps_return_check'):
            if value.lower() in ('1', 'y', 'yes', 'true'):
                raise ValueError('charging-test boot; desktop install forbidden')
    for name in ('direct_charge', 'direct_charge_once', 'fixed_return_check', 'pps_return_check'):
        flag = Path('/sys/module/sm5440_fedora/parameters') / name
        if flag.exists() and flag.read_text().strip().lower() in ('1', 'y', 'yes', 'true'):
            raise ValueError('active charging-test parameter; desktop install forbidden')
    return boot


def run(argv, evidence, name, check=True):
    stdout = evidence / (name + '.stdout.txt')
    stderr = evidence / (name + '.stderr.txt')
    with stdout.open('w') as out, stderr.open('w') as err:
        result = subprocess.run(argv, env=dict(os.environ, LC_ALL='C',
                                DEBIAN_FRONTEND='noninteractive'), stdout=out, stderr=err)
    result.stdout, result.stderr = stdout.read_text(), stderr.read_text()
    (evidence / (name + '.command.json')).write_text(json.dumps(
        dict(argv=argv, returncode=result.returncode), indent=2) + '\n')
    if check and result.returncode:
        raise RuntimeError(name + ' failed: ' + str(result.returncode))
    return result


def installed_versions(text):
    installed = {}
    for line in text.splitlines():
        fields = line.split('\t')
        if len(fields) == 3 and fields[2] == 'installed':
            installed[fields[0]] = fields[1]
    return installed


def local_apt_argv(cache, rows, evidence):
    # --no-download also forbids APT's acquisition of command-line local .debs
    # outside its archive cache (Test351, Debian APT3). Disable repository
    # sources for this invocation instead; every input is a verified local file.
    # Do not edit /etc/apt or weaken the exact simulation/version gate.
    source_list = evidence / 'empty-sources.list'
    source_list.write_text('')
    source_parts = evidence / 'empty-sources.d'
    source_parts.mkdir()
    return ['apt-get', '-o', 'Dir::Etc::sourcelist=' + str(source_list.resolve()),
            '-o', 'Dir::Etc::sourceparts=' + str(source_parts.resolve()),
            '--yes', '--no-remove', '--no-upgrade', '--no-install-recommends',
            'install'] + [str((cache / r['filename']).resolve()) for r in rows]


def install(prepared, cache, firmware, evidence, expected_boot):
    boot = target_identity(expected_boot)
    evidence.mkdir(parents=True, exist_ok=False)
    status = dict(verdict='STARTED_NOT_ACCEPTED', boot_id=boot,
                  package_installation_started=False, gdm_started=False,
                  firmware_created=[], masks=[])
    def checkpoint():
        (evidence / 'summary.json').write_text(json.dumps(status, indent=2) + '\n')
    checkpoint()
    try:
        audit = run(['dpkg', '--audit'], evidence, 'dpkg-audit')
        if audit.stdout.strip() or audit.stderr.strip():
            raise ValueError('dpkg requires repair before desktop installation')
        before = run(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${db:Status-Status}\n'],
                     evidence, 'packages-before')
        installed = installed_versions(before.stdout)
        gdm = run(['systemctl', 'is-active', *GDM_UNITS], evidence, 'gdm-before', check=False)
        if (gdm.returncode not in (3, 4) or gdm.stderr.strip() or
                len(gdm.stdout.splitlines()) != len(GDM_UNITS) or
                any(line not in ('inactive', 'unknown') for line in gdm.stdout.splitlines())):
            raise ValueError('display manager already active/failed; inspect first')
        apt = local_apt_argv(cache, prepared['packages'], evidence)
        simulation = run(apt[:1] + ['--simulate'] + apt[1:], evidence, 'apt-simulation')
        status['new_packages'] = verify_simulation(simulation.stdout, prepared['packages'], installed)
        # Confirm all existing destination files before touching any firmware.
        for row in prepared['firmware']:
            destination = Path('/') / row['destination']
            if destination.is_symlink() or (destination.exists() and sha(destination) != row['sha256']):
                raise ValueError('existing GPU firmware differs: ' + str(destination))
        status['masks'] = mask_gdm(Path('/etc/systemd/system'))
        checkpoint()
        run(['systemctl', 'daemon-reload'], evidence, 'mask-reload')
        for row in prepared['firmware']:
            destination = Path('/') / row['destination']
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open('xb') as stream:
                    status['firmware_created'].append(str(destination))
                    checkpoint()
                    stream.write((firmware / row['destination']).read_bytes())
        with deny_service_actions(Path('/usr/sbin')):
            status['package_installation_started'] = True
            checkpoint()
            run(apt, evidence, 'apt-install')
        # Explicitly keep masks after success AND failure. Activation is a
        # separate reviewed device stage; this also guards the next boot.
        run(['systemctl', 'daemon-reload'], evidence, 'post-install-reload')
        after = run(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${db:Status-Status}\n'],
                    evidence, 'packages-after')
        final = installed_versions(after.stdout)
        if any(final.get(name) != version for name, version in installed.items()):
            raise ValueError('pre-existing package identity changed')
        for row in prepared['packages']:
            if final.get(row['package']) != row['version']:
                raise ValueError('installed identity mismatch: ' + row['package'])
        for row in prepared['firmware']:
            if sha(Path('/') / row['destination']) != row['sha256']:
                raise ValueError('installed firmware mismatch')
        for name in GDM_UNITS:
            if str((Path('/etc/systemd/system') / name).readlink()) != '/dev/null':
                raise ValueError('display-manager mask changed: ' + name)
        active = run(['systemctl', 'is-active', 'gdm.service'], evidence, 'gdm-state', check=False)
        if active.returncode == 0 or active.stdout.strip() not in ('inactive', 'unknown'):
            raise ValueError('unexpected display-manager state')
        if target_identity(expected_boot) != boot:
            raise ValueError('boot identity changed')
        status['verdict'] = 'INSTALLED_GDM_MASKED_HARDWARE_NOT_ACCEPTED'
    except BaseException as exc:
        status.update(verdict='STOP_INSTALLATION_GDM_GUARD_RETAINED' if status['masks']
                      else 'STOP_BEFORE_INSTALLATION', error=repr(exc))
        raise
    finally:
        checkpoint()
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-boot-id')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    prepared = plan(json.loads(args.manifest.read_text()), args.cache, args.firmware)
    if args.execute:
        if not args.expected_boot_id or not args.evidence:
            parser.error('--execute requires --expected-boot-id and a new --evidence directory')
        result = install(prepared, args.cache, args.firmware, args.evidence, args.expected_boot_id)
    else:
        result = dict(verdict='CACHE_VALIDATED_NO_DEVICE_OPERATIONS',
                      packages=len(prepared['packages']), firmware=len(prepared['firmware']),
                      installation_executed=False, device_operations=False,
                      gdm_units_to_mask=list(GDM_UNITS))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
