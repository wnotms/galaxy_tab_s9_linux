"""Exercise Test371's actual file transaction and source-attributed fault gates."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-371-usb-lifecycle-gmu'
def load(name):
    spec=importlib.util.spec_from_file_location('test371_'+name,R/(name+'.py'))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
D=load('device')
H=load('host_flow')


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rows={}
        for name,mode in D.PATHS.items():
            data=('actual payload '+name).encode()
            self.rows[name]=dict(bytes=len(data),mode=mode,sha256=hashlib.sha256(data).hexdigest(),base64=base64.b64encode(data).decode())

    def test_exact_three_file_install_rollback_and_no_retry(self):
        D.install(self.root,self.rows,'boot-a')
        D.verify_files(self.root,self.rows)
        D.restore_files(self.root,self.rows,'boot-a')
        self.assertTrue(all(not (self.root/n).exists() for n in D.PATHS))
        with self.assertRaises(ValueError):D.install(self.root,self.rows,'boot-a')

    def test_existing_file_refused_before_any_mutation(self):
        name=list(D.PATHS)[-1]
        p=self.root/name
        p.parent.mkdir(parents=True)
        p.write_text('owner file')
        with self.assertRaises(ValueError):D.install(self.root,self.rows,'boot-a')
        self.assertFalse((self.root/D.STATE).exists())
        self.assertEqual(p.read_text(),'owner file')

    def test_parent_symlink_refused(self):
        (self.root/'etc').symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):D.install(self.root,self.rows,'boot-a')
        self.assertFalse((self.root/D.STATE).exists())

    def test_wrong_payload_digest_refused_before_mutation(self):
        self.rows[next(iter(self.rows))]['sha256']='0'*64
        with self.assertRaises(ValueError):D.install(self.root,self.rows,'boot-a')
        self.assertFalse((self.root/D.STATE).exists())

    def test_drift_refuses_entire_rollback(self):
        D.install(self.root,self.rows,'boot-a')
        (self.root/list(D.PATHS)[-1]).write_text('external edit')
        with self.assertRaises(ValueError):D.restore_files(self.root,self.rows,'boot-a')
        self.assertTrue(all((self.root/n).exists() for n in D.PATHS))

    def test_wrong_boot_refuses_rollback(self):
        D.install(self.root,self.rows,'boot-a')
        with self.assertRaises(ValueError):D.restore_files(self.root,self.rows,'boot-b')
        self.assertTrue(all((self.root/n).exists() for n in D.PATHS))

    def test_partial_install_recovers_without_assuming_all_files_exist(self):
        real=__import__('os').link
        count=[0]
        def fail(src,dst):
            count[0]+=1
            if count[0]==2:raise OSError('injected crash before exposing second file')
            real(src,dst)
        with patch.object(D.os,'link',fail):
            with self.assertRaises(OSError):D.install(self.root,self.rows,'boot-a')
        D.restore_files(self.root,self.rows,'boot-a')
        self.assertTrue(all(not (self.root/n).exists() and not (self.root/(n+'.test371-pending')).exists() for n in D.PATHS))

    def test_partial_temporary_bytes_recover_only_registered_prefix(self):
        D.install(self.root,self.rows,'boot-a')
        name=next(iter(self.rows))
        p=self.root/(name+'.test371-pending')
        p.write_bytes(base64.b64decode(self.rows[name]['base64'])[:3])
        p.chmod(D.PATHS[name])
        D.restore_files(self.root,self.rows,'boot-a')
        self.assertFalse(p.exists())

    def test_corrupt_temporary_prevents_all_deletions(self):
        D.install(self.root,self.rows,'boot-a')
        name=next(iter(self.rows))
        p=self.root/(name+'.test371-pending')
        p.write_bytes(b'unknown')
        p.chmod(D.PATHS[name])
        with self.assertRaises(ValueError):D.restore_files(self.root,self.rows,'boot-a')
        self.assertTrue(all((self.root/n).exists() for n in D.PATHS))

    def test_partial_start_cleanup_uses_frozen_source_not_device_import(self):
        D.install(self.root,self.rows,'boot-a')
        (self.root/next(iter(self.rows))).unlink()
        def run(args,**kwargs):
            return SimpleNamespace(returncode=3 if 'is-active' in args else 0,stdout='not-found\n')
        real_restore=D.restore_files
        real_verify=D.verify_files
        with patch.object(D,'verify_files',lambda root,rows,**kw:real_verify(self.root,rows,**kw)), \
             patch.object(D,'guard') as guard,patch.object(D.subprocess,'run',run), \
             patch.object(D,'restore_files',lambda root,rows,boot:real_restore(self.root,rows,boot)):
            result=D.deactivate(self.rows,{},'boot-a')
        self.assertEqual(result['status'],'rolled_back')
        self.assertEqual(guard.call_args.args[2],base64.b64decode(self.rows[next(iter(self.rows))]['base64']).decode())

    def test_drift_prevents_cleanup_import_or_stop(self):
        with patch.object(D,'verify_files',side_effect=ValueError('unknown edit')), \
             patch.object(D,'guard') as guard,patch.object(D.subprocess,'run') as run:
            with self.assertRaises(ValueError):D.deactivate(self.rows,{},'boot-a')
        guard.assert_not_called()
        run.assert_not_called()


class EvidenceTests(unittest.TestCase):
    def row(self,cursor='a',message='existing GMU timeout',priority='3'):
        return dict(__CURSOR=cursor,_BOOT_ID='0123456789abcdef0123456789abcdef',_TRANSPORT='kernel',
                    __MONOTONIC_TIMESTAMP='12345',PRIORITY=priority,MESSAGE=message)

    def test_existing_errors_preserved_without_classifying_new_repeat_clean(self):
        old=self.row()
        H.health([old],None,{old['MESSAGE']:1})
        new=self.row('b')
        with self.assertRaises(ValueError):H.health([old,new],[old],{old['MESSAGE']:1})

    def test_missing_or_modified_history_fails(self):
        old=self.row()
        with self.assertRaises(ValueError):H.health([], [old], {})
        changed=dict(old,MESSAGE='edited')
        with self.assertRaises(ValueError):H.health([changed],[old],{})

    def test_new_ep0_error_not_waived_as_old_known_message(self):
        old=self.row(message='request was not queued to ep0out')
        with self.assertRaises(ValueError):H.health([old,self.row('b',old['MESSAGE'])],[old],{old['MESSAGE']:1})

    def test_cpu_signatures_fail_even_if_priority_warning(self):
        for message in ('watchdog: BUG: soft lockup - CPU#4 stuck','rcu: INFO: rcu_preempt detected stalls',
                        'CSD: CPU4 non-responsive','Kernel panic - not syncing','INFO: task blocked for more than 120 seconds'):
            with self.subTest(message=message),self.assertRaises(ValueError):H.health([self.row(message=message,priority='4')],None,{})

    def test_cmdline_softlockup_parameter_not_fault(self):
        for text in ('Kernel command line: softlockup_panic=0 panic=0',
                     'ramoops: using 0x200000@0x880900000, ecc: 0'):
            row=self.row(message=text,priority='6')
            self.assertEqual(H.health([row],None,{}),[])

    def test_complete_journal_requires_unique_boot_and_metadata(self):
        row=self.row()
        boot='01234567-89ab-cdef-0123-456789abcdef'
        self.assertEqual(H.journal(json.dumps(row),boot),[row])
        for raw in ('',json.dumps(row)+'\n'+json.dumps(row),json.dumps(dict(row,_BOOT_ID='other'))):
            with self.assertRaises(ValueError):H.journal(raw,boot)

    def test_normal_new_info_message_passes(self):
        old=self.row()
        new=self.row('b','USB disconnect',priority='6')
        self.assertEqual(H.health([old,new],[old],{}),[new])

    def test_repeated_unbind_and_wrong_boot_events_fail(self):
        boot='01234567-89ab-cdef-0123-456789abcdef'
        def packet(events):
            return dict(boot_id=boot,partner=False,usb_online='0',udc='',
                        lifecycle_state=dict(stdout='ActiveState=active'),
                        lifecycle=dict(stdout='\n'.join(json.dumps(dict(_BOOT_ID=boot.replace('-',''),MESSAGE=json.dumps(dict(boot_id=b,event=e)))) for b,e in events)))
        H.check_edge(packet([(boot,'unbind')]),'detached',1,0)
        for events in ([(boot,'unbind'),(boot,'unbind')],[('other','unbind')]):
            with self.assertRaises(ValueError):H.check_edge(packet(events),'detached',1,0)

    def test_first_failure_is_durable_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp)
            folder=r/'run'
            folder.mkdir()
            with patch.object(H,'R',r),patch.object(H,'ROOT',r):
                H.first_failure(folder,ValueError('first'))
                H.first_failure(folder,ValueError('second'))
            self.assertEqual(json.loads((r/'first-failure.json').read_text())['error'],'first')


class AcceptedKernelScopeTests(unittest.TestCase):
    def test_profile_is_exact_accepted370_not_old331(self):
        plan,profile=H.load()
        accepted=json.loads((ROOT/'reference/boot-tests/test-370-gmu-native-palm-escape/final-acceptance/snapshot.json').read_text())
        for k,v in profile.items():
            self.assertEqual(v,accepted['uname'].split()[2] if k=='release' else accepted[k])
        self.assertEqual(plan['boot_id'],accepted['boot_id'])
        self.assertEqual(plan['test'],371)
        self.assertFalse(plan['flashing'])
        self.assertFalse(plan['reboot'])
        self.assertFalse(plan['enable_at_boot'])
        self.assertNotEqual(profile['notes_sha256'],json.loads((ROOT/'userspace/adbd/profile-test331.json').read_text())['notes_sha256'])

    def test_frozen_fault_multiset_has_exact_accepted_source_and_no_hfi(self):
        from collections import Counter
        plan,_=H.load()
        src=plan['existing_errors_source']
        data=(ROOT/src['path']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),src['sha256'])
        rows=H.journal(data.decode(),plan['boot_id'])
        self.assertEqual(dict(Counter(r['MESSAGE'] for r in rows if int(r['PRIORITY'])<=3)),plan['existing_errors'])
        self.assertFalse(any('HFI_' in msg for msg in plan['existing_errors']))
        self.assertFalse(any('ep0out' in msg for msg in plan['existing_errors']))
        H.health(rows,None,plan['existing_errors'])

    def test_actual_same_boot_admission_rejects_old_identity_and_new_boot(self):
        plan,profile=H.load()
        d=dict(boot_id=plan['boot_id'],**profile,direct='N',roles=dict(power_role='[sink]',data_role='[device]'),
               battery=dict(POWER_SUPPLY_HEALTH='Good',POWER_SUPPLY_PRESENT='1',POWER_SUPPLY_CAPACITY='77',
                            POWER_SUPPLY_TEMP='316',POWER_SUPPLY_VOLTAGE_NOW='4250000'),
               services=dict(status=0,stdout='active\n'*4),failed=dict(status=0,stdout=''))
        H.admit(d,profile,plan['boot_id'])
        for change in (dict(boot_id='other'),dict(notes_sha256='old331'),dict(direct='Y'),dict(roles=dict(power_role='[source]',data_role='[host]'))):
            with self.subTest(change=change),self.assertRaises(ValueError):H.admit(dict(d,**change),profile,plan['boot_id'])

    def test_repeated_bind_event_is_not_accepted(self):
        boot='01234567-89ab-cdef-0123-456789abcdef'
        d=dict(boot_id=boot,partner=True,usb_online='1',udc='a600000.usb',lifecycle_state=dict(stdout='ActiveState=active'),
               lifecycle=dict(stdout='\n'.join(json.dumps(dict(_BOOT_ID=boot.replace('-',''),MESSAGE=json.dumps(dict(boot_id=boot,event=e)))) for e in ('unbind','bind','bind'))))
        with self.assertRaises(ValueError):H.check_edge(d,'attached',1,1)


if __name__=='__main__':unittest.main()
