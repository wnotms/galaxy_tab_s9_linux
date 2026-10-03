from pathlib import Path
import subprocess,hashlib,json,tarfile,gzip,difflib,importlib.util
ROOT=Path('/home/ms/Samsung/galaxy_tab_s9_linux');OUT=ROOT/'out/kernel-x710-308-passive';TREE=ROOT/'.work/build/linux-src-x710-charging';BUILD=ROOT/'.work/build/linux-out-x710-308-passive';REF=ROOT/'reference/boot-tests/test-308-ordinary-program-recovery/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
revision='158d0dd3';compiled={}
for name in ('sm5714-battery.c','sm5714-stage2.h','sm5714_usbpd.c','sm5714-pd-policy.h','sm5440-direct.c','sm5440-hw.h','x710-charging-policy.c','x710-charging-policy.h','x710-pd-session.c','x710-pd-session.h'):
 raw=subprocess.check_output(['git','-C',str(ROOT),'show',f'{revision}:kernel/drivers/{name}'])
 subsystem='usb/typec/tcpm' if name in ('sm5714_usbpd.c','sm5714-pd-policy.h') else 'power/supply'
 compiled[name]=sha(TREE/'drivers'/subsystem/name)==hashlib.sha256(raw).hexdigest()
assert all(compiled.values())
base=ROOT/'out/kernel-x710-299-passive';old=(base/'config').read_bytes();new=(OUT/'config').read_bytes()
assert new.replace(b'# CONFIG_SM5440_ADC_CONDITION_TEST is not set\n',b'')==old
assert subprocess.check_output([str(TREE/'scripts/extract-ikconfig'),str(OUT/'Image.gz')])==new
assert sha(base/'sm8550-samsung-gts9wifi.dtb')==sha(OUT/'sm8550-samsung-gts9wifi.dtb')
spec=importlib.util.spec_from_file_location('gate',ROOT/'scripts/verify-container-config.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate);container=gate.verify(new.decode());assert container['valid']
protected=json.loads((ROOT/'reference/boot-tests/test-255-sm5714-fixed-pd/validation/protected-source-hashes.json').read_text())['files'];changed={p:sha(ROOT/p) for p,v in protected.items() if sha(ROOT/p)!=v['sha256']};assert not changed
subprocess.run(['llvm-objcopy','--dump-section','.notes='+str(OUT/'kernel-notes.bin'),str(BUILD/'vmlinux'),'/dev/null'],check=True)
release=(OUT/'kernel.release').read_text().strip();mod=OUT/'modules-root/lib/modules'/release
modules={str(p.relative_to(mod)):sha(p) for p in sorted(mod.rglob('*')) if p.is_file()};assert len(modules)==181
archive=OUT/'modules-x710.tar.gz'
def normalized(info):
 if info.issym() or info.islnk():return None
 info.uid=info.gid=info.mtime=0;info.uname=info.gname='root';return info
with archive.open('wb') as raw:
 with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=3) as gz:
  with tarfile.open(fileobj=gz,mode='w|') as tar:tar.add(mod,arcname=release,filter=normalized)
with tarfile.open(archive) as tar:archived={str(Path(p.name).relative_to(release)):hashlib.sha256(tar.extractfile(p).read()).hexdigest() for p in tar.getmembers() if p.isfile()}
assert archived==modules
artifacts={name:{'path':str((OUT/name).relative_to(ROOT)),'bytes':(OUT/name).stat().st_size,'sha256':sha(OUT/name)} for name in ('Image.gz','sm8550-samsung-gts9wifi.dtb','config','kernel-notes.bin','modules-x710.tar.gz','kernel.release')}
data=dict(valid=True,source_revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',revision],text=True).strip(),config_delta={'CONFIG_SM5440_ADC_CONDITION_TEST':['absent','n']},unexpected_config_delta={},DTB_identical_to_Test299=True,compiled_source_matches=compiled,protected_file_count=len(protected),protected_changes=changed,container_gate=container,modules=modules,artifacts=artifacts,historical_stage2_image_check={'executed':False,'reason':'Image retired under owner recent-ten-round storage policy; no false frozen-image identity assertion'},device_commands_executed=False)
(REF/'artifact-audit.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({k:v for k,v in data.items() if k not in ('modules','container_gate','compiled_source_matches')},indent=2))
