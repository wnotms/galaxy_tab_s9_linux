import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('registry_mutation_test',ROOT/'userspace/sensors/registry_mutation_evidence.py')
E=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(E)
BOOT='11111111-1111-4111-8111-111111111111'
V='/mnt/vendor/persist/sensors/registry/registry/'


def snapshot(data,phase='before',boot=BOOT):
    return dict(schema=1,machine_id=E.MACHINE,boot_id=boot,phase=phase,prefix=E.PREFIX,
                producers_inactive=True,bytes=sum(len(x)for x in data.values()),files={
        n:dict(bytes=len(x),data_hex=x.hex(),sha256=E.digest(x),mode=0o644,uid=80,gid=80,mtime_ns=123000000000)
        for n,x in data.items()})


def manifest(data):
    return {E.PREFIX+n:dict(bytes=len(x),sha256=E.digest(x),mode=0o644,mtime=123)for n,x in data.items()}


def call(method,incoming,outgoing=(),status=0,transport=0):
    sc=(method<<24)|(len(incoming)<<16)|(len(outgoing)<<8)
    if method>=31:
        sc=(31<<24)|(len(incoming)<<16)|(len(outgoing)<<8)
    return dict(response_to=dict(handle=1,scalars=sc,buffers_hex=[x.hex()for x in incoming],output_capacities=[len(x)for x in outgoing]),
                returned_buffers_hex=[x.hex()for x in outgoing],status=status,transport_return=transport)


def opened(path,mode='r',fd=3):
    return call(19,[b'',b'ADSP_LIBRARY_PATH\0',b'',path.encode()+b'\0',mode.encode()+b'\0'],[struct.pack('<I',fd)])


def read(data,fd=3):
    return call(4,[struct.pack('<II',fd,len(data))],[struct.pack('<II',len(data),0),data])


def write(data,fd=3):
    return call(5,[struct.pack('<II',fd,len(data)),data],[struct.pack('<II',len(data),0)])


def close(fd=3):
    return call(3,[struct.pack('<I',fd)])


def rename(source,target):
    return call(33,[struct.pack('<I',33),source.encode()+b'\0',target.encode()+b'\0'])


def frames(calls):
    records=[]
    for i,c in enumerate(calls):records.append(dict(c,sequence=i,tx_row=i))
    return dict(complete=True,boot_id=BOOT.replace('-',''),streams=[dict(unit=E.UNIT,pid='17',calls=records,pending_final_call=None)])


