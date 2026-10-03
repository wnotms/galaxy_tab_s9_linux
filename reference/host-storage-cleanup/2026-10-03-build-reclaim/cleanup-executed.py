"""One-time cleanup: archive selected debug inputs, delete three stale Kbuild trees."""
import gzip, hashlib, json, os, shutil, subprocess, tarfile
from pathlib import Path

ROOT = Path('/home/ms/Samsung/galaxy_tab_s9_linux')
REPORT = ROOT / 'reference/host-storage-cleanup/2026-10-03-build-reclaim'
SAVE = ROOT / '.work/host-storage-cleanup/2026-10-03-build-reclaim'
NAMES = ['linux-out-x710-294-passive', 'linux-out-x710-295-passive',
         'linux-out-x710-296-passive']
PROVIDERS = ['linux-out', 'linux-out-x710-263-passive',
             'linux-out-x710-272-passive', 'linux-out-x710-290-passive',
             'linux-out-x710-299-passive', 'linux-out-x710-302-passive',
             'linux-out-x710-303-policy', 'linux-out-x710-305-adc-condition',
             'linux-out-x710-308-passive']
KEEP = {'.config', '.config.old', 'vmlinux', 'System.map', 'Module.symvers',
        'modules.order', 'modules.builtin', 'modules.builtin.modinfo',
        'modules.builtin.ranges', 'vmlinux.symvers', 'Makefile'}


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def entries(base):
    for d, dirs, files in os.walk(base, followlinks=False):
        for name in dirs[:]:
            p = Path(d) / name
            if p.is_symlink():
                dirs.remove(name)
                yield p
        for name in files:
            yield Path(d) / name


def snapshot():
    result = {}
    for area in ('out', 'reference'):
        for p in entries(ROOT / area):
            if REPORT in p.parents or 'test-308-ordinary-program-recovery' in p.parts:
                continue  # Separate, in-progress work is not part of this cleanup.
            if p.is_symlink():
                result[str(p.relative_to(ROOT))] = {'symlink': os.readlink(p)}
            elif p.is_file():
                result[str(p.relative_to(ROOT))] = {
                    'bytes': p.stat().st_size, 'sha256': digest(p)}
    for name in PROVIDERS:
        base = ROOT / '.work/build' / name
        assert base.is_dir() and not base.is_symlink(), name
        selected = [base / rel for rel in ('.config', 'vmlinux', 'Module.symvers',
                    'System.map', 'include/config/auto.conf')]
        selected += list((base / 'include/generated').glob('*'))
        for p in selected:
            if p.is_file() and not p.is_symlink():
                result[str(p.relative_to(ROOT))] = {
                    'bytes': p.stat().st_size, 'sha256': digest(p)}
    return result


def guard():
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
            cmd = Path(os.fsdecode(argv[0])).name if argv else ''
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if cmd in ('make', 'clang', 'clang-22', 'ld.lld', 'ninja', 'sparse'):
            raise RuntimeError('Build process is running; do not race the cleanup')


def check_archive(path, wanted):
    found = {}
    with tarfile.open(path, 'r:gz') as tf:
        for m in tf:
            if m.isfile():
                f = tf.extractfile(m)
                h = hashlib.sha256()
                for b in iter(lambda: f.read(8*1024*1024), b''):
                    h.update(b)
                found[m.name] = {'bytes': m.size, 'sha256': h.hexdigest()}
            elif m.issym():
                found[m.name] = {'symlink': m.linkname}
            else:
                raise RuntimeError('Unexpected archive entry: ' + m.name)
    assert found == wanted, path


