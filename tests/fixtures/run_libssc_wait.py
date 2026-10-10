#!/usr/bin/env python3
"""Bounded real-GLib ARM64 harness, including original/reference regressions."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
results = []
plans = {
    'original': ('owner', 'foreign-completion', 'unanswered'),
    'reference': ('owner', 'already', 'foreign-owner', 'foreign-completion'),
    'final': ('owner', 'already', 'foreign-owner', 'foreign-completion', 'cancelled', 'unanswered'),
}
for stage, modes in plans.items():
    for mode in modes:
        command = ['timeout', '2', 'qemu-aarch64', '-L', '/usr/aarch64-linux-gnu',
                   str(root / ('wait-' + stage)), mode]
        run = subprocess.run(command, capture_output=True, text=True, timeout=4)
        record = dict(stage=stage, case=mode, argv=command,
                      returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
        results.append(record)
        (root / 'WAIT_TESTS.partial.json').write_text(json.dumps(results, indent=2) + '\n')
        if stage == 'reference' and mode == 'foreign-completion':
            # The exact reference patch sleeps forever after the cond signal;
            # the local wakeup fix is justified by this bounded regression.
            assert run.returncode == 124, record
            continue
        assert run.returncode == 0, record
        value = json.loads(run.stdout)
        record['observation'] = value
        assert value['finished'] == (mode != 'unanswered'), record
        if stage == 'original':
            assert value['polls'] > 100 and value['zero_polls'] > 100, record
        else:
            assert value['polls'] <= 20 and value['zero_polls'] <= 20, record
            assert value['foreign_polls'] == 0, record
        if mode in ('owner', 'cancelled', 'unanswered'):
            assert value['heartbeats'] >= 3, record
(root / 'WAIT_TESTS.json').write_text(json.dumps(
    {'successful': True, 'cases': results, 'hardware_tested': False,
     'notes': 'Real GLib/GIO and original source; no QMI/ADSP server, no new protocol timeout.'},
    indent=2) + '\n')
print('13 ARM64/GLib cases qualified; exact reference cross-thread timeout reproduced')
