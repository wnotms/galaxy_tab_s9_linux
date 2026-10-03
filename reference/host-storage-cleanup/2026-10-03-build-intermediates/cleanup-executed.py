"""One-time selective Kbuild cleanup; preserve final outputs and module inputs."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/home/ms/Samsung/galaxy_tab_s9_linux')
REPORT = ROOT / 'reference/host-storage-cleanup/2026-10-03-build-intermediates'
NAMES = [
    'linux-out', 'linux-out-x710-263-passive',
    'linux-out-x710-272-passive', 'linux-out-x710-290-passive',
    'linux-out-x710-299-passive', 'linux-out-x710-303-policy',
    'linux-out-x710-305-adc-condition',
]
FULL = ['linux-out-x710-302-passive', 'linux-out-x710-308-passive']


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def entries(base):
    for root, dirs, files in os.walk(base, followlinks=False):
        for name in dirs[:]:
            p = Path(root) / name
            if p.is_symlink():
                dirs.remove(name)
                yield p
        for name in files:
            yield Path(root) / name


def guard():
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            args = (p / 'cmdline').read_bytes().split(b'\0')
            name = Path(os.fsdecode(args[0])).name if args else ''
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if name in ('make', 'clang', 'clang-22', 'ld.lld', 'ninja', 'sparse'):
            raise RuntimeError('Build in progress; refusing concurrent cleanup')


def selected(base):
    assert base.is_dir() and not base.is_symlink()
    assert not (base / '.git').exists()
    result = set()
    for p in entries(base):
        rel = p.relative_to(base)
        if p.is_symlink() or not p.is_file():
            continue
        if rel.parts[0] in ('scripts', 'tools', 'include'):
            continue
        if rel.as_posix().startswith('arch/arm64/include/'):
            continue
        if p.name == '.module-common.o':
            continue
        if p.suffix in ('.o', '.a') or (
            len(rel.parts) == 1 and (
                p.name.startswith('.tmp_vmlinux') or p.name == 'vmlinux.unstripped'
            )
        ):
            result.add(p)
    for p in list(result):
        for suffix in ('.cmd', '.d'):
            extra = p.with_name('.' + p.name + suffix)
            if extra.is_file() and not extra.is_symlink():
                result.add(extra)
    return result


def protected(excluded):
    result = {}
    bases = [ROOT / x for x in ('.work/build', 'out', 'reference')]
    dirty = subprocess.check_output(
        ['git', 'diff', '--name-only', '-z'], cwd=ROOT
    ).decode().split('\0')
    paths = set()
    for b in bases:
        paths.update(entries(b))
    paths.update(ROOT / x for x in dirty if x)
    # Include untracked current source/tests outside the reference archive.
    other = subprocess.check_output(
        ['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT
    ).decode().split('\0')
    paths.update(ROOT / x for x in other if x)
    for p in sorted(paths):
        if p in excluded or p == REPORT or REPORT in p.parents:
            continue
        key = p.relative_to(ROOT).as_posix()
        if p.is_symlink():
            result[key] = {'symlink': os.readlink(p)}
        elif p.is_file():
            result[key] = {'bytes': p.stat().st_size, 'sha256': sha(p)}
    return result


def disk():
    return subprocess.check_output(
        ['df', '-B1', '--output=source,size,used,avail,pcent', '/', '/mnt/d'],
        text=True,
    )


def write_gz(name, value):
    with gzip.open(REPORT / name, 'wt') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def main():
    assert Path.cwd().resolve() == ROOT
    assert not (REPORT / 'deleted-files.json.gz').exists(), 'One-time operation'
    guard()
    before_disk = disk()
    before_size = int(subprocess.check_output(
        ['du', '-x', '-B1', '-s', str(ROOT / '.work/build')], text=True
    ).split()[0])
    chosen = set()
    counts = {}
    for name in NAMES:
        base = ROOT / '.work/build' / name
        items = selected(base)
        chosen.update(items)
        counts[name] = len(items)
        for rel in ('.config', 'vmlinux', 'Module.symvers', 'System.map',
                    'modules.builtin.modinfo', '.module-common.o',
                    'include/config/auto.conf', 'include/generated/autoconf.h',
                    'scripts/mod/modpost', 'scripts/module.lds'):
            p = base / rel
            assert p.is_file() and p not in chosen, p
        sections = subprocess.check_output(
            ['llvm-readelf', '-S', str(base / 'vmlinux')], text=True
        )
        assert '.debug_info' in sections and '.BTF ' in sections, name
    assert not any(
        (ROOT / '.work/build' / name) in p.parents for p in chosen for name in FULL
    )
    prior = protected(chosen)
    write_gz('protected-before.json.gz', prior)
    print('Surviving build/source/artifact/evidence files hashed:', len(prior), flush=True)
    manifest = []
    for p in sorted(chosen):
        s = p.lstat()
        assert not p.is_symlink() and s.st_nlink == 1, p
        manifest.append({
            'path': p.relative_to(ROOT).as_posix(), 'bytes': s.st_size,
            'allocated_bytes': s.st_blocks * 512, 'sha256': sha(p),
            'inode': s.st_ino, 'mtime_ns': s.st_mtime_ns,
            'contents_archived': False,
        })
    write_gz('deleted-files.json.gz', manifest)
    print('Regenerable files selected:', len(manifest), 'allocated GiB:',
          round(sum(x['allocated_bytes'] for x in manifest) / 2**30, 3), flush=True)
    guard()
    for name in NAMES:
        assert selected(ROOT / '.work/build' / name) == {
            p for p in chosen if p.parts[len(ROOT.parts) + 2] == name
        }, name
    for r in manifest:
        p = ROOT / r['path']
        s = p.lstat()
        assert not p.is_symlink() and s.st_nlink == 1
        assert (s.st_ino, s.st_size, s.st_mtime_ns) == (
            r['inode'], r['bytes'], r['mtime_ns']
        ), p
    # Only individually listed regular files are removed, never source trees.
    for name in NAMES:
        guard()
        for p in sorted(chosen):
            if (ROOT / '.work/build' / name) in p.parents:
                p.unlink()
        print('Trimmed intermediate files:', name, counts[name], flush=True)
    after = protected(set())
    assert after == prior, 'Surviving file contents or set changed'
    assert all(not (ROOT / x['path']).exists() for x in manifest)
    after_size = int(subprocess.check_output(
        ['du', '-x', '-B1', '-s', str(ROOT / '.work/build')], text=True
    ).split()[0])
    result = {
        'trimmed_builds': NAMES, 'full_incremental_builds_untouched': FULL,
        'removed_files': len(manifest),
        'removed_allocated_bytes': sum(x['allocated_bytes'] for x in manifest),
        'build_before_allocated_bytes': before_size,
        'build_after_allocated_bytes': after_size,
        'protected_files_hash_verified': len(prior),
        'surviving_file_set_and_hashes_unchanged': True,
        'regenerable_intermediates_archived': False,
        'disk_before': before_disk, 'disk_after': disk(),
        'kernel_build': {'executed': False},
        'host_regression': {'executed': False},
        'device_commands': {'executed': False}, 'ci': {'executed': False},
    }
    (REPORT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    identities = {}
    for name in ('deleted-files.json.gz', 'protected-before.json.gz'):
        p = REPORT / name
        identities[name] = {'bytes': p.stat().st_size, 'sha256': sha(p)}
    (REPORT / 'manifest-archives.json').write_text(json.dumps(identities, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
