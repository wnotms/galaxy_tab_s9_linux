"""Check that host-only sync isolation retains actual record write barriers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from record_sync_fixture import record_sync_env
from test_minimal_rootfs_stages import run_library


class RecordSyncFixtureTests(unittest.TestCase):
    def test_real_syncfs_has_both_pre_and_post_rename_barriers(self):
        real_sync = shutil.which('sync', path=os.defpath)
        with tempfile.TemporaryDirectory(prefix='record scope ') as tmp:
            root = Path(tmp)
            spy = root / 'sync-spy'
            trace = root / 'trace.jsonl'
            spy.write_text(
                '#!/usr/bin/env python3\n'
                'import json, os, pathlib, sys\n'
                f'root = pathlib.Path({tmp!r})\n'
                f'with open({str(trace)!r}, "a") as log:\n'
                ' log.write(json.dumps([sys.argv[1:], '
                '(root / "gts9-minimal-last-boot.tmp").exists(), '
                '(root / "gts9-minimal-last-boot").exists()]) + "\\n")\n'
                f'os.execv({real_sync!r}, [{real_sync!r}, *sys.argv[1:]])\n')
            spy.chmod(0o755)
            with patch('record_sync_fixture.shutil.which', return_value=str(spy)):
                result = run_library(tmp, 'minimal_state_init\n'
                                     'minimal_state_stage root-mounted\n'
                                     'minimal_state_persist_enable "$GTS9_MINIMAL_LOG_DIR"\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual(observed, [[['-f', tmp], True, False],
                                        [['-f', tmp], False, True]])

    def test_fixture_rejects_changed_sync_arguments_and_keeps_parent_env(self):
        parent = dict(os.environ)
        with tempfile.TemporaryDirectory() as tmp:
            env = record_sync_env(tmp, parent)
            result = subprocess.run(['sync', '--help'], env=env, timeout=5,
                                    capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(parent, dict(os.environ))
            self.assertNotEqual(env['PATH'], parent['PATH'])
