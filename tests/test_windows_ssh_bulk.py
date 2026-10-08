"""Exercise real partial-send code; no tablet or Windows dependency."""
from pathlib import Path
import shlex
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import windows_ssh_bulk as b


class BulkSSHTests(unittest.TestCase):
    def test_partial_send_would_block_and_interrupt_never_duplicate_bytes(self):
        output = bytearray()
        actions = iter([2, BlockingIOError(), 1, InterruptedError(), 3])
        class Socket:
            def send(self, data):
                action = next(actions)
                if isinstance(action, Exception):
                    raise action
                output.extend(data[:action])
                return action
        sock = Socket()
        with patch.object(b.select, 'select', return_value=([], [sock], [])):
            b.send_pending(sock, b'\x00\xffabcd', threading.Event())
        self.assertEqual(output, b'\x00\xffabcd')

    def test_deadline_refreshed_only_by_successful_progress(self):
        class Socket:
            def send(self, data):return 1
        sock = Socket()
        # Two bytes may take >30 seconds overall if each send progresses.
        with patch.object(b.time, 'monotonic', side_effect=[0, 29, 29, 58, 58]), \
             patch.object(b.select, 'select', return_value=([], [sock], [])):
            b.send_pending(sock, b'ab', threading.Event())
        with patch.object(b.time, 'monotonic', side_effect=[0, 29, 31]), \
             patch.object(b.select, 'select', return_value=([], [], [])), \
             self.assertRaises(TimeoutError):
            b.send_pending(sock, b'ab', threading.Event())

    def test_closed_or_cancelled_socket_fails_without_retry(self):
        class Socket:
            def send(self, data):return 0
        sock = Socket()
        with patch.object(b.select, 'select', return_value=([], [sock], [])), self.assertRaises(ConnectionError):
            b.send_pending(sock, b'a', threading.Event())
        stop = threading.Event();stop.set()
        with self.assertRaises(ConnectionAbortedError):b.send_pending(sock, b'a', stop)

    def test_proxy_preserves_identity_and_has_only_public_code(self):
        with patch('windows_ssh_transport.Path.is_file', return_value=True):
            argv = b.bulk_ssh_argv('/private/key', '/private/trust', 'accepted', '10.1.2.3', 'cat > cache')
        proxy = next(x.removeprefix('ProxyCommand=') for x in argv if x.startswith('ProxyCommand='))
        self.assertEqual(shlex.split(proxy), [b.WINDOWS_PYTHON, '-u', '-c', b.PROXY, '10.1.2.3'])
        self.assertNotIn('/private/', proxy)
        self.assertIn('StrictHostKeyChecking=yes', argv)
        self.assertIn('HostKeyAlias=accepted', argv)
        self.assertEqual(argv[-2:], ['root@10.1.2.3', 'cat > cache'])
        compile(b.PROXY, '<bulk-proxy>', 'exec')

    def test_invalid_endpoints_and_missing_native_executable_rejected(self):
        with self.assertRaises(ValueError):b.bulk_ssh_argv('k', 'h', 'a', '8.8.8.8', 'id')
        with patch('windows_ssh_transport.Path.is_file', return_value=False), self.assertRaises(ValueError):
            b.bulk_ssh_argv('k', 'h', 'a', '10.1.2.3', 'id')


if __name__ == '__main__':unittest.main()
