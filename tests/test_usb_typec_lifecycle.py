import gzip
import hashlib
import importlib.util
from pathlib import Path
import signal
import os
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('usb_lifecycle', ROOT/'userspace/adbd/typec-lifecycle.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TypecLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        config = b'# CONFIG_HVC_DCC is not set\n'
        notes = b'qualified-test-notes'
        self.profile = dict(machine_id='accepted-machine', release='accepted-release',
                            config_sha256=hashlib.sha256(config).hexdigest(),
                            notes_sha256=hashlib.sha256(notes).hexdigest())
        self.put('etc/machine-id', 'accepted-machine')
        self.put('proc/sys/kernel/random/boot_id', 'accepted-boot')
        self.put('proc/sys/kernel/osrelease', 'accepted-release')
        self.put('proc/config.gz', gzip.compress(config))
        self.put('sys/kernel/notes', notes)
        self.put('sys/module/sm5440_fedora/parameters/direct_charge', 'N')
        self.put('sys/class/typec/port0/power_role', '[sink]')
        self.put('sys/class/typec/port0/data_role', '[device]')
        self.put('sys/class/power_supply/sm5714-usb/online', '0')
        self.g = self.root/'sys/kernel/config/usb_gadget/gts9'
        for name, value in [('UDC', 'a600000.usb'), ('idVendor', '0x0525'), ('idProduct', '0xa4a7')]:
            self.put(str((self.g/name).relative_to(self.root)), value)
        for name in ('ffs.adb', 'ncm.usb0'):
            dest = self.g/'functions'/name
            dest.mkdir(parents=True)
            link = self.g/'configs/c.1'/name
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(dest)
        self.guard = m.Gadget(self.root, self.profile)

    def put(self, name, value):
        p = self.root/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value if isinstance(value, bytes) else value.encode())

    def attach(self):
        (self.root/'sys/class/typec/port0-partner').mkdir()
        self.put('sys/class/power_supply/sm5714-usb/online', '1')

    def test_stale_detach_rebind_and_no_repeat_on_healthy_link(self):
        edges = m.CableEdges()
        self.assertIsNone(edges.observe(self.guard.state(), 0))
        self.assertEqual(self.guard.apply(edges.observe(self.guard.state(), 1)), 'unbind')
        self.assertEqual((self.g/'UDC').read_text(), '\n')
        self.assertIsNone(self.guard.apply('detached'))
        self.attach()
        self.assertIsNone(edges.observe(self.guard.state(), 2))
        self.assertEqual(self.guard.apply(edges.observe(self.guard.state(), 3)), 'bind')
        self.assertIsNone(self.guard.apply('attached'))
        self.assertEqual(self.guard.describe(), self.guard.fingerprint)

    def test_short_detach_does_not_reset(self):
        e = m.CableEdges()
        self.assertIsNone(e.observe('detached', 0))
        self.assertIsNone(e.observe('attached', .5))
        self.attach()
        self.assertIsNone(self.guard.apply(e.observe('attached', 1.5)))

    def test_hard_reset_and_mixed_attach_are_unknown(self):
        self.assertEqual(m.cable_state(True, 0), 'unknown')
        self.assertEqual(m.cable_state(False, 1), 'unknown')
        self.attach()
        self.put('sys/class/power_supply/sm5714-usb/online', '0')
        self.assertIsNone(self.guard.apply('detached'))
        self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb')

    def test_unknown_resets_pending_debounce(self):
        e = m.CableEdges()
        e.observe('detached', 0)
        self.assertIsNone(e.observe('unknown', .9))
        self.assertIsNone(e.observe('detached', 2))

    def test_invalid_online_does_not_write(self):
        self.put('sys/class/power_supply/sm5714-usb/online', 'error')
        with self.assertRaises(m.GuardError):
            self.guard.apply('detached')
        self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb')

    def test_external_unbind_not_adopted(self):
        (self.g/'UDC').write_text('\n')
        with self.assertRaises(m.GuardError):
            self.guard.apply('detached')
        with self.assertRaises(m.GuardError):
            m.Gadget(self.root, self.profile)

    def test_external_controller_not_overwritten_during_restore(self):
        self.guard.apply('detached')
        (self.g/'UDC').write_text('another-controller')
        with self.assertRaises(m.GuardError):
            self.guard.restore()
        self.assertEqual((self.g/'UDC').read_text(), 'another-controller')

    def test_layout_drift_rejected(self):
        (self.g/'idProduct').write_text('0xffff')
        with self.assertRaises(m.GuardError):
            self.guard.apply('detached')
        self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb')

    def test_identity_drift_rejected(self):
        for path, value in [('sys/kernel/notes', 'other'),
                            ('proc/sys/kernel/random/boot_id', 'other'),
                            ('sys/module/sm5440_fedora/parameters/direct_charge', 'Y'),
                            ('sys/class/typec/port0/data_role', '[host]')]:
            p = self.root/path
            original = p.read_bytes()
            with self.subTest(path=path):
                p.write_text(value)
                with self.assertRaises(m.GuardError):
                    self.guard.apply('detached')
                self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb')
                p.write_bytes(original)

    def test_service_stop_restores_only_owned_empty_binding(self):
        self.guard.apply('detached')
        self.guard.restore()
        self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb\n')
        self.assertFalse(self.guard.owned_unbound)
        self.guard.restore()

    def test_io_read_fault_restores_owned_binding(self):
        self.guard.apply('detached')
        (self.root/'sys/class/power_supply/sm5714-usb/online').unlink()
        with self.assertRaises(OSError):
            self.guard.state()
        self.guard.restore()
        self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb\n')

    def test_signal_mask_covers_write_and_ownership(self):
        with patch.object(m.signal, 'pthread_sigmask', return_value=set()) as mask:
            self.guard.apply('detached')
        self.assertEqual(mask.call_count, 2)
        self.assertTrue(self.guard.owned_unbound)

    def test_rebind_io_failure_keeps_recovery_ownership(self):
        self.guard.apply('detached')
        self.attach()
        real = Path.write_text
        def fail(p, value, *args, **kwargs):
            if p == self.g/'UDC':
                raise OSError('injected bind failure')
            return real(p, value, *args, **kwargs)
        with patch.object(Path, 'write_text', fail):
            with self.assertRaises(OSError):
                self.guard.apply('attached')
        self.assertTrue(self.guard.owned_unbound)
        self.guard.restore()
        self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb\n')

    def test_event_origin_and_filter(self):
        event = b'remove@/path\0SUBSYSTEM=typec\0DEVPATH=/path\0'
        self.assertTrue(m.relevant_uevent(event, (0, 1)))
        self.assertFalse(m.relevant_uevent(event, (123, 1)))
        self.assertFalse(m.relevant_uevent(event+b'SUBSYSTEM=typec\0', (0, 1)))
        self.assertFalse(m.relevant_uevent(b'change@x\0SUBSYSTEM=input\0', (0, 1)))
        self.assertTrue(m.relevant_uevent(b'change@x\0SUBSYSTEM=power_supply\0DEVPATH=/devices/sm5714-usb\0', (0, 1)))
        self.assertFalse(m.relevant_uevent(b'change@x\0SUBSYSTEM=power_supply\0DEVPATH=/devices/sm5714-battery\0', (0, 1)))

    def test_receive_error_restores_binding_and_does_not_restart(self):
        self.guard.apply('detached')
        with patch.object(m.select, 'select', return_value=([object()], [], [])):
            sock = unittest.mock.Mock()
            sock.recvfrom.side_effect = OSError('netlink buffer overflow')
            with self.assertRaises(OSError):
                m.serve(self.guard, sock)
        self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb\n')
        unit = (ROOT/'userspace/adbd/gts9-usb-typec-lifecycle.service').read_text()
        self.assertIn('Restart=no', unit)

    def test_actual_event_loop_unbinds_then_binds_once(self):
        clock = [0.0]
        sock = unittest.mock.Mock()
        sock.recvfrom.return_value = (b'add@x\0SUBSYSTEM=typec\0', (0, 1))
        events = 0
        writes = []
        real_write = Path.write_text
        def record(p, value, *args, **kwargs):
            if p == self.g/'UDC':
                writes.append(value)
            return real_write(p, value, *args, **kwargs)
        def select(_, __, ___, timeout):
            nonlocal events
            if timeout is not None:
                clock[0] += timeout
                return [], [], []
            events += 1
            if events == 1:
                self.attach()
                return [sock], [], []
            raise InterruptedError('normal service stop')
        with patch.object(m.select, 'select', select), patch.object(Path, 'write_text', record):
            with self.assertRaises(InterruptedError):
                m.serve(self.guard, sock, lambda: clock[0])
        self.assertEqual(writes, ['\n', 'a600000.usb\n'])
        self.assertFalse(self.guard.owned_unbound)

    def test_actual_stop_signal_cannot_strand_successful_unbind(self):
        old = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, old)
        def stopped(signum, frame):
            raise InterruptedError('service stop')
        signal.signal(signal.SIGTERM, stopped)
        real = Path.write_text
        def signalled(p, value, *args, **kwargs):
            result = real(p, value, *args, **kwargs)
            if p == self.g/'UDC' and value == '\n':
                os.kill(os.getpid(), signal.SIGTERM)
            return result
        with patch.object(Path, 'write_text', signalled):
            with self.assertRaises(InterruptedError):
                self.guard.apply('detached')
        self.assertTrue(self.guard.owned_unbound)
        self.guard.restore()
        self.assertEqual((self.g/'UDC').read_text(), 'a600000.usb\n')


if __name__ == '__main__':
    unittest.main()
