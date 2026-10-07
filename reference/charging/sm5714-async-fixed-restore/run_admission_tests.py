#!/usr/bin/env python3
"""Run affected actual C adapter/lease/coherence and current observer tests only."""
import contextlib, json, sys, time, unittest
from pathlib import Path
D = Path(__file__).resolve().parent
ROOT = D.parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
modules = ['test_pps_restore_admission', 'test_ordinary_charge_window', 'test_pps_off_evidence', 'test_charging_wifi_discovery']
suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
def flatten(s):
    for x in s:
        if isinstance(x, unittest.TestSuite):
            yield from flatten(x)
        else:
            yield x
ids = [x.id() for x in flatten(suite)]
start = time.monotonic()
with (D / 'admission-tests.txt').open('w') as stream:
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream).run(suite)
record = dict(executed=True, selected=ids, tests=result.testsRun,
              failures=len(result.failures), errors=len(result.errors),
              skips=len(result.skipped), seconds=time.monotonic()-start,
              coverage=modules, full_suite_executed=False,
              reason='New Test337 actual bounded discovery/admission integration and captured Test336 ordinary charge packet; unchanged kernel qualification reused',
              device_commands_executed=False)
(D / 'admission-tests.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k != 'selected'}))
raise SystemExit(not result.wasSuccessful() or bool(result.skipped))