def main():
    assert Path.cwd().resolve() == ROOT
    guard()
    start = os.statvfs(ROOT)
    protected = snapshot()
    with gzip.open(REPORT / 'protected-before.json.gz', 'wt') as f:
        json.dump(protected, f, indent=2)
    print('Protected artifact/evidence snapshot recorded', len(protected), flush=True)
    manifest = []
    for name in NAMES:
        guard()
        build = ROOT / '.work/build' / name
        assert build.is_dir() and not build.is_symlink()
        assert not (build / '.git').exists()
        archive = SAVE / (name + '-debug-inputs.tar.gz')
        assert not archive.exists()
        files = sorted(entries(build))
        row = {'build': str(build.relative_to(ROOT)), 'entries': [],
               'archived': {}, 'image_content_archived': False}
        for p in files:
            rel = p.relative_to(build).as_posix()
            r = {'path': rel}
            if p.is_symlink():
                r['symlink'] = os.readlink(p)
            else:
                s = p.stat()
                r.update(bytes=s.st_size, allocated_bytes=s.st_blocks*512,
                         inode=s.st_ino, mtime_ns=s.st_mtime_ns, nlink=s.st_nlink)
            keep = (rel in KEEP or p.suffix in ('.ko', '.dtb', '.dtbo') or
                    rel.startswith(('include/', 'arch/arm64/include/generated/')))
            r['archived'] = keep
            if keep:
                row['archived'][rel] = ({'symlink': r['symlink']} if p.is_symlink()
                      else {'bytes': r['bytes'], 'sha256': digest(p)})
            elif p.name in ('Image', 'Image.gz'):
                r['sha256'] = digest(p)  # Old boot-image contents are not re-archived.
            row['entries'].append(r)
        with archive.open('wb') as output:
            with gzip.GzipFile(fileobj=output, mode='wb', compresslevel=3, mtime=0) as gz:
                with tarfile.open(fileobj=gz, mode='w', dereference=False) as tf:
                    for rel in row['archived']:
                        tf.add(build / rel, arcname=rel, recursive=False)
        check_archive(archive, row['archived'])
        row['archive'] = str(archive.relative_to(ROOT))
        row['archive_sha256'] = digest(archive)
        row['archive_bytes'] = archive.stat().st_size
        row['archive_allocated_bytes'] = archive.stat().st_blocks*512
        manifest.append(row)
        print(name, 'debug inputs compressed and hash verified', len(row['archived']), flush=True)
    with gzip.open(REPORT / 'build-manifest.json.gz', 'wt') as f:
        json.dump(manifest, f, indent=2)
    guard()
    # Verify no file in a selected tree changed during archiving before any removal.
    for row in manifest:
        build = ROOT / row['build']
        assert {p.relative_to(build).as_posix() for p in entries(build)} == {
            e['path'] for e in row['entries']}
        for r in row['entries']:
            p = build / r['path']
            if 'symlink' in r:
                assert p.is_symlink() and os.readlink(p) == r['symlink']
            else:
                s = p.stat()
                assert (s.st_size, s.st_ino, s.st_mtime_ns) == (
                    r['bytes'], r['inode'], r['mtime_ns']), p
    for row in manifest:
        shutil.rmtree(ROOT / row['build'])
        print('Removed', row['build'], flush=True)
    assert snapshot() == protected, 'Protected artifacts/evidence changed'
    for row in manifest:
        assert not (ROOT / row['build']).exists()
        check_archive(ROOT / row['archive'], row['archived'])
        assert digest(ROOT / row['archive']) == row['archive_sha256']
    end = os.statvfs(ROOT)
    result = {'removed_build_count': len(manifest),
              'removed_tree_files': sum(len(r['entries']) for r in manifest),
              'removed_tree_allocated_bytes': sum(e.get('allocated_bytes', 0)
                    for r in manifest for e in r['entries']),
              'retained_archive_allocated_bytes': sum(r['archive_allocated_bytes'] for r in manifest),
              'archived_debug_input_count': sum(len(r['archived']) for r in manifest),
              'protected_artifact_evidence_files_hash_verified': len(protected),
              'retained_provider_builds': PROVIDERS,
              'observed_linux_available_byte_change': end.f_bavail*end.f_frsize-start.f_bavail*start.f_frsize,
              'all_archives_hash_verified': True,
              'kernel_build': {'executed': False}, 'host_regression': {'executed': False},
              'device_commands': {'executed': False}, 'ci': {'executed': False}}
    (REPORT / 'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
