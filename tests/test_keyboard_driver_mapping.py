"""The driver candidate and Test331 use one swap each, with exact identity gates."""
import gzip
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location('keyboard_driver_mapping',
        ROOT / 'userspace/gnome/keyboard/select-driver.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_native_removes_only_interim_option(self):
        raw = repr(['compose:ralt', self.m.OPTION, 'caps:ctrl_modifier'])
        self.assertEqual(self.m.select(raw, 'native'), ['compose:ralt', 'caps:ctrl_modifier'])

    def test_interim_restoration_is_idempotent(self):
        result = self.m.select("['compose:ralt']", 'interim')
        self.assertEqual(result, ['compose:ralt', self.m.OPTION])
        self.assertEqual(self.m.select(repr(result), 'interim'), result)

    def test_empty_array_and_malformed_values(self):
        self.assertEqual(self.m.select('@as []', 'native'), [])
        for raw in ('42', "['good', 5]", '{"option": "value"}', 'not-python'):
            with self.assertRaises((ValueError, SyntaxError)):
                self.m.select(raw, 'native')
        with self.assertRaises(ValueError):
            self.m.select('[]', 'unknown')

    def fake(self):
        values = {'xkb-options': repr(['compose:ralt', self.m.OPTION]),
                  'sources': "[('xkb', 'us'), ('xkb', 'de')]"}
        calls = []
        def settings(action, schema, key, *args):
            self.assertEqual(schema, self.m.SCHEMA)
            calls.append((action, key, args))
            if action == 'set':
                values[key] = args[0]
                return ''
            return values[key]
        return values, calls, settings

    def test_apply_preserves_sources_and_records_before_write(self):
        values, calls, settings = self.fake()
        def record(before, sources):
            self.assertEqual(before, values['xkb-options'])
            self.assertEqual(sources, values['sources'])
            self.assertFalse(any(c[0] == 'set' for c in calls))
        result = self.m.apply('native', settings, lambda: None, record)
        self.assertEqual(result['after'], ['compose:ralt'])
        self.assertFalse(any(c[1] == 'sources' and c[0] == 'set' for c in calls))

    def test_identity_failure_does_not_write(self):
        _, calls, settings = self.fake()
        def check():
            raise ValueError('wrong kernel')
        with self.assertRaises(ValueError):
            self.m.apply('native', settings, check)
        self.assertEqual(calls, [])

    def test_bad_readback_restores_options(self):
        values, calls, settings = self.fake()
        before = values['xkb-options']
        mutated = False
        def bad(action, schema, key, *args):
            nonlocal mutated
            result = settings(action, schema, key, *args)
            if action == 'set':
                mutated = True
            if action == 'get' and key == 'xkb-options' and mutated:
                return "['different']"
            return result
        with self.assertRaisesRegex(ValueError, 'readback'):
            self.m.apply('native', bad, lambda: None)
        self.assertEqual(values['xkb-options'], before)
        self.assertEqual(sum(c[0] == 'set' for c in calls), 2)

    def test_changed_boot_after_write_never_blindly_restores(self):
        values, calls, settings = self.fake()
        checks = 0
        def check():
            nonlocal checks
            checks += 1
            if checks >= 3:
                raise ValueError('boot changed')
        with self.assertRaisesRegex(ValueError, 'boot changed'):
            self.m.apply('native', settings, check)
        self.assertEqual(sum(c[0] == 'set' for c in calls), 1)

    def test_exact_identity_rejects_old_notes_and_new_boot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = {'proc/sys/kernel/random/boot_id': b'boot', 'etc/machine-id': b'3c2a1b8f2d624db4b5ffdc836050fcf6',
                    'sys/firmware/devicetree/base/compatible': b'samsung,gts9wifi\0',
                    'proc/config.gz': gzip.compress(b'config'), 'sys/kernel/notes': b'native-notes'}
            for name, value in data.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
            self.m.IDENTITIES['native'] = tuple(hashlib.sha256(x).hexdigest() for x in (b'config', b'native-notes'))
            args = dict(root=root, machine='aarch64', release='7.2.0-rc3-gts9wifi-dirty')
            self.m.identity('native', 'boot', **args)
            with self.assertRaisesRegex(ValueError, 'boot changed'):
                self.m.identity('native', 'other-boot', **args)
            (root / 'sys/kernel/notes').write_bytes(b'old-notes')
            with self.assertRaisesRegex(ValueError, 'config/notes'):
                self.m.identity('native', 'boot', **args)

    def test_private_and_existing_bus_commands_drop_root_bus(self):
        for active in (False, True):
            argv = self.m.settings_command(1000, '/home/ms', active)
            self.assertEqual(argv[:11], ['runuser', '-u', 'ms', '--', 'env', '-u', 'DBUS_SESSION_BUS_ADDRESS',
                                        '-u', 'XDG_RUNTIME_DIR', 'HOME=/home/ms', 'XDG_CONFIG_HOME=/home/ms/.config'])
            self.assertEqual(argv[-1], 'gsettings')
            self.assertEqual('dbus-run-session' in argv, not active)


if __name__ == '__main__':
    unittest.main()
