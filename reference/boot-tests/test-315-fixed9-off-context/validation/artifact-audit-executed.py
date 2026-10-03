"""Executed local Test315 qualification; no device access."""
from pathlib import Path
import subprocess, hashlib, json, tarfile, gzip, difflib, importlib.util
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'out/kernel-x710-315-fixed9-context'
TREE=ROOT/'.work/build/linux-src-x710-charging'
BUILD=ROOT/'.work/build/linux-out-x710-308-passive'
REF=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
revision=json.loads((REF/'build.json').read_text())['source_revision']
compiled={}
for name in ('sm5714-battery.c','sm5714-stage2.h','sm5714_usbpd.c','sm5714-pd-policy.h','sm5440-direct.c','sm5440-hw.h','x710-charging-policy.c','x710-charging-policy.h','x710-pd-session.c','x710-pd-session.h','sm5440-control.c','sm5440-control.h'):
    raw=subprocess.check_output(['git','-C',str(ROOT),'show',f'{revision}:kernel/drivers/{name}'])
    subsystem='usb/typec/tcpm' if name in ('sm5714_usbpd.c','sm5714-pd-policy.h') else 'power/supply'
    compiled[name]=sha(TREE/'drivers'/subsystem/name)==hashlib.sha256(raw).hexdigest()
assert all(compiled.values())
base=ROOT/'out/kernel-x710-308-passive'
old=(base/'config').read_bytes();new=(OUT/'config').read_bytes()
expected=old.replace(b'# CONFIG_SM5440_ADC_CONDITION_TEST is not set\n',b'CONFIG_SM5440_ADC_CONDITION_TEST=y\n')
assert new==expected, 'unexpected resolved config changes'
assert subprocess.check_output([str(TREE/'scripts/extract-ikconfig'),str(OUT/'Image.gz')])==new
assert sha(base/'sm8550-samsung-gts9wifi.dtb')==sha(OUT/'sm8550-samsung-gts9wifi.dtb')
for module,path in [('container','scripts/verify-container-config.py'),('profile','scripts/verify-x710-charging-profile.py')]:
    spec=importlib.util.spec_from_file_location(module,ROOT/path);gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    if module=='container':container=gate.verify(new.decode());assert container['valid']
    else:profile=gate.verify(new.decode(),profile='sm5440-adc-condition');assert profile['valid']
protected=json.loads((ROOT/'reference/boot-tests/test-255-sm5714-fixed-pd/validation/protected-source-hashes.json').read_text())['files']
changed={p:sha(ROOT/p) for p,v in protected.items() if sha(ROOT/p)!=v['sha256']};assert not changed
subprocess.run(['llvm-objcopy','--dump-section','.notes='+str(OUT/'kernel-notes.bin'),str(BUILD/'vmlinux'),'/dev/null'],check=True)
symbols=subprocess.check_output(['llvm-nm',str(BUILD/'vmlinux')],text=True)
functions=('sm5440_control_prepare','sm5440_control_restore')
for name in functions:
    assert any(line.split()[-2:]==['T',name] for line in symbols.splitlines()),name
    assert '__ksymtab_'+name not in symbols,name
release=(OUT/'kernel.release').read_text().strip();mod=OUT/'modules-root/lib/modules'/release
modules={str(p.relative_to(mod)):sha(p) for p in sorted(mod.rglob('*')) if p.is_file()};assert len(modules)==181
archive=OUT/'modules-x710.tar.gz'
def normalized(info):
    if info.issym() or info.islnk():return None
    info.uid=info.gid=info.mtime=0;info.uname=info.gname='root';return info
with archive.open('wb') as raw:
    with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=3) as gz:
        with tarfile.open(fileobj=gz,mode='w|') as tar:tar.add(mod,arcname=release,filter=normalized)
with tarfile.open(archive) as tar:
    archived={str(Path(p.name).relative_to(release)):hashlib.sha256(tar.extractfile(p).read()).hexdigest() for p in tar.getmembers() if p.isfile()}
assert archived==modules
# Old formal accepted / diagnostic artifacts survive incremental cache reuse.
old312=json.loads((REF/'reuse-freeze.json').read_text())['formal314_artifacts_verified']
for row in old312.values():assert sha(ROOT/row['path'])==row['sha256']
old308=json.loads((ROOT/'reference/boot-tests/test-312-adc-condition-requalification/validation/reuse-freeze.json').read_text())['formal_Test308_artifacts_verified_unchanged']
for row in old308.values():assert sha(ROOT/row['path'])==row['sha256']
artifacts={name:{'path':str((OUT/name).relative_to(ROOT)),'bytes':(OUT/name).stat().st_size,'sha256':sha(OUT/name)} for name in ('Image.gz','sm8550-samsung-gts9wifi.dtb','config','kernel-notes.bin','modules-x710.tar.gz','kernel.release')}
data=dict(valid=True,source_revision=revision,config_delta={'CONFIG_SM5440_ADC_CONDITION_TEST':['n','y']},unexpected_config_delta={},DTB_identical_to_accepted_Test308_Test311=True,compiled_source_matches=compiled,protected_file_count=len(protected),protected_changes=changed,container_gate=container,profile_gate=profile,modules=modules,artifacts=artifacts,compiled_not_exported=functions,unchanged_formal314_and_accepted308_verified=True,physical_executed=False,hardware_activation_available=False)
(REF/'accepted311-config.diff').write_text(''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='accepted308/311/config',tofile='Test315/config')))
(REF/'artifact-audit.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(dict(valid=True,config_delta=data['config_delta'],unexpected={},DTB_identical=True,protected_files=len(protected),compiled_overlays=len(compiled),modules=len(modules),functions=list(functions),physical_executed=False),indent=2))
