"""Actual provider-anchored reader and unchanged acceptance lifecycle, host only."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_sm5714_ordinary_device_runner as inherited

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-310-ordinary-provider-acceptance'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

m=load('provider310_runner',R/'host_flow.py')
c=load('provider310_controls',R/'read-controls.py')

class ProviderTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        for name in ('proc/sys/kernel/random','sys/class/power_supply/sm5714-battery',
                     'sys/bus/i2c/devices','devices/2-0049/of_node','devices/7-0049',
                     'drivers/sm5714-battery'):
            (self.root/name).mkdir(parents=True,exist_ok=True)
        self.node=self.root/'devices/2-0049'
        (self.root/'proc/sys/kernel/random/boot_id').write_text(inherited.BOOT)
        (self.root/'sys/class/power_supply/sm5714-battery/device').symlink_to(self.node)
        (self.root/'sys/bus/i2c/devices/2-0049').symlink_to(self.node)
        (self.root/'sys/bus/i2c/devices/7-0049').symlink_to(self.root/'devices/7-0049')
        (self.node/'driver').symlink_to(self.root/'drivers/sm5714-battery')
        (self.node/'of_node/compatible').write_bytes(b'siliconmitus,sm5714\0')
        ctx=mock.patch.object(c,'Path',side_effect=lambda name:self.root/str(name).lstrip('/'))
        ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(c.os,'open',return_value=17);self.open=ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(c.os,'close');self.close=ctx.start();self.addCleanup(ctx.stop)
        ctx=mock.patch.object(c.fcntl,'ioctl',side_effect=self.transfer);self.io=ctx.start();self.addCleanup(ctx.stop)
        self.registers=[]

    def transfer(self,fd,request,packet):
        self.assertEqual((fd,request,packet.nmsgs),(17,0x0707,2))
        pointer,response=packet.msgs[0],packet.msgs[1]
        self.assertEqual((pointer.addr,pointer.flags,pointer.length),(0x49,0,1))
        self.assertEqual((response.addr,response.flags,response.length),(0x49,1,1))
        self.registers.append(pointer.buf[0]);response.buf[0]=0

    def refused_without_open(self):
        with self.assertRaises((ValueError,FileNotFoundError)):c.capture()
        self.open.assert_not_called();self.io.assert_not_called()

    def test_actual_two_bus_layout_selects_supply_provider_and_seven_pointer_reads(self):
        result=c.capture()
        self.assertEqual(result['i2c_node'],'2-0049')
        self.assertEqual(self.registers,list(c.REGISTERS))
        self.assertFalse(result['register_data_writes'])
        self.assertTrue(result['only_atomic_pointer_reads'])
        self.open.assert_called_once_with('/dev/i2c-2',c.os.O_RDWR)
        self.close.assert_called_once_with(17)

    def test_alias_to_unrelated_same_address_is_rejected_before_io(self):
        alias=self.root/'sys/bus/i2c/devices/2-0049';alias.unlink()
        alias.symlink_to(self.root/'devices/7-0049');self.refused_without_open()

    def test_wrong_driver_or_compatible_is_rejected_before_io(self):
        (self.node/'driver').unlink();(self.node/'driver').symlink_to(self.root/'devices/7-0049')
        self.refused_without_open()
        (self.node/'driver').unlink();(self.node/'driver').symlink_to(self.root/'drivers/sm5714-battery')
        (self.node/'of_node/compatible').write_bytes(b'siliconmitus,other\0')
        self.refused_without_open()

    def test_missing_provider_or_alias_is_rejected_before_io(self):
        alias=self.root/'sys/bus/i2c/devices/2-0049';alias.unlink();self.refused_without_open()
        alias.symlink_to(self.node);(self.root/'sys/class/power_supply/sm5714-battery/device').unlink()
        self.refused_without_open()

    def test_wrong_address_provider_is_rejected_before_io(self):
        supply=self.root/'sys/class/power_supply/sm5714-battery/device';supply.unlink()
        (self.root/'devices/2-0071').mkdir();supply.symlink_to(self.root/'devices/2-0071')
        self.refused_without_open()

    def test_i2c_error_closes_fd_without_retry(self):
        self.io.side_effect=OSError('I2C failure')
        with self.assertRaises(OSError):c.capture()
        self.io.assert_called_once();self.close.assert_called_once_with(17)

class NewRunner:
    def setUp(self):
        ctx=mock.patch.object(inherited,'m',m);ctx.start();self.addCleanup(ctx.stop)
        super().setUp()

class GateTests(NewRunner,inherited.GateTests):pass
class LifecycleTests(NewRunner,inherited.LifecycleTests):pass
class AdmissionTests(NewRunner,inherited.AdmissionTests):pass
class PreflightTests(NewRunner,inherited.PreflightTests):
    def setUp(self):
        super().setUp()
        ctx=mock.patch.object(m,'controls',return_value={'input_limit_ma':500})
        self.controls=ctx.start();self.addCleanup(ctx.stop)

    def test_provider_control_collection_also_runs_before_first_flash(self):
        self.test_debian_preflight_uses_label_hashes_without_touching_recovery_or_bcb()
        self.controls.assert_called_once()

if __name__=='__main__':unittest.main()
