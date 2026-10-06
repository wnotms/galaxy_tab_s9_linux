#!/usr/bin/env python3
"""Reuse artifact qualification, preserving the exact accepted config and DTB."""
from pathlib import Path
import hashlib, json
D = Path(__file__).resolve().parent
ROOT = D.parents[2]
original = ROOT / 'reference/charging/sm5440-fedora-port/qualify.py'
source = original.read_text().replace("OUT=ROOT/'out/kernel-x710-fedora'", "OUT=ROOT/'out/kernel-x710-fedora-fixed-return'")
exec(compile(source, str(original), 'exec'), globals())
summary = json.loads((D / 'summary.json').read_text())
new = ROOT / 'out/kernel-x710-fedora-fixed-return'
old = ROOT / 'out/kernel-x710-fedora-snapshot-fix'
for name in ('config', 'sm8550-samsung-gts9wifi.dtb', 'kernel.release'):
    if (new / name).read_bytes() != (old / name).read_bytes():
        raise ValueError('unchanged Test331 baseline mismatch: ' + name)
summary.update(verdict='OFFLINE_FIXED_RETURN_WINDOW_PASS',
               config_delta_from_test331={}, DTB_delta_from_test331=[],
               full_port_verdict='NOT_READY',
               unresolved='Corrected fixed-return proof and active PPS require separately registered physical acceptance',
               inherited_qualification_sha256=hashlib.sha256(original.read_bytes()).hexdigest())
(D / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(dict(verdict=summary['verdict'], config_delta={}, DTB_delta=[], modules=181)))
