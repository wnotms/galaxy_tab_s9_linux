import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('registry_core_audit', ROOT / 'userspace/sensors/registry_core_audit.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class CoreAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.archive = Path(temp.name) / 'assets.tar.gz'
        self.inputs = {}
        for group, (filename, keys) in m.GROUPS.items():
            name = 'config/' + filename
            document = self.inputs.setdefault(name, {'config': {'soc_id': ['519']}})
            leaf = document
            for key in keys:
                leaf = leaf.setdefault(key, {})
            leaf.update(owner='lsm6dso', value=dict(type='int', ver='0', data='3'))
            self.inputs['registry/' + group] = {group: copy.deepcopy(leaf)}

    def run_audit(self, duplicate=False, special=None):
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, value in self.inputs.items():
                data = json.dumps(value).encode()
                member = tarfile.TarInfo(m.PREFIX + name); member.size = len(data)
                if name == special:
                    member.type = tarfile.SYMTYPE; member.linkname = '/etc/shadow'
                    archive.addfile(member); continue
                archive.addfile(member, io.BytesIO(data))
                if duplicate: archive.addfile(member, io.BytesIO(data))
        sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        return m.audit(self.archive, sha)

    def test_exact_core_groups_match_without_hardware_claim(self):
        result = self.run_audit()
        self.assertTrue(result['complete'])
        for claim in ('selector_match_proved', 'electrical_bus_type_proved', 'SSC_publication_proved', 'device_operations'):
            self.assertFalse(result[claim])

    def test_changed_bus_value_reported(self):
        self.inputs['registry/lsm6dso_0_platform.config']['lsm6dso_0_platform.config']['value']['data'] = '9'
        result = self.run_audit()
        self.assertFalse(result['complete'])
        self.assertEqual(result['groups']['lsm6dso_0_platform.config']['differing_fields'], ['value'])

    def test_extra_or_missing_registry_fields_do_not_pass(self):
        leaf = self.inputs['registry/lsm6dso_0.accel.config']['lsm6dso_0.accel.config']
        leaf.pop('value'); leaf['extra'] = 'unexpected'
        self.assertFalse(self.run_audit()['complete'])

    def test_hash_mismatch_rejected(self):
        self.run_audit()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): m.audit(self.archive, '0' * 64)

    def test_missing_group_rejected(self):
        self.inputs.pop('registry/lsm6dso_0.gyro.config')
        with self.assertRaisesRegex(ValueError, 'missing core'): self.run_audit()

    def test_duplicate_archive_members_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.run_audit(duplicate=True)

    def test_symlink_not_followed(self):
        with self.assertRaisesRegex(ValueError, 'invalid core'): self.run_audit(special='config/lsm6dso_0.json')

    def test_wrong_group_schema_rejected(self):
        self.inputs['registry/lsm6dso_0.gyro.config']['wrong'] = {}
        with self.assertRaisesRegex(ValueError, 'schema'): self.run_audit()


if __name__ == '__main__': unittest.main()
