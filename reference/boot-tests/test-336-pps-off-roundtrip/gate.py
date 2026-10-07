"""Test336 admission adapter; historical Test334 gates remain unchanged."""
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parent.parent / 'test-334-fixed-return-soc-margin/gate.py'
spec = importlib.util.spec_from_file_location('fixed334_frozen_gate', path)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
pump = old.pump
preparation_margin = old.preparation_margin


def identity(sections, plan, phase, expected=None, restoration=False):
    if phase != 'baseline':
        raise ValueError('candidate admitted only through PPS-aware WiFi observer')
    if sections['direct-default'].strip() not in ('N', '0') or sections.get('pps-check', 'absent').strip() not in ('absent', 'N', '0') or sections['driver'].strip().split('/')[-1] != 'sm5440-fedora':
        raise ValueError('accepted331 OFF provider')
    effective = dict(plan)
    if restoration:
        # Restore can follow accumulated normal charging beyond the entry SOC
        # limit; this never relaxes candidate admission/activation gates.
        effective.update(flash_soc_min=0, flash_soc_max=101, vbat_max_uv=4440001)
    return old.identity(sections, effective, phase, expected)
