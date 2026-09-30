#!/usr/bin/env python3
"""One ordinary TWRP-to-Debian boot; ADB attribution before observation."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e

A = Path(__file__).resolve().parent
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT) == subprocess.check_output(['git', 'rev-parse', 'origin/test'], cwd=ROOT)
assert json.loads((A / 'install/summary.json').read_text())['root_unmounted']
r = p.Recorder(A / 'candidate-boot')
M = json.loads((A.parent / 'ARTIFACTS.json').read_text())
base = json.loads((A / 'preflight/summary.json').read_text())
p.SERIAL = 'R52X10045LT'
r.adb('normal-system-boot', 'reboot', 15, required=False)
start = time.monotonic()
for count in range(60):
    devices, _ = r.host_adb(f'wait-{count:02}', 'devices', '-l', timeout=8, required=False)
    if 'gts9wifi-0001' in devices and 'device' in devices:
        p.SERIAL = 'gts9wifi-0001'
        lines = r.adb('new-identity', 'set -e; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; '
                      'zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes', 20)[0].splitlines()
        boot = e.canonical_boot_id(lines[0])
        assert boot != base['boot_id']
        assert lines[2].split()[0] == M['artifacts']['out/kernel-x710-260-passive/config']['sha256']
        assert lines[3].split()[0] == M['artifacts']['out/kernel-x710-260-passive/kernel-notes.bin']['sha256']
        history = r.adb('boots-after', 'journalctl --list-boots --no-pager --no-legend', 15)[0]
        attribution = e.attribute(base['boot_id'], boot, (A / 'preflight/boots-before.txt').read_text(), history)
        p.write_json(r.folder / 'summary.json', {'verdict': 'new candidate boot attributed; observation pending',
                    'boot_id': boot, 'attribution': attribution, 'seconds': round(time.monotonic() - start, 3)})
        print('New candidate boot attributed', boot, flush=True)
        break
    time.sleep(2)
else:
    raise RuntimeError('candidate boot not observed; STOP, no reboot retry')
