"""Exercise offline Debian metadata/payload gates without Docker or a device."""
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tarfile
import unittest

BASE = Path(__file__).resolve().parents[1] / 'userspace/sensors'
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location('ssc_package', BASE / 'package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def archive(entries, owner=0, symlink=False):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as target:
        for name, data in entries:
            member = tarfile.TarInfo('./' + name)
            member.uid = member.gid = owner
            member.size = len(data)
            if symlink:
                member.type = tarfile.SYMTYPE
                member.linkname = '/outside'
                member.size = 0
            target.addfile(member, io.BytesIO(data))
    return stream.getvalue()


class PackageInspectionTests(unittest.TestCase):
    def setUp(self):
        self.name = 'libssc2'
        self.spec = package.PACKAGES[self.name]
        self.payload = [('usr/bin/ssccli', b'qualified-binary')]
        self.row = dict(version=self.spec['version'], depends='libc6 (>= 2.34)',
                        control_files=['control', 'triggers'],
                        payload_files={k:hashlib.sha256(v).hexdigest() for k,v in self.payload})
        self.metadata = [('control',package.control(self.name,self.spec,self.row['depends']).encode()),
                         ('triggers',b'activate-noawait ldconfig\n')]

    def inspect(self, metadata=None, payload=None):
        return package.inspect_package(archive(self.metadata if metadata is None else metadata),
            archive(self.payload if payload is None else payload), self.name, self.row)

    def test_matching_package(self):
        self.assertEqual(self.inspect(), self.row['payload_files'])

    def test_changed_binary(self):
        with self.assertRaisesRegex(ValueError, 'payload differs'):
            self.inspect(payload=[('usr/bin/ssccli',b'other')])

    def test_extra_firmware(self):
        with self.assertRaisesRegex(ValueError, 'payload differs'):
            self.inspect(payload=self.payload+[('usr/lib/firmware/adsp.mdt',b'firmware')])

    def test_missing_binary(self):
        with self.assertRaisesRegex(ValueError, 'payload differs'):
            self.inspect(payload=[])

    def test_postinst_not_allowed(self):
        with self.assertRaisesRegex(ValueError, 'control scripts'):
            self.inspect(metadata=self.metadata+[('postinst',b'systemctl start adsp')])

    def test_wrong_architecture(self):
        data=self.metadata[0][1].replace(b'Architecture: arm64',b'Architecture: amd64')
        with self.assertRaisesRegex(ValueError, 'metadata mismatch'):
            self.inspect(metadata=[('control',data),self.metadata[1]])

    def test_wrong_dependency(self):
        data=self.metadata[0][1].replace(b'libc6 (>= 2.34)',b'libc6')
        with self.assertRaisesRegex(ValueError, 'metadata mismatch'):
            self.inspect(metadata=[('control',data),self.metadata[1]])

    def test_trigger_must_only_request_ldconfig(self):
        with self.assertRaisesRegex(ValueError, 'trigger'):
            self.inspect(metadata=[self.metadata[0],('triggers',b'activate adsp-start\n')])

    def test_non_root_ownership(self):
        with self.assertRaisesRegex(ValueError, 'not owned by root'):
            package.archive_files(archive(self.payload,owner=1000))

    def test_links_rejected(self):
        with self.assertRaisesRegex(ValueError, 'link/special'):
            package.archive_files(archive(self.payload,symlink=True))

    def test_unsafe_member_path(self):
        for name in ['../escape', '/absolute']:
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                package.archive_files(archive([(name,b'data')]))

    def test_manifest_cannot_authorize_postinst(self):
        self.row['control_files'].append('postinst')
        with self.assertRaisesRegex(ValueError, 'control scripts'):
            self.inspect(metadata=self.metadata+[('postinst',b'start')])

    def test_duplicate_members(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            package.archive_files(archive(self.payload*2))

    def test_runtime_plan_excludes_mocks_development_and_firmware(self):
        files={name:'hash' for spec in package.PACKAGES.values() for name in spec['files']}
        files.update({'usr/lib/firmware/adsp.mdt':'hash','usr/include/libssc.h':'hash',
                      'usr/lib/python3/dist-packages/ssc_server/mock.py':'hash'})
        plan=package.payload_plan({'files':files})
        self.assertNotIn('usr/lib/firmware/adsp.mdt',plan)
        self.assertNotIn('usr/include/libssc.h',plan)
        self.assertNotIn('usr/lib/python3/dist-packages/ssc_server/mock.py',plan)

    def test_missing_runtime_plan_file(self):
        with self.assertRaisesRegex(ValueError, 'missing qualified runtime'):
            package.payload_plan({'files':{}})

    def test_dependency_newline_rejected(self):
        with self.assertRaisesRegex(ValueError, 'dependency field'):
            package.control(self.name,self.spec,'libc6\nPostinst: start')


if __name__ == '__main__':
    unittest.main()
