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
        # The earlier log message now precedes USB/storage setup. Extract
        # only the final supervision loop so this host test cannot run it.
        marker = '# PID 1 must survive EOF, an unavailable UART'
        self.assertEqual(source.count(marker), 1)
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

    def test_pogo_report_section_is_valid_shell(self):
        source = (ROOT / 'boot/bringup-init.sh').read_text()
        marker = "report 'pogo keyboard' sh -c '"
        self.assertEqual(source.count(marker), 1,
                         'the keyboard report section must exist exactly once')
        # The body is single-quoted and contains no single quote of its own, so
        # it can be lifted out and handed to the shell the initramfs really uses.
        body = source.split(marker, 1)[1].split("'", 1)[0]
        result = subprocess.run(['/bin/sh', '-n', '-c', body],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        # It has to report what a first mainline boot is judged on: whether the
        # driver bound, and the model handshake the stock keyboard answers.
        self.assertIn('samsung-pogo-keyboard', body)
        self.assertIn('EF-DX710', body)
        self.assertEqual(source.count("report 'input devices'"), 1)

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
