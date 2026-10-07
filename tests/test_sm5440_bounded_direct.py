"""Test338 pure guardian/native evidence; all hardware and time are mocked."""
import importlib.util
import hashlib
import io
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT/'reference/boot-tests/test-338-bounded-direct-1p8a/guard.py'
spec = importlib.util.spec_from_file_location('bounded338_guard',PATH)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
BOOT = 'a'*32


def row(message, us):
    return dict(MESSAGE=message,_BOOT_ID=BOOT,__MONOTONIC_TIMESTAMP=str(us),
                _SOURCE_MONOTONIC_TIMESTAMP=str(us))


def journal():
    return [row('Linux boot',0),
            row('direct charge started: PPS 8940 mV/1800 mA, ibus limit 1800 mA',1000000),
            row('one-shot pump started: target=8940mV/1800mA deadline=30900ms max_ms=30000 no_restart=1',1000100),
            row('one-shot refresh parked: pump_OFF=1',5000000),
            row('one-shot refresh resumed: target=8940mV/1800mA deadline=30900ms',5150000),
            row('fixed return verified: source=9 lease=1 vbus=9267000uV samples=3 range=9267..9267mV settled=100ms raw_ibus=0 pump_off=1',31010000),
            row('one-shot pump complete: lease=0 fixed_return=1 positive_samples=240 no_restart=1',31011000)]


def sample(on=True):
    return dict(battery=dict(POWER_SUPPLY_HEALTH='Good',POWER_SUPPLY_PRESENT='1',
                POWER_SUPPLY_CAPACITY='57',POWER_SUPPLY_TEMP='280',
                POWER_SUPPLY_VOLTAGE_NOW='4000000',POWER_SUPPLY_CURRENT_NOW='2000000'),
                adc=dict(mode=4 if on else 0,adc_enabled=True,ibus_ua=1500000,
                vbat_uv=4000000,die_decic=400,vbus_mv=8940),
                tcpm=dict(POWER_SUPPLY_ONLINE='2' if on else '1',
                POWER_SUPPLY_CURRENT_NOW='1800000',POWER_SUPPLY_VOLTAGE_NOW='8940000' if on else '9000000'))


class BoundedGuardianTests(unittest.TestCase):
    def test_unique_module_slots_install_restore_on_temporary_root(self):
        import test_sm5440_module_staging as old
        fixture = old.ModuleStagingTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        data = {f'new-{n:03}.ko':('new '+str(n)).encode() for n in range(181)}
        archive = fixture.work/'new.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name,value in data.items():
                item = tarfile.TarInfo(old.RELEASE+'/'+name);item.size=len(value)
                tar.addfile(item,io.BytesIO(value))
        expected = {n:hashlib.sha256(v).hexdigest() for n,v in data.items()}
        manifest = fixture.manifest('new.sha256',expected)
        with patch.object(old,'HELPER',PATH.parent/'module-swap.sh'):
            p = fixture.call('install',manifest,archive)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(fixture.current_hashes(),expected)
            self.assertTrue((fixture.base/'.gts9-test338-original').is_dir())
            self.assertFalse((fixture.base/'.gts9-test337-original').exists())
            p = fixture.call('restore',fixture.old_manifest)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(fixture.current_hashes(),fixture.old)

    def test_unique_attributed_native_round(self):
        d=g.native_proof(journal(),BOOT,required=True)
        self.assertEqual((d['target_ma'],d['refreshes'],d['fixed_return']), (1800,1,True))

    def test_pending_prefix_never_is_a_pass(self):
        for count in range(1,7):
            self.assertIsNone(g.native_proof(journal()[:count],BOOT))
            with self.assertRaises(ValueError):
                g.native_proof(journal()[:count],BOOT,required=True)

    def test_invalid_empty_boot_missing_source_time_or_duplicate_start(self):
        for rows in [[],[row('late journal only',6000000)],journal()+[journal()[2]],journal()+[row('one-shot pump stopped: primary=-5',32000000)]]:
            with self.assertRaises(ValueError):g.native_proof(rows,BOOT,required=True)
        rows=journal();rows[0]['_BOOT_ID']='b'*32
        with self.assertRaises(ValueError):g.native_proof(rows,BOOT)
        rows=journal();rows[2].pop('_SOURCE_MONOTONIC_TIMESTAMP')
        with self.assertRaises(KeyError):g.native_proof(rows,BOOT)

    def test_unpaired_late_refresh_or_second_entry(self):
        for changed in [journal()[:3]+journal()[4:],
                        journal()[:4]+[row('one-shot refresh resumed: target=8940mV/1800mA deadline=30900ms',8000000)]+journal()[5:],
                        journal()+[row('direct charge started: PPS 8940 mV/1800 mA',32000000)]]:
            with self.assertRaises(ValueError):g.native_proof(changed,BOOT)

    def test_no_positive_charge_or_late_completion(self):
        for text in ['one-shot pump complete: lease=0 fixed_return=1 positive_samples=0 no_restart=1',
                     'one-shot pump complete: lease=0 fixed_return=1 positive_samples=10 no_restart=0']:
            rows=journal();rows[-1]=row(text,31011000)
            with self.assertRaises(ValueError):g.native_proof(rows,BOOT)
        rows=journal();rows[-1]=row(rows[-1]['MESSAGE'],35000000)
        with self.assertRaises(ValueError):g.native_proof(rows,BOOT)

    def test_actual_current_precision_and_pack_adc_gates(self):
        self.assertTrue(g.check_sample(sample()))
        for section,key,value in [('adc','ibus_ua',1800625),('adc','mode',8),
                ('adc','die_decic',850),('adc','vbat_uv',4200500),
                ('battery','POWER_SUPPLY_TEMP','420'),
                ('battery','POWER_SUPPLY_CURRENT_NOW','3600001'),
                ('tcpm','POWER_SUPPLY_ONLINE','1')]:
            s=sample();s[section][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):g.check_sample(s)

    def test_first_faults_include_i2c_cpu_and_native_failure(self):
        for message in ['one-shot pump stopped: primary=-5 cleanup=0',
                'soft lockup','rcu: detected stall','CSD non-responsive',
                'Kernel panic','I2C timeout','SError','WARNING: CPU:']:
            with self.subTest(message=message),self.assertRaises(ValueError):
                g.native_proof(journal()+[row(message,32000000)],BOOT)

    def test_guardian_cleanup_on_success_fault_transport_and_missing_pump_sample(self):
        class Clock:
            now=0
            def __call__(self):return self.now
            def sleep(self,n):self.now+=n
        for mode in ('pass','fault','journal-error','missing-live'):
            clock=Clock();events=[]
            class Mock:
                stops=0
                def sample(self):
                    s=sample(on=mode!='missing-live' and clock.now<31.02)
                    if mode=='fault':s['adc']['ibus_ua']=1800625
                    return s
                def stop(self):self.stops+=1;return dict(pump_mode=0)
            hw=Mock()
            def get_rows():
                if mode=='journal-error':raise RuntimeError('SSH/journal lost')
                return [x for x in journal() if int(x['_SOURCE_MONOTONIC_TIMESTAMP'])<=clock.now*1000000]
            if mode=='pass':
                result=g.observe(hw,get_rows,lambda *x:events.append(x),BOOT,clock,clock.sleep)
                self.assertEqual(result['verdict'],'BOUNDED_NATIVE_RETURN_PASS')
            else:
                with self.assertRaises(Exception):
                    g.observe(hw,get_rows,lambda *x:events.append(x),BOOT,clock,clock.sleep)
            self.assertEqual(hw.stops,1)
