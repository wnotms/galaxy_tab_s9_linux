import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/desktop-bringup/usb-lifecycle-permanent'
spec=importlib.util.spec_from_file_location('permanent_usb_device',R/'device.py')
D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)

class PersistentTransactionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.rows={}
        for name,mode in D.PATHS.items():
            data=('qualified '+name).encode();self.rows[name]=dict(bytes=len(data),mode=mode,sha256=hashlib.sha256(data).hexdigest(),base64=base64.b64encode(data).decode())

    def test_install_and_full_original_absence_restore(self):
        D.install_permanent(self.root,self.rows,'boot')
        self.assertIsNotNone(D.enabled_link(self.root));D.verify_files(self.root,self.rows)
        D.rollback_permanent(self.root,self.rows,'boot')
        self.assertIsNone(D.enabled_link(self.root))
        self.assertTrue(all(not (self.root/n).exists() for n in D.PATHS))
        with self.assertRaises(ValueError):D.install_permanent(self.root,self.rows,'boot')

    def test_unknown_link_refused_before_file_install(self):
        link=self.root/D.LINK;link.parent.mkdir(parents=True);link.symlink_to('../other.service')
        with self.assertRaises(ValueError):D.install_permanent(self.root,self.rows,'boot')
        self.assertFalse((self.root/D.STATE).exists())

    def test_matching_but_preexisting_link_not_adopted(self):
        link=self.root/D.LINK;link.parent.mkdir(parents=True);link.symlink_to('../'+D.UNIT)
        with self.assertRaises(ValueError):D.install_permanent(self.root,self.rows,'boot')
        self.assertFalse((self.root/D.STATE).exists())

    def test_preexisting_payload_refused(self):
        name=next(iter(self.rows));p=self.root/name;p.parent.mkdir(parents=True);p.write_text('owner')
        with self.assertRaises(ValueError):D.install_permanent(self.root,self.rows,'boot')
        self.assertEqual(p.read_text(),'owner');self.assertIsNone(D.enabled_link(self.root))

    def test_file_drift_preserves_link_and_all_payloads(self):
        D.install_permanent(self.root,self.rows,'boot');(self.root/next(iter(self.rows))).write_text('external')
        with self.assertRaises(ValueError):D.rollback_permanent(self.root,self.rows,'boot')
        self.assertIsNotNone(D.enabled_link(self.root))
        self.assertTrue(all((self.root/n).exists() for n in self.rows))

    def test_link_drift_preserves_all_payloads(self):
        D.install_permanent(self.root,self.rows,'boot');link=self.root/D.LINK;link.unlink();link.symlink_to('../other.service')
        with self.assertRaises(ValueError):D.rollback_permanent(self.root,self.rows,'boot')
        self.assertTrue(all((self.root/n).exists() for n in self.rows))

    def test_wrong_boot_preserves_link_and_payloads(self):
        D.install_permanent(self.root,self.rows,'boot')
        with self.assertRaises(ValueError):D.rollback_permanent(self.root,self.rows,'other')
        self.assertIsNotNone(D.enabled_link(self.root))

    def test_corrupt_pending_preserves_link_and_payloads(self):
        D.install_permanent(self.root,self.rows,'boot');p=self.root/(next(iter(self.rows))+'.usb-lifecycle-pending');p.write_bytes(b'foreign');p.chmod(0o755)
        with self.assertRaises(ValueError):D.rollback_permanent(self.root,self.rows,'boot')
        self.assertIsNotNone(D.enabled_link(self.root))
        self.assertTrue(all((self.root/n).exists() for n in self.rows))

    def test_interrupted_link_creation_recovers_three_files(self):
        real=Path.symlink_to
        def fail(p,*a,**kw):
            if str(p).endswith(D.LINK):raise OSError('injected link failure')
            return real(p,*a,**kw)
        with patch.object(Path,'symlink_to',fail):
            with self.assertRaises(OSError):D.install_permanent(self.root,self.rows,'boot')
        D.rollback_permanent(self.root,self.rows,'boot')
        self.assertTrue(all(not (self.root/n).exists() for n in self.rows))

    def test_parent_symlink_is_rejected(self):
        p=self.root/'etc/systemd/system';p.mkdir(parents=True);(p/'multi-user.target.wants').symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):D.install_permanent(self.root,self.rows,'boot')
        self.assertFalse((self.root/D.STATE).exists())

if __name__=='__main__':unittest.main()
