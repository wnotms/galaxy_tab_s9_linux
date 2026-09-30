#!/usr/bin/env python3
"""Registered recovery of the exact accepted Test260 pair after first failure."""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p

A = Path(__file__).resolve().parent
M = json.loads((A / 'PACKAGE.json').read_text())
SEALED = json.loads((A / 'STAGED_FILES.json').read_text())
stage = Path('/mnt/d/android/gts9-active/gts9-test263')
win = 'D:/android/gts9-active/gts9-test263/'
mode = sys.argv[1] if len(sys.argv) == 2 else ''
assert mode in {'enter', 'restore'}, 'explicit rollback phase required'
folder = A / ('rollback-' + mode)
assert not folder.exists(), 'never overwrite recovery evidence'
r = p.Recorder(folder)


def push(name):
    path = Path(SEALED[name]['path'])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == SEALED[name]['sha256'], name
    remote = '/tmp/test263-a01-rollback-' + name
    local = ('D:/android/gts9-active/gts9-test263/' if name == 'module-swap.sh' else win) + name
    r.host_adb('push-' + name, '-s', p.SERIAL, 'push', local, remote, timeout=75)
    assert r.adb('hash-' + name, 'sha256sum ' + remote, 30)[0].split()[0] == digest
    return remote


if mode == 'enter':
    failure_path = A / 'pd-observation/summary.json'
    if not failure_path.exists():
        failure_path = A / 'observation/summary.json'
    failure = json.loads(failure_path.read_text())
    assert failure['verdict'].startswith('STOP') and failure['rollback_required']
    p.SERIAL = 'gts9wifi-0001'
    raw = r.adb('failed-boot-identity', 'set -e; cat /proc/sys/kernel/random/boot_id; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes', 30)[0].splitlines()
    assert p.evidence.canonical_boot_id(raw[0]) == (failure['boot_id'] or failure['attributed_boot_id'])
    assert raw[1].split()[0] == M['artifacts']['out/kernel-x710-263-passive/config']['sha256']
    assert raw[2].split()[0] == M['artifacts']['out/kernel-x710-263-passive/kernel-notes.bin']['sha256']
    helper = push('gts9-debian-to-recovery.sh')
    assert '(empty, boots mainline)' in r.adb('bcb-check', 'TMPDIR=/tmp sh ' + helper + ' --check')[0]
    r.adb('bcb-request', 'TMPDIR=/tmp sh ' + helper + ' --yes --no-reboot', 25)
    r.adb('normal-reboot', 'systemctl reboot', 20, required=False)
    start = time.monotonic()
    for n in range(45):
        raw, _ = r.host_adb(f'wait-{n:02}', 'devices', '-l', timeout=8, required=False)
        if 'R52X10045LT' in raw and 'recovery' in raw:
            p.write_json(folder / 'summary.json', {'verdict': 'TWRP reached for registered rollback', 'seconds': round(time.monotonic() - start, 3)})
            print('TWRP available for rollback', flush=True)
            break
        time.sleep(2)
    else:
        raise RuntimeError('STOP: recovery not reached; do not change images blindly')
else:
    p.SERIAL = 'R52X10045LT'
    raw = r.adb('recovery-identity', 'getprop ro.product.model; getprop ro.twrp.version; cat /proc/sys/kernel/random/boot_id')[0].splitlines()
    assert raw[0] == 'SM-X710' and raw[1].startswith('3.7')
    recovery_boot = p.evidence.canonical_boot_id(raw[2])
    raw = r.adb('candidate-partitions', 'set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/block/by-name/$n; done', 75)[0]
    assert p.parse_hashes(raw, '/dev/block/by-name/') == M['candidate_partitions']
    files = {name: push(name) for name in ('rollback-test260-boot.img', 'rollback-test260-vendor_boot.img', 'test260-rollback-modules.sha256', 'module-swap.sh', 'twrp-mount-debian.sh')}
    r.adb('mount-readonly', 'sh ' + files['twrp-mount-debian.sh'], 25)
    raw = r.adb('root-identity', 'set -e; cat /mnt/debian/etc/machine-id; grep " /mnt/debian " /proc/mounts; dd if=/dev/block/mmcblk1p1 bs=1 skip=1128 count=16 2>/dev/null | od -An -tx1; test -d /mnt/debian/usr/lib/modules/.gts9-test263-original; test ! -e /mnt/debian/usr/lib/modules/.gts9-test263-tested; test ! -e /mnt/debian/usr/lib/modules/.gts9-test263-stage', 25)[0]
    assert raw.splitlines()[0] == '3c2a1b8f2d624db4b5ffdc836050fcf6'
    assert '/dev/block/mmcblk1p1 /mnt/debian ext4 ro,' in raw
    assert '85 18 19 a7 0d 96 42 17 b6 4a ae ee e5 d8 be 61' in raw
    assert p.evidence.canonical_boot_id(r.adb('same-recovery-boot', 'cat /proc/sys/kernel/random/boot_id')[0]) == recovery_boot
    r.adb('remount-rw', 'set -e; umount /mnt/debian; mount -t ext4 -o rw /dev/block/mmcblk1p1 /mnt/debian; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6', 25)
    r.adb('restore-modules', 'sh ' + files['module-swap.sh'] + ' /mnt/debian restore ' + files['test260-rollback-modules.sha256'], 120)
    for name in ('boot', 'vendor_boot'):
        path = files['rollback-test260-' + name + '.img']
        r.adb('restore-' + name, 'set -e; test "$(blockdev --getsize64 /dev/block/by-name/' + name + ')" = 100663296; dd if=' + path + ' of=/dev/block/by-name/' + name + ' bs=4M; sync', 70)
    raw = r.adb('baseline-partitions-readback', 'set -e; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/block/by-name/$n; done', 75)[0]
    assert p.parse_hashes(raw, '/dev/block/by-name/') == M['baseline_partitions']
    raw = r.adb('clear-bcb-unmount', 'set -e; test "$(blockdev --getsize64 /dev/block/by-name/misc)" = 1048576; dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc; sync; umount /mnt/debian; dd if=/dev/block/by-name/misc bs=32 count=1 2>/dev/null | od -An -v -tx1', 40)[0]
    assert len(raw.split()) == 32 and set(raw.split()) == {'00'}
    p.write_json(folder / 'summary.json', {'verdict': 'accepted Test260 boot/vendor/modules restored and readback verified; TWRP remains', 'partitions': M['baseline_partitions'], 'module_file_count': 181, 'tested_candidate_modules_retained': True, 'bcb_cleared': True, 'root_unmounted': True})
    print('Rollback pair restored; normal baseline boot may proceed', flush=True)
