"""Offline Test319 identity and no-replay tests; fixtures are explicitly mocked."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-319-normal-accepted311-reentry'
spec=importlib.util.spec_from_file_location('normal319',R/'host_flow.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);h.configure()

def fixture(incoming=False):
    raw=(R.parent/'test-317-fixed9-off-context-device/final-acceptance/current-state.txt').read_text()
    sec=h.h.g.baseline.sections(raw)
    # Derive parser fixture shape only; these are not new device observations.
    sec['cmdline']=h.PLAN['incoming_cmdline' if incoming else 'runtime_cmdline']+'\n'
    sec['pack-thermal']='sm5714-battery\nenabled\n29400\n'
    sec['source']='ret=0\nonline=1\nbudget_mv=5000\n'
    sec['boot-end']=sec['boot']
    return '\n'.join('@@'+k+'\n'+v.rstrip('\n') for k,v in sec.items())+'\n'

class Reentry(unittest.TestCase):
    def test_normal_and_exact_incoming(self):
        self.assertEqual(h.identity(fixture())[1],h.identity(fixture(True),True)[1])

    def test_no_lpcharge_exemption_after_reboot(self):
        with self.assertRaises(ValueError):h.identity(fixture(True))

    def test_no_wrong_incoming_variant(self):
        with self.assertRaises(ValueError):h.identity(fixture(),True)

    def test_config_and_roles_unchanged(self):
        for source,target in [(h.PLAN['baseline_config_sha256'],'0'*64),('[device]','[host]'),('budget_mv=5000','budget_mv=9000'),('sm5714-battery\nenabled','sm5714-battery\ndisabled')]:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):h.identity(fixture().replace(source,target))

    def test_mixed_boot_refused(self):
        raw=fixture();raw=raw[:raw.index('@@boot-end')]+'@@boot-end\n'+'f'*32+'\n'
        with self.assertRaises(ValueError):h.identity(raw)

    def test_no_second_reboot(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(h,'R',Path(tmp)),patch.object(h,'verify_registration'),patch.object(h.p,'Recorder') as rec:
                (Path(tmp)/'reboot-state.json').write_text('{}')
                with self.assertRaisesRegex(ValueError,'one reboot'):h.run()
                rec.assert_not_called()

    def test_stale_preflight_does_not_reboot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'preflight').mkdir()
            h.write(root/'preflight/summary.json',dict(verdict='READY_ONE_UNCHANGED_NORMAL_REBOOT',collected_at_epoch=0))
            with patch.object(h,'R',root),patch.object(h,'verify_registration'),patch.object(h.p,'Recorder') as rec:
                with self.assertRaisesRegex(ValueError,'fresh preflight'):h.run()
                rec.assert_not_called()

if __name__=='__main__':unittest.main()
