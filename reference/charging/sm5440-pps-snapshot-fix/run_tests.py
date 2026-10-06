#!/usr/bin/env python3
"""Run affected actual C adapter/lease/coherence and current observer tests only."""
import contextlib, json, sys, time, unittest
from pathlib import Path
D = Path(__file__).resolve().parent
ROOT = D.parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
modules = ['test_sm5440_fedora', 'test_x710_pps_guard',
           'test_sm5714_owned_pps', 'test_sm5714_fixed_release',
           'test_sm5714_pack_snapshot', 'test_sm5714_runtime_snapshot',
           'test_sm5714_fixed_restore', 'test_sm5714_stage2_pd']
suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
def flatten(s):
    for x in s:
        if isinstance(x, unittest.TestSuite):
            yield from flatten(x)
        else:
            yield x
ids = [x.id() for x in flatten(suite)]
start = time.monotonic()
with (D / 'tests.txt').open('w') as stream:
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream).run(suite)
record = dict(executed=True, selected=ids, tests=result.testsRun,
              failures=len(result.failures), errors=len(result.errors),
              skips=len(result.skipped), seconds=time.monotonic()-start,
              coverage=modules, full_suite_executed=False,
              reason='Actual adapter, its existing lease/epoch/fixed-return APIs, profile gate and new observer; routing unchanged',
              device_commands_executed=False)
(D / 'host-tests.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k != 'selected'}))
raise SystemExit(not result.wasSuccessful() or bool(result.skipped))
