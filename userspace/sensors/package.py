#!/usr/bin/env python3
"""Package qualified SSC ARM64 outputs offline; never install on a tablet."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
from email.parser import Parser

from build import inspect_stage

BASE = Path(__file__).resolve().parent
PACKAGES = {
    'libssc2': dict(version='0.4.4+gts9.1', component='libssc', license='LICENSE',
        description='Qualcomm Sensor Core library and diagnostic client', files=[
            'usr/lib/aarch64-linux-gnu/libssc.so.2', 'usr/bin/ssccli']),
    'gts9-hexagonrpc': dict(version='0.4.0+gts9.1', component='hexagonrpc', license='COPYING',
        description='FastRPC userspace daemon for the X710 sensor stack', extra_depends=['systemd'], files=[
            'usr/lib/aarch64-linux-gnu/libhexagonrpc.so.0.4', 'usr/bin/hexagonrpcd',
            'usr/share/man/man1/hexagonrpcd.1',
            'usr/lib/systemd/system/hexagonrpcd-adsp-rootpd.service',
            'usr/lib/systemd/system/hexagonrpcd-adsp-sensorspd.service',
            'usr/lib/systemd/system/hexagonrpcd-sdsp.service']),
    'pd-mapper': dict(version='1.1+gts9.1', component='pd-mapper', license='LICENSE',
        description='Qualcomm remote service domain mapper', files=[
            'usr/bin/pd-mapper', 'usr/lib/systemd/system/pd-mapper.service']),
    'iio-sensor-proxy': dict(version='3.9+gts9.1', component='iio-sensor-proxy', license='COPYING',
        description='Sensor D-Bus proxy with Qualcomm SSC support', extra_depends=['udev'], files=[
            'usr/bin/monitor-sensor', 'usr/libexec/iio-sensor-proxy',
            'usr/lib/systemd/system/iio-sensor-proxy.service',
            'usr/lib/udev/rules.d/80-iio-sensor-proxy.rules',
            'usr/share/dbus-1/system.d/net.hadess.SensorProxy.conf',
            'usr/share/polkit-1/actions/net.hadess.SensorProxy.policy']),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_plan(report):
    """A reviewed runtime subset; no mock server, development files or firmware."""
    ownership = {}
    for package, spec in PACKAGES.items():
        for name in spec['files']:
            if name not in report['files']:
                raise ValueError('missing qualified runtime file: ' + name)
            if name in ownership:
                raise ValueError('duplicate package ownership: ' + name)
            ownership[name] = package
    return ownership


def verify_build(directory, reference):
    if digest(directory / 'BUILD.json') != digest(reference):
        raise ValueError('build report differs from qualified reference')
    report = json.loads(reference.read_text())
    if report.get('final_status') != 0 or report.get('verdict') != 'ARM64_COMPILED_NOT_DEPLOYED':
        raise ValueError('build is not qualified for packaging')
    actual = inspect_stage(directory / 'stage')
    if any(actual[key] != report[key] for key in ('files', 'links', 'elf_files')):
        raise ValueError('staged files differ from qualified build')
    payload_plan(report)
    return report


def control(name, spec, depends):
    if not depends or '\n' in depends or '\r' in depends:
        raise ValueError('invalid dependency field')
    return (f'Package: {name}\nVersion: {spec["version"]}\nArchitecture: arm64\n'
            'Section: misc\nPriority: optional\n'
            'Maintainer: GTS9 port maintainers <noreply@localhost>\n'
            f'Depends: {depends}\nDescription: {spec["description"]}\n'
            ' Built from the pinned Fedora X710 sensor sources for Debian trixie.\n'
            ' This package contains no firmware and does not enable services.\n')


def archive_files(data):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
                raise ValueError('unsafe package member path')
            if member.uid != 0 or member.gid != 0:
                raise ValueError('package member is not owned by root')
            if member.isdir():
                continue
            if not member.isfile() or name in files:
                raise ValueError('unexpected link/special/duplicate package member')
            files[name] = archive.extractfile(member).read()
    return files


def inspect_package(control_tar, data_tar, name, row):
    metadata = archive_files(control_tar)
    allowed = {'control', 'triggers'} if name in ('libssc2', 'gts9-hexagonrpc') else {'control'}
    if set(metadata) != allowed or set(row['control_files']) != allowed:
        raise ValueError('unexpected package control scripts/files')
    headers = Parser().parsestr(metadata['control'].decode())
    expected = dict(Package=name, Version=row['version'], Architecture='arm64', Depends=row['depends'])
    if any(headers[key] != value for key, value in expected.items()):
        raise ValueError('package metadata mismatch')
    if 'triggers' in metadata and metadata['triggers'] != b'activate-noawait ldconfig\n':
        raise ValueError('unexpected package trigger')
    payload = archive_files(data_tar)
    actual = {key:hashlib.sha256(value).hexdigest() for key,value in payload.items()}
    if actual != row['payload_files']:
        raise ValueError('package payload differs from manifest')
    return actual


def verify_packages(output, directory):
    report = json.loads((output / 'PACKAGES.json').read_text())
    build = json.loads((directory / 'BUILD.json').read_text())
    if report['qualified_build_sha256'] != digest(directory / 'BUILD.json'):
        raise ValueError('package input build identity mismatch')
    if set(report['packages']) != set(PACKAGES):
        raise ValueError('package set mismatch')
    ownership = set()
    for name, row in report['packages'].items():
        spec = PACKAGES[name]
        expected_files = {p:build['files'][p] for p in spec['files']}
        expected_files['usr/share/doc/' + name + '/copyright'] = build['files'][
            'usr/share/doc/gts9-ssc-sources/' + spec['component'] + '/' + spec['license']]
        if name == 'gts9-hexagonrpc':
            for source, target in [('10-fastrpc.rules','usr/lib/udev/rules.d/10-fastrpc.rules'),
                                   ('gts9-fastrpc.conf','usr/lib/sysusers.d/gts9-fastrpc.conf')]:
                expected_files[target] = digest(BASE / 'integration' / source)
        if row['version'] != spec['version'] or row['payload_files'] != expected_files:
            raise ValueError('package payload is not the reviewed runtime subset')
        path = output / row['filename']
        if digest(path) != row['sha256']:
            raise ValueError('Debian package hash mismatch')
        actual = inspect_package(
            subprocess.check_output(['dpkg-deb', '--ctrl-tarfile', str(path)]),
            subprocess.check_output(['dpkg-deb', '--fsys-tarfile', str(path)]), name, row)
        if ownership.intersection(actual):
            raise ValueError('overlapping package payloads')
        ownership.update(actual)
    return report


def package_inside(directory, output):
    report = json.loads((directory / 'BUILD.json').read_text())
    ownership = payload_plan(report)
    work = output / 'work'
    work.mkdir()
    debian = work / 'debian'
    debian.mkdir()
    (debian / 'control').write_text('Source: gts9-ssc\n\n' + '\n'.join(
        f'Package: {name}\nArchitecture: arm64\nDescription: local sensor component\n'
        for name in PACKAGES))
    (debian / 'shlibs.local').write_text(
        'libssc 2 libssc2 (>= 0.4.4+gts9.1)\n'
        'libhexagonrpc 0.4 gts9-hexagonrpc (>= 0.4.0+gts9.1)\n')
    result = dict(verdict='DEBIAN_ARM64_PACKAGES_NOT_DEPLOYED', device_operations=False,
                  installed=False, qualified_build_sha256=digest(directory / 'BUILD.json'),
                  recipe_sha256=digest(Path(__file__)), packages={},
                  excluded_build_files=sorted(set(report['files']) - set(ownership)))
    for name, spec in PACKAGES.items():
        tree = debian / name
        for item in spec['files']:
            target = tree / item
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(directory / 'stage' / item, target)
        license_path = tree / 'usr/share/doc' / name / 'copyright'
        license_path.parent.mkdir(parents=True)
        shutil.copyfile(directory / 'stage/usr/share/doc/gts9-ssc-sources' /
                        spec['component'] / spec['license'], license_path)
        if name == 'gts9-hexagonrpc':
            for source, destination in [
                ('10-fastrpc.rules', 'usr/lib/udev/rules.d/10-fastrpc.rules'),
                ('gts9-fastrpc.conf', 'usr/lib/sysusers.d/gts9-fastrpc.conf')]:
                target = tree / destination
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(BASE / 'integration' / source, target)
        metadata = tree / 'DEBIAN'
        metadata.mkdir()
        # Discover runtime minima from target ELF symbols in the exact build image.
        command = ['dpkg-shlibdeps', '-O', '-x' + name,
                   '-l' + str(directory / 'stage/usr/lib/aarch64-linux-gnu'),
                   '-l/usr/lib/aarch64-linux-gnu']
        command += ['-e' + str(tree / p) for p in spec['files'] if p in report['elf_files']]
        env = dict(os.environ, DEB_HOST_ARCH='arm64', DEB_HOST_MULTIARCH='aarch64-linux-gnu')
        process = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True)
        (output / (name + '-shlibdeps.stdout')).write_text(process.stdout)
        (output / (name + '-shlibdeps.stderr')).write_text(process.stderr)
        process.check_returncode()
        lines = [line.removeprefix('shlibs:Depends=') for line in process.stdout.splitlines()
                 if line.startswith('shlibs:Depends=')]
        if len(lines) != 1:
            raise ValueError('missing or ambiguous shlibdeps output')
        depends = ', '.join(lines + spec.get('extra_depends', []))
        (metadata / 'control').write_text(control(name, spec, depends))
        if name in ('libssc2', 'gts9-hexagonrpc'):
            # Standard libc trigger; no postinst, daemon start or unit enablement.
            (metadata / 'triggers').write_text('activate-noawait ldconfig\n')
        for path in tree.rglob('*'):
            if not path.is_symlink():
                os.utime(path, (0, 0))
        archive = output / f'{name}_{spec["version"]}_arm64.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(tree),
                        str(archive)], env=dict(os.environ, SOURCE_DATE_EPOCH='0'), check=True)
        result['packages'][name] = dict(version=spec['version'], depends=depends,
            filename=archive.name, sha256=digest(archive), bytes=archive.stat().st_size,
            payload_files={str(p.relative_to(tree)):digest(p) for p in sorted(tree.rglob('*'))
                           if p.is_file() and 'DEBIAN' not in p.relative_to(tree).parts},
            control_files=sorted(p.name for p in metadata.iterdir()))
    (output / 'PACKAGES.json').write_text(json.dumps(result, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path,
        default=BASE / '../../reference/desktop-bringup/ssc-offline/BUILD.json')
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    directory, output = args.build.resolve(), args.output.resolve()
    if args.inside:
        package_inside(directory, output)
        return
    report = verify_build(directory, args.reference)
    if output.exists() or output.is_relative_to(directory) or directory.is_relative_to(output):
        raise ValueError('package output must be new and separate from build inputs')
    subprocess.run(['docker', 'image', 'inspect', report['image']], check=True,
                   stdout=subprocess.DEVNULL)
    output.mkdir(parents=True)
    command = ['docker', 'run', '--rm', '--network=none', '--cap-drop=ALL',
               '--security-opt=no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
               '-v', str(directory) + ':/inputs:ro', '-v', str(BASE) + ':/recipe:ro',
               '-v', str(output) + ':/output', report['image'],
               'python3', '/recipe/package.py', '--inside', '--build', '/inputs',
               '--output', '/output']
    with (output / 'package.log').open('wb') as log:
        process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    if process.returncode == 0:
        verify_packages(output, directory)
    print('Packaging return code:', process.returncode, '; output:', output)
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