class RegistryMutationTests(unittest.TestCase):
    def replay(self,calls,before=None,after=None):
        before=before or {'registry/group':b'old','sns_reg.conf':b'version=6\n'}
        after=before if after is None else after
        return E.replay(frames(calls),BOOT,snapshot(before),snapshot(after,'after'),manifest(before))

    def assert_fault(self,calls,reason,before=None,after=None):
        r=self.replay(calls,before,after)
        self.assertFalse(r['complete']);self.assertTrue(any(reason in f['reason']for f in r['faults']),r['faults'])

    def test_read_only_replay_keeps_original_hashes(self):
        r=self.replay([opened(V+'group'),read(b'old'),close()])
        self.assertTrue(r['complete'],r['faults']);self.assertEqual(r['changed_members'],[])
        self.assertFalse(r['DSP_parsing_proved']);self.assertFalse(r['SSC_publication_proved'])

    def test_write_temp_then_extended_rename_matches_final(self):
        r=self.replay([opened(V+'temp.json','w'),write(b'new'),close(),rename(V+'temp.json',V+'group')],
            after={'registry/group':b'new','sns_reg.conf':b'version=6\n'})
        self.assertTrue(r['complete'],r['faults']);self.assertEqual(r['counts']['renames'],1)
        self.assertEqual(r['changed_members'],['registry/group'])

    def test_read_generated_file_checks_current_bytes(self):
        r=self.replay([opened(V+'group','w'),write(b'new'),close(),opened(V+'group'),read(b'new'),close()],
            after={'registry/group':b'new','sns_reg.conf':b'version=6\n'})
        self.assertTrue(r['complete'],r['faults'])

    def test_corrupt_generated_read_is_not_accepted(self):
        self.assert_fault([opened(V+'group','w'),write(b'new'),close(),opened(V+'group'),read(b'bad'),close()],
                          'returned read bytes',after={'registry/group':b'new','sns_reg.conf':b'version=6\n'})

    def test_append_uses_end_of_file(self):
        r=self.replay([opened(V+'group','a'),write(b'!'),close()],after={'registry/group':b'old!','sns_reg.conf':b'version=6\n'})
        self.assertTrue(r['complete'],r['faults'])

    def test_read_write_mode_and_seek_are_modelled(self):
        r=self.replay([opened(V+'group','r+'),call(9,[struct.pack('<III',3,1,0)]),write(b'X'),close()],
            after={'registry/group':b'oXd','sns_reg.conf':b'version=6\n'})
        self.assertTrue(r['complete'],r['faults'])

    def test_replacement_preserves_old_open_inode(self):
        r=self.replay([opened(V+'group',fd=3),opened(V+'temp.json','w',4),write(b'new',4),close(4),
                       rename(V+'temp.json',V+'group'),read(b'old',3),close(3)],
            after={'registry/group':b'new','sns_reg.conf':b'version=6\n'})
        self.assertTrue(r['complete'],r['faults'])

    def test_registry_parent_alias_and_version_mapping(self):
        self.assertEqual(E.mapped(V+'../sns_reg_version'),'sns_reg_version')
        self.assertEqual(E.mapped('/persist/sensors/registry/registry/group'),'registry/group')
        self.assertEqual(E.mapped('/vendor/etc/sensors/sns_reg_config'),'sns_reg.conf')
        self.assertEqual(E.mapped('/system/vendor/etc/sensors/config/sns_cm.json'),'config/sns_cm.json')

    def test_config_write_rejected(self):
        self.assert_fault([opened('/vendor/etc/sensors/config/sns_cm.json','w')],'write outside')

    def test_unmapped_physical_persist_write_rejected(self):
        self.assert_fault([opened('/mnt/vendor/persist/sensors/secret','w')],'outside isolated')

    def test_rename_escaping_registry_rejected(self):
        self.assert_fault([rename(V+'group','/vendor/etc/sensors/config/sns_cm.json')],'rename scope')

    def test_unexplained_final_file_change_rejected(self):
        self.assert_fault([],'final snapshot differs',after={'registry/group':b'bad','sns_reg.conf':b'version=6\n'})

    def test_new_unexplained_file_rejected(self):
        self.assert_fault([],'final snapshot differs',after={'registry/group':b'old','registry/new':b'x','sns_reg.conf':b'version=6\n'})

    def test_transport_failure_rejected(self):
        c=write(b'new');c['transport_return']=-1
        self.assert_fault([opened(V+'group','w'),c,close()],'unsuccessful/unacknowledged')

    def test_short_write_rejected(self):
        c=write(b'new');c['returned_buffers_hex']=[struct.pack('<II',2,0).hex()]
        self.assert_fault([opened(V+'group','w'),c,close()],'short registry write')

    def test_reply_larger_than_requested_capacity_rejected(self):
        c=write(b'new');c['response_to']['output_capacities']=[4]
        self.assert_fault([opened(V+'group','w'),c,close()],'output capacity')

    def test_unknown_write_descriptor_rejected(self):
        self.assert_fault([write(b'new')],'unattributed write')

    def test_unclosed_descriptor_rejected(self):
        self.assert_fault([opened(V+'group','w')],'unclosed mutable')

    def test_retained_bootstrap_reader_reported_without_invented_close(self):
        r=self.replay([opened('/vendor/etc/sensors/sns_reg_config'),read(b'version=6\n')])
        self.assertTrue(r['complete'],r['faults'])
        self.assertEqual(r['open_readonly_at_journal_boundary'][0]['member'],'sns_reg.conf')
        self.assertEqual(r['counts']['closes'],0)

    def test_descriptor_reuse_rejected(self):
        self.assert_fault([opened(V+'group'),opened(V+'group')],'descriptor reuse')

    def test_unknown_app_method_rejected(self):
        self.assert_fault([call(20,[b'bad'])],'unmodelled')

    def test_wrong_snapshot_boot_rejected(self):
        data={'registry/group':b'old'}
        with self.assertRaisesRegex(ValueError,'snapshot identity'):
            E.replay(frames([]),BOOT,snapshot(data),snapshot(data,'after','22222222-2222-4222-8222-222222222222'),manifest(data))

    def test_before_manifest_mismatch_rejected(self):
        data={'registry/group':b'old'};m=manifest(data);m[E.PREFIX+'registry/group']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'qualified profile'):
            E.replay(frames([]),BOOT,snapshot(data),snapshot(data,'after'),m)

    def test_snapshot_hash_mismatch_rejected(self):
        s=snapshot({'registry/group':b'old'});s['files']['registry/group']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash'):
            E.decode_snapshot(s,BOOT,'before')

    def test_executable_snapshot_file_rejected(self):
        s=snapshot({'registry/group':b'old'});s['files']['registry/group']['mode']=0o755
        with self.assertRaisesRegex(ValueError,'metadata'):
            E.decode_snapshot(s,BOOT,'before')

    def test_after_snapshot_must_be_quiescent(self):
        data={'registry/group':b'old'};after=snapshot(data,'after');after['producers_inactive']=False
        with self.assertRaisesRegex(ValueError,'quiescence'):
            E.replay(frames([]),BOOT,snapshot(data),after,manifest(data))

    def test_snapshot_collector_refuses_symlink_and_running_producer(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'etc').mkdir();(root/'etc/machine-id').write_text(E.MACHINE)
            p=root/'proc/sys/kernel/random';p.mkdir(parents=True);(p/'boot_id').write_text(BOOT)
            p=root/E.PREFIX;p.mkdir(parents=True);(p/'file').write_bytes(b'input')
            with self.assertRaisesRegex(ValueError,'inactive'):
                E.capture(BOOT,'before',root=root,quiescent=lambda:False)
            good=E.capture(BOOT,'before',root=root,quiescent=lambda:True)
            self.assertEqual(E.decode_snapshot(good,BOOT,'before'),{'file':b'input'})
            (p/'link').symlink_to(p/'file')
            with self.assertRaisesRegex(ValueError,'symlink'):
                E.capture(BOOT,'before',root=root,quiescent=lambda:True)

    def test_real_test400_frames_replay_original_archive_inputs(self):
        spec=importlib.util.spec_from_file_location('mutation_real_archive',ROOT/'userspace/sensors/fedora_adsp_profile.py')
        a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
        archive=a.read_archive(ROOT/'out/ssc-fedora-adsp-profile/sensor-assets.tar.gz',
            'd647dcdf5ecc010080dbd057cec2c9cc66368d9e241cc3883a532e3f648177b3')
        data={n[len(E.PREFIX):]:row['data']for n,row in archive.items()if n.startswith(E.PREFIX)}
        m={n:dict(bytes=len(row['data']),sha256=E.digest(row['data']),mode=row['mode'],mtime=row['mtime'])for n,row in archive.items()}
        boot='3ff4d010-adab-48b2-b34d-0bde9a50b472'
        before=snapshot(data,boot=boot);after=snapshot(data,'after',boot)
        for n in data:
            before['files'][n]['mtime_ns']=after['files'][n]['mtime_ns']=archive[E.PREFIX+n]['mtime']*1000000000
            before['files'][n]['mode']=after['files'][n]['mode']=archive[E.PREFIX+n]['mode']
        raw=(ROOT/'reference/boot-tests/test-400-fedora-adsp-comparison/runtime-discovery/discovery-unit-journal.txt').read_text()
        f=E.RETURN.inspect(raw,boot);self.assertTrue(f['complete'],f['faults'])
        report=E.replay(f,boot,before,after,m)
        self.assertTrue(report['complete'],report['faults']);self.assertGreater(report['counts']['reads'],178)
        self.assertEqual(report['counts']['writes'],0)


class RealRegistryCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.folder=Path(cls.temp.name);cls.binary=cls.folder/'callbacks'
        source=ROOT/'out/rpc-readdir/build/work/hexagonrpc'
        directory=source/'hexagonrpcd'
        command=['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-function',
                 '-Wno-unused-parameter','-fsanitize=undefined','-fno-sanitize-recover=all',
                 '-ffunction-sections','-fdata-sections','-I'+str(source/'include'),'-I'+str(directory),
                 str(ROOT/'tests/fixtures/rpc_registry_write_harness.c'),
                 str(directory/'hexagonfs.c'),str(directory/'hexagonfs_virt_dir.c'),
                 str(directory/'hexagonfs_mapped.c'),'-Wl,--gc-sections','-o',str(cls.binary)]
        subprocess.run(command,check=True,capture_output=True,text=True,timeout=30)

    def case(self,mode):
        with tempfile.TemporaryDirectory(dir=self.folder) as temp:
            root=Path(temp);(root/'group').write_bytes(b'old')
            r=subprocess.run([str(self.binary),mode,str(root)],capture_output=True,text=True,check=True,timeout=5)
            self.assertNotIn('runtime error',r.stderr)
            return json.loads(r.stdout.splitlines()[-1]),{p.name:p.read_bytes()for p in root.iterdir()}

    def test_real_write_reply_and_content(self):
        r,files=self.case('write');self.assertEqual((r['status'],r['written'],r['eof']),(0,3,0))
        self.assertEqual(files,{'group':b'new'})

    def test_real_append(self):
        r,files=self.case('append');self.assertEqual(r['status'],0)
        self.assertEqual(files,{'group':b'oldnew'})

    def test_real_rename(self):
        r,files=self.case('rename');self.assertEqual((r['status'],r['rename_status']),(0,0))
        self.assertEqual(files,{'renamed':b'new'})

    def test_short_input_rejected_without_write(self):
        r,files=self.case('short-input');self.assertNotEqual(r['status'],0)
        self.assertEqual(r['written'],0xffffffff);self.assertEqual(files,{'group':b'old'})

    def test_readonly_descriptor_cannot_write(self):
        r,files=self.case('readonly');self.assertNotEqual(r['status'],0)
        self.assertEqual(files,{'group':b'old'})


if __name__=='__main__':unittest.main()
