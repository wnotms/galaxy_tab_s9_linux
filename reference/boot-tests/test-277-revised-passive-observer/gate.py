"""Reuse reviewed pure Test275 gates without altering historical evidence."""
import importlib.util
from pathlib import Path
_path = Path(__file__).resolve().parent.parent / 'test-275-passive-fresh-acquisition/gate.py'
_spec = importlib.util.spec_from_file_location('test275_frozen_gate', _path)
_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate)
ROOT, baseline, evidence = _gate.ROOT, _gate.baseline, _gate.evidence
require, identity, wifi_address = _gate.require, _gate.identity, _gate.wifi_address
observer, journal, retained_startup = _gate.observer, _gate.journal, _gate.retained_startup
