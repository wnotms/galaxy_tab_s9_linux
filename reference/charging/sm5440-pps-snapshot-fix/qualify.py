#!/usr/bin/env python3
"""Reuse the frozen Fedora offline artifact checks; add exact unchanged config gate."""
from pathlib import Path
import hashlib, json
D = Path(__file__).resolve().parent
ROOT = D.parents[2]
original = ROOT / 'reference/charging/sm5440-fedora-port/qualify.py'
source = original.read_text()
source = source.replace("OUT=ROOT/'out/kernel-x710-fedora'", "OUT=ROOT/'out/kernel-x710-fedora-snapshot-fix'")
exec(compile(source, str(original), 'exec'), globals())
summary = json.loads((D / 'summary.json').read_text())
new = ROOT / 'out/kernel-x710-fedora-snapshot-fix'
old = ROOT / 'out/kernel-x710-fedora'
for name in ('config', 'sm8550-samsung-gts9wifi.dtb', 'kernel.release'):
    if (new / name).read_bytes() != (old / name).read_bytes():
        raise ValueError('unchanged baseline mismatch: ' + name)
summary.update(verdict='OFFLINE_PPS_ADAPTER_FIX_PASS',
               config_delta_from_test330={}, DTB_delta_from_test330=[],
               full_port_verdict='NOT_READY',
               unresolved='Physical fixed9 return ADC proof timeout remains; no gate relaxation',
               inherited_qualification_sha256=hashlib.sha256(original.read_bytes()).hexdigest())
(D / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(dict(verdict=summary['verdict'], config_delta={}, DTB_delta=[], modules=181)))
