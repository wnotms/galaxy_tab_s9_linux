"""New evidence gate boundaries; historical Test311 checks remain untouched."""
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-322-pc-source-budget'
spec=importlib.util.spec_from_file_location('pc322_gate_tests',R/'gate.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
BOOT='0123456789abcdef0123456789abcdef'

def source(ma=1800000,uv=5000000,kind='C [PD] PD_PPS',online=1):
    return f'POWER_SUPPLY_ONLINE={online}\nPOWER_SUPPLY_VOLTAGE_NOW={uv}\nPOWER_SUPPLY_VOLTAGE_MAX={uv}\nPOWER_SUPPLY_CURRENT_MAX={ma}\nPOWER_SUPPLY_USB_TYPE={kind}\n'

def packet(budget=1800):
    regs={'0x0d':'0x01','0x0e':'0x00','0x13':'0x08','0x14':'0x05','0x15':hex((budget-100)//25),'0x18':hex(7+(max(500,budget)*1000-109375)//15625),'0x1a':'0x2d'}
    return dict(boot_id_before=BOOT,boot_id_after=BOOT,register_data_writes=False,only_atomic_pointer_reads=True,bound_driver='sm5714-battery',i2c_node='1-0049',stable_registers=regs)

class GateTests(unittest.TestCase):
    def test_authorized_budgets(self):
        for ma,want in [(500000,500),(1500000,1500),(1800000,1800),(3000000,1800)]:
            with self.subTest(ma=ma): self.assertEqual(g.source_budget(source(ma)),want)
    def test_invalid_source(self):
        for raw in [source(0),source(3001000),source(1800500),source(uv=9000000),source(kind='C PD [PD_PPS]'),source(online=0),'']:
            with self.subTest(raw=raw),self.assertRaises((ValueError,KeyError)): g.source_budget(raw)
    def test_exact_higher_program(self):
        self.assertEqual(g.program_controls(json.dumps(packet()),BOOT,1800)['input_limit_ma'],1800)
    def test_default500_preserved(self):
        self.assertEqual(g.program_controls(json.dumps(packet(500)),BOOT,500)['fast_code'],32)
    def test_aicl_lower_not_raise(self):
        p=packet();p['stable_registers']['0x15']='0x10'
        self.assertEqual(g.program_controls(json.dumps(p),BOOT,1800)['input_limit_ma'],500)
    def test_over_grant(self):
        with self.assertRaises(ValueError): g.program_controls(json.dumps(packet()),BOOT,1500)
    def test_bad_original_byte(self):
        for value in ['-1','0x144']:
            p=packet();p['stable_registers']['0x15']=value
            with self.subTest(value=value),self.assertRaises(ValueError):g.program_controls(json.dumps(p),BOOT,1800)
    def test_fast_mismatch(self):
        p=packet();p['stable_registers']['0x18']='0x20'
        with self.assertRaises(ValueError): g.program_controls(json.dumps(p),BOOT,1800)
    def test_protected_control_failures(self):
        for k,v in [('0x0d','0x05'),('0x0e','0x80'),('0x13','0'),('0x14','0'),('0x1a','0x2c')]:
            p=packet();p['stable_registers'][k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):g.program_controls(json.dumps(p),BOOT,1800)
    def test_identity_access_faults(self):
        for k,v in [('boot_id_after','f'*32),('register_data_writes',True),('only_atomic_pointer_reads',False),('bound_driver','other')]:
            p=packet();p[k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):g.program_controls(json.dumps(p),BOOT,1800)
    def test_missing_register(self):
        p=packet();del p['stable_registers']['0x0e']
        with self.assertRaises((ValueError,KeyError)):g.program_controls(json.dumps(p),BOOT,1800)
    def test_reserve(self):
        def b(s):return f'POWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_CAPACITY={s}\nPOWER_SUPPLY_VOLTAGE_NOW=3877000\nPOWER_SUPPLY_TEMP=304\n'
        self.assertEqual(g.battery_entry(b(20))['soc'],20)
        with self.assertRaises(ValueError):g.battery_entry(b(19))
    def test_runner_import_offline(self):
        spec=importlib.util.spec_from_file_location('pc322_runner_tests',R/'host_flow.py')
        h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
        self.assertEqual(h.R,R)
    def test_one_normalization_then_stop(self):
        text=(R/'normal_reentry.py').read_text()
        self.assertIn("raise ValueError('one request only; no replay')",text)
        self.assertEqual(text.count("'systemctl reboot'"),1)

if __name__=='__main__':unittest.main()
