#!/usr/bin/env python3
"""Build the patched Debian ACPI client; never contact or modify a device."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_source(destination):
    manifest = json.loads((HERE / 'SOURCE.json').read_text())
    destination.mkdir(parents=True, exist_ok=True)
    for name, expected in manifest['files'].items():
        source = HERE / 'source-baseline' / name
        if digest(source) != expected:
            raise ValueError('upstream source identity changed: ' + name)
        shutil.copyfile(source, destination / name)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i',
                    str(HERE / '0001-use-power-supply-capacity.patch')],
                   cwd=destination, check=True)
    (destination / 'config.h').write_text('#define VERSION "1.8+gts9-capacity1"\n')


def prepare_sysroot(destination):
    manifest = json.loads((HERE / 'arm64-sysroot.json').read_text())
    cache = ROOT / '.work/downloads/acpi-arm64-sysroot'
    cache.mkdir(parents=True, exist_ok=True)

    def fetch(package):
        archive = cache / Path(package['filename']).name
        if not archive.exists():
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
                temporary = Path(stream.name)
            try:
                with urllib.request.urlopen(manifest['mirror'] + package['filename'], timeout=30) as response:
                    with temporary.open('wb') as stream:
                        shutil.copyfileobj(response, stream)
                if digest(temporary) != package['sha256']:
                    raise ValueError('download hash mismatch: ' + archive.name)
                os.replace(temporary, archive)
            finally:
                temporary.unlink(missing_ok=True)
        if digest(archive) != package['sha256']:
            raise ValueError('cached sysroot hash mismatch: ' + archive.name)
        return archive

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        archives = list(pool.map(fetch, manifest['packages']))
    destination.mkdir(parents=True, exist_ok=True)
    for archive in archives:
        subprocess.run(['dpkg-deb', '-x', str(archive), str(destination)], check=True)
    # Debian's packages assume the base system's merged-/usr alias exists.
    alias = destination / 'lib'
    if not alias.exists():
        alias.symlink_to('usr/lib', target_is_directory=True)


def build(arch, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='acpi-build-', dir=output) as directory:
        source = Path(directory) / 'source'
        prepare_source(source)
        files = [str(source / name) for name in ['main.c', 'acpi.c', 'list.c']]
        compiler = os.environ.get('CC', 'cc' if arch == 'host' else 'clang')
        flags = ['-O2', '-Wall', '-I' + str(source)]
        if arch == 'arm64':
            sysroot = ROOT / '.work/build/acpi-arm64-sysroot'
            prepare_sysroot(sysroot)
            lib = sysroot / 'usr/lib/aarch64-linux-gnu'
            flags += ['--target=aarch64-linux-gnu', '-fuse-ld=lld',
                      '--sysroot=' + str(sysroot), '-nostdlib', '-fPIE', '-pie',
                      '-Wl,--dynamic-linker=/lib/ld-linux-aarch64.so.1',
                      '-Wl,-z,relro,-z,now', '-L' + str(lib)]
            # Plain C needs libc startup, not a target GCC/C++ runtime.
            files = [str(lib / 'Scrt1.o'), str(lib / 'crti.o')] + files + ['-lc', str(lib / 'crtn.o')]
        target = Path(directory) / 'acpi'
        command = [compiler] + flags + files + ['-o', str(target)]
        subprocess.run(command, check=True)
        os.replace(target, output / 'acpi')
        summary = dict(arch=arch, binary_sha256=digest(output / 'acpi'),
                       patch_sha256=digest(HERE / '0001-use-power-supply-capacity.patch'),
                       source=json.loads((HERE / 'SOURCE.json').read_text()),
                       compiler=subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
                       command=command, device_modified=False)
        (output / 'build.json').write_text(json.dumps(summary, indent=2) + '\n')
        return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=['host', 'arm64'], default='arm64')
    parser.add_argument('--out', type=Path, default=ROOT / 'out/userspace/acpi-battery-compat')
    args = parser.parse_args()
    print(json.dumps(build(args.arch, args.out), indent=2))
