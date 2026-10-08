#!/usr/bin/env python3
"""Owner-requested Test347 recovery endpoint; reuse qualified restoration helpers.

This one-time completion changes only the final endpoint: do not reboot Debian.
No charging activation, kernel/config changes or runtime acceptance is implied.
"""
import importlib.util
from pathlib import Path


def finish(f):
    f.configure()
    f.verify_inputs(require_push=True)
    owner = f.read(f.R / 'owner-recovery-endpoint.json')
    if owner.get('stay_in_TWRP') is not True or not owner.get('owner_reply'):
        raise ValueError('owner-requested TWRP endpoint required')
    state = f.read(f.R / 'mutation-state.json')
    pc = f.read(f.R / 'PC-return/summary.json')
    if not state.get('rollback_required') or pc.get('verdict') != 'PASS':
        raise ValueError('pending restoration and completed PC return required')
    rec = f.p.Recorder(f.R / 'recovery-completion')
    f.p.SERIAL = 'gts9wifi-0001'
    target, _ = rec.adb('target-boot-id', 'cat /proc/sys/kernel/random/boot_id', timeout=8)
    if target.strip().replace('-', '') != state['candidate_boot_id']:
        raise ValueError('unexpected boot before recovery')
    rec.adb('target-boots', 'journalctl --list-boots --no-pager', timeout=20)
    f.h.enter_recovery(rec)
    f.base.transfer(rec)
    raw, _ = rec.adb('partitions-before', f.h.PARTS, timeout=20)
    current = f.base.restoration_layout(raw)
    rec.adb('remount-rw', 'mount -o remount,rw /mnt/debian', timeout=10)
    root = '/mnt/debian/usr/lib/modules'
    saved, _ = rec.adb('module-layout',
        f'set -e; test "$(cat /mnt/debian/etc/machine-id)" = 3c2a1b8f2d624db4b5ffdc836050fcf6; '
        f'if test -d {root}/.gts9-test347-original; then echo saved; else echo no-saved; fi',
        timeout=10)
    if saved.strip() == 'saved':
        rec.adb('restore-modules',
            f'sh {f.h.TMP}/module-swap.sh /mnt/debian restore {f.h.TMP}/rollback-modules.sha256',
            timeout=25)
    elif saved.strip() != 'no-saved' or current != f.PACKAGE['baseline_partitions']['boot']:
        raise ValueError('paired original modules missing')
    f.h.verify_modules(rec, 'restored-modules', 'rollback-modules.sha256')
    if current != f.PACKAGE['baseline_partitions']['boot']:
        f.h.write_boot(rec, 'restore-boot', 'rollback-accepted331-boot.img',
                       current, f.PACKAGE['baseline_partitions']['boot'])
    raw, _ = rec.adb('partitions-after', f.h.PARTS, timeout=20)
    f.h.require_partitions(raw, f.PACKAGE['baseline_partitions'])
    f.h.clear_unmount(rec)
    identity, _ = rec.adb('final-twrp-identity',
        'getprop ro.product.device; getprop ro.twrp.version; uname -a; id; cat /proc/mounts',
        timeout=10)
    if 'gts9wifi' not in identity or 'uid=0' not in identity or '7.2.0-rc3' in identity:
        raise ValueError('final TWRP identity missing')
    if any(' /mnt/debian ' in line for line in identity.splitlines()):
        raise ValueError('Debian root remained mounted')
    result = dict(verdict='ACCEPTED331_ALLFIVE_181_RESTORED_STAYING_TWRP',
        rollback_required=False, final_endpoint='TWRP', modules=181,
        allfive_verified=True, Debian_reboot_executed=False,
        restored_Debian_runtime_acceptance_executed=False,
        owner_endpoint_override=True)
    f.write(rec.folder / 'summary.json', result)
    f.write(f.R / 'mutation-state.json', dict(result, phase='accepted331-restored-staying-TWRP'))
    return result


if __name__ == '__main__':
    import json
    spec = importlib.util.spec_from_file_location('completion347_flow', Path(__file__).with_name('host_flow.py'))
    flow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flow)
    print(json.dumps(finish(flow), indent=2), flush=True)
