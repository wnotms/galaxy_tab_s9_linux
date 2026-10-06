import asyncio
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import charging_wifi_discovery as discovery


EXPECTED = discovery.Identity('a' * 32, 'b' * 64, 'c' * 64, 'd' * 32)
PACKET = '\n'.join([EXPECTED.machine_id, EXPECTED.boot_id,
                    EXPECTED.config_sha256 + '  -',
                    EXPECTED.notes_sha256 + '  /sys/kernel/notes']) + '\n'
MATCH = dict(machine_id=EXPECTED.machine_id, boot_id=EXPECTED.boot_id,
             config_sha256=EXPECTED.config_sha256, notes_sha256=EXPECTED.notes_sha256)


class Files(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key, self.trust = self.root / 'key', self.root / 'known-hosts'
        self.key.write_text('host test placeholder; never used for real authentication')
        self.trust.write_text('enrolled ssh-ed25519 AAAA\n')
        self.key.chmod(0o600)
        self.trust.chmod(0o600)
        self.settings = discovery.Settings('10.0.0.7', self.key, self.trust, 'enrolled')
        self.events = []

    def emit(self, kind, **fields):
        self.events.append(dict(kind=kind, **fields))


class InputGates(Files):
    def test_private_network_is_exactly_24(self):
        self.assertEqual(str(self.settings.validate()), '10.0.0.0/24')

    def test_no_public_loopback_link_local_or_ipv6_scan(self):
        for address in ('8.8.8.8', '127.0.0.1', '169.254.42.1', '0.0.0.0', '::1'):
            with self.assertRaises(ValueError):
                replace(self.settings, previous_ip=address).validate()

    def test_broadcast_and_network_address_rejected(self):
        for address in ('10.0.0.0', '10.0.0.255'):
            with self.assertRaises(ValueError):
                replace(self.settings, previous_ip=address).validate()

    def test_no_unbounded_timeout_or_parallelism(self):
        for change in ({'total_seconds': 91}, {'tcp_seconds': 4}, {'tcp_seconds': 0},
                       {'ssh_seconds': 9}, {'concurrency': 17}, {'concurrency': 0}):
            with self.assertRaises(ValueError):
                replace(self.settings, **change).validate()

    def test_unenrolled_alias_rejected_without_learning_key(self):
        before = self.trust.read_bytes()
        with self.assertRaises(ValueError):
            replace(self.settings, alias='other').validate()
        self.assertEqual(self.trust.read_bytes(), before)

    def test_loose_permissions_and_symlink_rejected(self):
        self.trust.chmod(0o644)
        with self.assertRaises(ValueError):
            self.settings.validate()
        self.trust.chmod(0o600)
        link = self.root / 'link'
        link.symlink_to(self.trust)
        with self.assertRaises(ValueError):
            replace(self.settings, known_hosts=link).validate()

    def test_identity_packet_and_canonical_boot(self):
        self.assertEqual(discovery.parse_identity(PACKET, EXPECTED), MATCH)

    def test_wrong_machine_config_notes_or_boot_cannot_match(self):
        for old, new in [('a' * 32, 'e' * 32), ('b' * 64, 'f' * 64),
                         ('c' * 64, 'e' * 64), ('d' * 32, 'f' * 32)]:
            self.assertIsNone(discovery.parse_identity(PACKET.replace(old, new), EXPECTED))

    def test_malformed_empty_extra_rows_and_missing_hash_paths(self):
        for packet in ('', PACKET + 'extra\n', PACKET.replace('  -', ''),
                       PACKET.replace('/sys/kernel/notes', 'other'), PACKET.replace('d' * 32, 'bad')):
            self.assertIsNone(discovery.parse_identity(packet, EXPECTED))

    def test_no_expected_boot_returns_actual_for_callers_attribution_gate(self):
        self.assertEqual(discovery.parse_identity(PACKET, replace(EXPECTED, boot_id='')), MATCH)

    def test_invalid_identity_rejected_before_network(self):
        for expected in (replace(EXPECTED, machine_id='bad'), replace(EXPECTED, boot_id='bad'),
                         replace(EXPECTED, notes_sha256='')):
            with self.assertRaises(ValueError):
                expected.validate()


class Process:
    def __init__(self, status=0, output=PACKET, block=False):
        self.returncode = None if block else status
        self.output = output
        self.block = block
        self.killed = False
        self.release = asyncio.Event()

    async def communicate(self):
        if self.block:
            await self.release.wait()
        return self.output.encode(), b'Host key verification failed.' if self.returncode == 255 else b''

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.release.set()


class Authentication(Files):
    def test_tcp_probe_closes_without_waiting_for_peer_fin(self):
        writer = Mock()
        with patch.object(asyncio, 'open_connection', AsyncMock(return_value=(None, writer))):
            self.assertTrue(asyncio.run(discovery.probe_tcp('10.0.0.7', 1)))
        writer.close.assert_called_once()
        writer.transport.abort.assert_called_once()
        writer.wait_closed.assert_not_called()

    def test_real_argv_strict_trust_and_read_only_identity(self):
        process = Process()
        with patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)) as create:
            result = asyncio.run(discovery.identify('10.0.0.7', 1, self.settings, EXPECTED, self.emit))
        argv = create.call_args.args
        self.assertIn('StrictHostKeyChecking=yes', argv)
        self.assertIn('UserKnownHostsFile=' + str(self.trust), argv)
        self.assertIn('HostKeyAlias=enrolled', argv)
        self.assertEqual(argv[-1], discovery.IDENTITY_COMMAND)
        self.assertNotIn('accept-new', ' '.join(argv))
        self.assertEqual(result, MATCH)

    def test_unknown_key_failure_cannot_be_overridden_by_matching_stdout(self):
        with patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=Process(255))):
            self.assertIsNone(asyncio.run(discovery.identify('10.0.0.7', 1, self.settings, EXPECTED, self.emit)))
        self.assertFalse(self.events[-1]['matched'])

    def test_transport_timeout_kills_and_drains_child(self):
        async def scenario():
            process = Process(block=True)
            with patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)):
                result = await discovery.identify('10.0.0.7', .01, self.settings, EXPECTED, self.emit)
            self.assertIsNone(result)
            self.assertTrue(process.killed)
        asyncio.run(scenario())

    def test_cancellation_kills_child_before_return(self):
        async def scenario():
            process = Process(block=True)
            with patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)):
                task = asyncio.create_task(discovery.identify('10.0.0.7', 3, self.settings, EXPECTED, self.emit))
                await asyncio.sleep(.001)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertTrue(process.killed)
        asyncio.run(scenario())


