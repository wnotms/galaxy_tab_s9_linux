"""Remove only enumerated obsolete Kbuild intermediates; keep debug/package inputs."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path('/home/ms/Samsung/galaxy_tab_s9_linux')
REPORT = ROOT / 'reference/host-storage-cleanup/2026-10-02-reclaim'
SAVE = ROOT / '.work/host-storage-cleanup/2026-10-02-reclaim/retained-build-inputs'
NAMES = ['linux-out-container', 'linux-out-poweroff-trace',
         'linux-out-sm5714-stage2', 'linux-out-x710-charging',
         'linux-out-x710-265-policy', 'linux-out-x710-266-passive',
         'linux-out-x710-269-policy']
KEEP = {'.config', '.config.old', 'vmlinux', 'System.map', 'Module.symvers',
        'modules.order', 'modules.builtin', 'modules.builtin.modinfo',
        'modules.builtin.ranges', 'vmlinux.symvers', 'Makefile',
        'arch/arm64/boot/Image', 'arch/arm64/boot/Image.gz'}


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def snapshot():
    # Immutable final artifacts/evidence are outside the deletion scope.
    files = [p for area in ('out', 'reference') for p in (ROOT / area).rglob('*')
             if p.is_file() and not p.is_symlink() and REPORT not in p.parents]
    return {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': digest(p)}
            for p in files}


def main():
    assert ROOT.resolve() == ROOT
    assert subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT,
                                   text=True).strip() == 'test'
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if argv and Path(os.fsdecode(argv[0])).name in ('make', 'clang', 'aarch64-linux-gnu-gcc'):
            raise RuntimeError('build process running; cleanup refused')
    old = snapshot()
    (REPORT / 'protected-before.json').write_text(json.dumps(old, indent=2) + '\n')
    manifest = []
    for name in NAMES:
        build = ROOT / '.work/build' / name
        assert build.is_dir() and not build.is_symlink()
        assert not (build / '.git').exists()
        assert not (SAVE / name).exists()
        entry = {'build': str(build.relative_to(ROOT)), 'kept': [],
                 'removed_file_count': 0, 'removed_logical_bytes': 0,
                 'removed_allocated_bytes': 0}
        files = sorted(p for p in build.rglob('*') if p.is_file() or p.is_symlink())
        for p in files:
            rel = p.relative_to(build)
            if (str(rel) in KEEP or p.suffix in ('.ko', '.dtb', '.dtbo')
                    or str(rel).startswith(('include/', 'arch/arm64/include/generated/'))):
                dst = SAVE / name / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                record = {'path': str(dst.relative_to(ROOT)), 'original': str(p.relative_to(ROOT))}
                if p.is_symlink():
                    record['symlink'] = os.readlink(p)
                else:
                    record.update(bytes=p.stat().st_size, sha256=digest(p))
                p.rename(dst)  # Same filesystem: no extra image-sized disk allocation.
                entry['kept'].append(record)
            elif not p.is_symlink():
                s = p.stat()
                entry['removed_file_count'] += 1
                entry['removed_logical_bytes'] += s.st_size
                entry['removed_allocated_bytes'] += s.st_blocks * 512
        manifest.append(entry)
        (REPORT / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        shutil.rmtree(build)
        print(name, 'removed intermediate bytes', entry['removed_allocated_bytes'], flush=True)
    new = snapshot()
    assert old == new, 'final artifact/evidence changed'
    for entry in manifest:
        assert not (ROOT / entry['build']).exists()
        for item in entry['kept']:
            p = ROOT / item['path']
            if 'sha256' in item:
                assert p.stat().st_size == item['bytes'] and digest(p) == item['sha256']
    for name in ('linux-out', 'linux-out-x710-263-passive',
                 'linux-out-x710-272-passive', 'linux-out-x710-290-passive'):
        assert (ROOT / '.work/build' / name).is_dir()
    result = {'removed_build_count': len(manifest),
              'removed_intermediate_files': sum(x['removed_file_count'] for x in manifest),
              'removed_allocated_bytes': sum(x['removed_allocated_bytes'] for x in manifest),
              'retained_input_count': sum(len(x['kept']) for x in manifest),
              'all_retained_hashes_verified': True,
              'unchanged_final_artifact_evidence_files': len(old),
              'current_and_observer_provider_builds_preserved': True,
              'device_operations': False, 'build_host_tests_executed': False}
    (REPORT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
