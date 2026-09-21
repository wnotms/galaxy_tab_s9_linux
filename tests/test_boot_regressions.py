"""Host regressions for init's shell supervision and mandatory ccache.

These do not emulate a tablet or establish hardware boot success.
"""
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootRegressions(unittest.TestCase):
    def test_init_survives_console_eof_and_missing_console(self):
        source = (ROOT / 'boot/bringup-init.sh').read_text()
        # Run the actual final shell handoff without mounting host filesystems.
        marker = "log 'dropping to an interactive shell; nothing was written to any block device'"
        handoff = source[source.index(marker):]
        for console in ('/dev/null', '/nonexistent-gts9-console'):
            with self.subTest(console=console), tempfile.TemporaryFile(mode='w+') as output:
                script = 'log() { printf "%s\\n" "$*"; }\n' + handoff.replace('/dev/console', console)
                proc = subprocess.Popen(
                    ['/bin/sh', '-c', script], stdin=subprocess.DEVNULL,
                    stdout=output, stderr=output, start_new_session=True,
                )
                try:
                    time.sleep(0.3)
                    self.assertIsNone(proc.poll(), 'init must survive shell exit/redirection failure')
                    output.seek(0)
                    self.assertIn('PID 1 remains alive', output.read())
                finally:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()

    def test_explicit_ccache_request_fails_when_missing(self):
        with tempfile.TemporaryDirectory() as tools:
            # dirname is needed to locate the repo before checking ccache.
            Path(tools, 'dirname').symlink_to('/usr/bin/dirname')
            result = subprocess.run(
                ['/bin/bash', str(ROOT / 'scripts/build-kernel.sh')],
                env={**os.environ, 'PATH': tools, 'JOBS': '1', 'USE_CCACHE': '1'},
                capture_output=True, text=True, timeout=5,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn('USE_CCACHE=1 requires ccache', result.stderr)
        self.assertNotIn('verified upstream', result.stdout)

    def test_invalid_ccache_mode_rejected(self):
        result = subprocess.run(
            ['/bin/bash', str(ROOT / 'scripts/build-kernel.sh')],
            env={**os.environ, 'JOBS': '1', 'USE_CCACHE': 'invalid'},
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn('USE_CCACHE must be', result.stderr)


if __name__ == '__main__':
    unittest.main()