class Search(Files):
    def test_changed_enrollment_rejects_matching_identity(self):
        async def auth(*args):
            self.trust.write_text('enrolled ssh-ed25519 BBBB\n')
            return MATCH
        with self.assertRaisesRegex(ValueError, 'changed'):
            asyncio.run(discovery.discover(self.settings, EXPECTED, self.emit,
                                          AsyncMock(return_value=True), auth))

    def test_recent_enrolled_ip_bypasses_false_negative_tcp_prefilter(self):
        probe = AsyncMock(return_value=False)
        auth = AsyncMock(return_value=MATCH)
        result = asyncio.run(discovery.discover(self.settings, EXPECTED, self.emit, probe, auth))
        self.assertEqual(result['address'], '10.0.0.7')
        probe.assert_not_called()
        self.assertEqual(auth.call_count, 1)
        self.assertEqual(self.events[-1]['kind'], 'drained')

    def test_changed_address_and_unknown_neighbor_identity(self):
        async def probe(address, timeout):
            return address in ('10.0.0.2', '10.0.0.19')
        async def auth(address, seconds, settings, expected, emit):
            return MATCH if address == '10.0.0.19' else None
        result = asyncio.run(discovery.discover(self.settings, EXPECTED, self.emit, probe, auth))
        self.assertEqual(result['address'], '10.0.0.19')
        addresses = [x['address'] for x in self.events if x['kind'] == 'tcp']
        self.assertNotIn('10.0.0.0', addresses)
        self.assertNotIn('10.0.0.255', addresses)
        self.assertTrue(all(x.startswith('10.0.0.') for x in addresses))

    def test_concurrency_cap_and_early_success_drain(self):
        active, peak = 0, 0
        async def probe(address, timeout):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(.005)
                return address == '10.0.0.2'
            finally:
                active -= 1
        async def auth(address, *args):
            return MATCH if address == '10.0.0.2' else None
        asyncio.run(discovery.discover(replace(self.settings, concurrency=4), EXPECTED, self.emit, probe, auth))
        self.assertLessEqual(peak, 4)
        self.assertEqual(active, 0)
        self.assertLess(sum(x['kind'] == 'tcp' for x in self.events), 253)

    def test_two_pass_bound_and_no_unexplained_retry(self):
        with self.assertRaises(TimeoutError):
            asyncio.run(discovery.discover(self.settings, EXPECTED, self.emit,
                                          AsyncMock(return_value=False), AsyncMock(return_value=None)))
        self.assertEqual([x['pass_number'] for x in self.events if x['kind'] == 'preferred'], [1, 2])
        self.assertEqual(self.events[-1]['kind'], 'drained')

    def test_global_deadline_cancels_pending_probes(self):
        active = 0
        async def probe(*args):
            nonlocal active
            active += 1
            try:
                await asyncio.sleep(10)
            finally:
                active -= 1
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            asyncio.run(discovery.discover(replace(self.settings, total_seconds=.03), EXPECTED,
                                          self.emit, probe, AsyncMock(return_value=None)))
        self.assertEqual(active, 0)
        self.assertLess(time.monotonic() - start, .5)
        self.assertEqual(self.events[-1]['kind'], 'drained')

    def test_authentication_concurrency_is_at_most_two(self):
        active, peak = 0, 0
        async def auth(*args):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(.001)
                return None
            finally:
                active -= 1
        with self.assertRaises(TimeoutError):
            asyncio.run(discovery.discover(replace(self.settings, total_seconds=.04), EXPECTED,
                                          self.emit, AsyncMock(return_value=True), auth))
        self.assertLessEqual(peak, 2)
        self.assertEqual(active, 0)


if __name__ == '__main__':
    unittest.main()
