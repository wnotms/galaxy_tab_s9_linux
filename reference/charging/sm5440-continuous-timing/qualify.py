#!/usr/bin/env python3
"""Qualify this exact OFF timing candidate locally; no device operations."""
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import struct
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[3]
RECORD=Path(__file__).resolve().parent
OUT=ROOT/'out/kernel-x710-continuous-timing'
TREE=ROOT/'.work/build/linux-src-x710-charging'
BUILD=ROOT/'.work/build/linux-out-x710-308-passive'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((RECORD/'inputs-final.json').read_text())
errors=[]
for name,d in inputs['formal_artifacts'].items():
    if sha(ROOT/d['path'])!=d['sha256']:errors.append('formal artifact changed: '+name)
for name,h in inputs['protected_sources'].items():
    if sha(ROOT/name)!=h:errors.append('protected source changed: '+name)
for name,h in inputs['inputs'].items():
    if sha(ROOT/name)!=h:errors.append('build input changed: '+name)
for name,h in inputs['changed_scripts'].items():
    if sha(ROOT/name)!=h:errors.append('build script changed: '+name)
spec=importlib.util.spec_from_file_location('gate',ROOT/'scripts/verify-x710-charging-profile.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
config=(OUT/'config').read_text();parsed=gate.STAGE2.CONTAINER.read_config(config)
gated=gate.verify(config,profile='sm5440-adc-timing');errors+=gated['errors']
deltas={}
for label,path in [('accepted311','out/kernel-x710-308-passive/config'),('Test316','out/kernel-x710-316-fixed-contract/config'),('native-pack','out/kernel-x710-pack-observation/config')]:
    old=gate.STAGE2.CONTAINER.read_config((ROOT/path).read_text())
    deltas[label]={k:[old.get(k,'absent'),parsed.get(k,'absent')] for k in sorted(old.keys()|parsed.keys()) if old.get(k,'absent')!=parsed.get(k,'absent')}
expected={'accepted311':{'CONFIG_SM5440_ADC_TIMING_TEST':['absent','y']},'Test316':{'CONFIG_SM5440_ADC_CONDITION_TEST':['y','n'],'CONFIG_SM5440_ADC_TIMING_TEST':['absent','y']},'native-pack':{'CONFIG_SM5440_ADC_CONDITION_TEST':['absent','n'],'CONFIG_X710_CHARGING_POLICY':['y','n'],'CONFIG_SM5440_ADC_TIMING_TEST':['absent','y']}}
if deltas!=expected:errors.append('unexpected config difference')
for name,value in {'CONFIG_HVC_DCC':'n','CONFIG_USER_NS':'y','CONFIG_POSIX_MQUEUE':'y','CONFIG_BATTERY_SM5714':'y','CONFIG_QCOM_SPMI_ADC5_GEN3':'y'}.items():
    if parsed.get(name)!=value:errors.append(name+' mismatch')
dtb=OUT/'sm8550-samsung-gts9wifi.dtb'
if sha(dtb)!=sha(ROOT/'out/kernel-x710-308-passive/sm8550-samsung-gts9wifi.dtb'):errors.append('DTB changed')
compiled={}
for name in ['sm5440-direct.c','sm5440-timing.c','sm5440-timing.h','sm5440-hw.h','sm5714-battery.c','sm5714-stage2.h']:
    compiled[name]=sha(ROOT/'kernel/drivers'/name)==sha(TREE/'drivers/power/supply'/name)
for name in ['sm5714_usbpd.c','sm5714-stage2.h','sm5714-pd-policy.h']:
    compiled['tcpc/'+name]=sha(ROOT/'kernel/drivers'/name)==sha(TREE/'drivers/usb/typec/tcpm'/name)
if not all(compiled.values()):errors.append('compiled source mismatch')
embedded=subprocess.check_output([str(TREE/'scripts/extract-ikconfig'),str(OUT/'Image.gz')])
if embedded!=(OUT/'config').read_bytes():errors.append('embedded config mismatch')
subprocess.run(['llvm-objcopy','--dump-section','.notes='+str(OUT/'kernel-notes.bin'),str(BUILD/'vmlinux'),'/dev/null'],check=True)
release=(OUT/'kernel.release').read_text().strip();module_dir=OUT/'modules-root/lib/modules'/release
new={str(p.relative_to(module_dir)):p.read_bytes() for p in sorted(module_dir.rglob('*')) if p.is_file()}
archive=OUT/'modules-x710.tar.gz'
def normalized(info):
    if info.issym() or info.islnk():return None
    info.uid=info.gid=info.mtime=0;info.uname=info.gname='root';return info
with archive.open('wb') as raw:
    with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=3) as gz:
        with tarfile.open(fileobj=gz,mode='w') as t:t.add(module_dir,arcname=release,filter=normalized)
def archived(path):
    with tarfile.open(path,'r:gz') as t:
        return {m.name.removeprefix(release+'/'):t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
old=archived(ROOT/'out/kernel-x710-308-passive/modules-x710.tar.gz')
if len(new)!=181 or new.keys()!=old.keys() or archived(archive)!=new:errors.append('paired module file set/archive mismatch')
def sections(data):
    if data[:6]!=b'\x7fELF\x02\x01':raise ValueError('not ELF64 little endian')
    hdr=struct.unpack_from('<HHIQQQIHHHHHH',data,16)
    entries=[struct.unpack_from('<IIQQQQIIQQ',data,hdr[5]+n*hdr[10]) for n in range(hdr[11])]
    string=entries[hdr[12]];names=data[string[4]:string[4]+string[5]]
    result={}
    for e in entries:
        name=names[e[0]:].split(b'\0',1)[0].decode()
        result[name]=b'' if e[1]==8 else data[e[4]:e[4]+e[5]]
    return result
changed={};metadata=[]
for n in new:
    if new[n]==old[n]:continue
    if not n.endswith('.ko'):
        metadata.append(n);continue
    a,b=sections(old[n]),sections(new[n]);changed[n]=[k for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)]
    if any(k!='.BTF' for k in changed[n]):errors.append('module code/data changed: '+n)
if any(n not in ('modules.builtin','modules.builtin.bin','modules.builtin.modinfo') for n in metadata):errors.append('unexpected module metadata change')
names=subprocess.check_output(['llvm-nm','--defined-only',str(BUILD/'vmlinux')],text=True)
linked={n:any(line.endswith(' '+n) for line in names.splitlines()) for n in ['sm5440_timing_begin','sm5440_timing_step','sm5440_timing_finish','sm5440_timing_cycle','sm5714_battery_read_pack']}
if not all(linked.values()):errors.append('actual timing/native pack not linked')
report={'valid':not errors,'errors':errors,'profile_gate':gated,'config_diff':deltas,'DTB_diff':[],'embedded_config_identical':embedded==(OUT/'config').read_bytes(),'compiled_sources':compiled,'protected_source_count':len(inputs['protected_sources']),'preserved_formal_artifact_count':len(inputs['formal_artifacts']),'module_file_count':len(new),'changed_module_sections':changed,'changed_builtin_metadata':metadata,'linked':linked,'artifacts':{n:{'path':str((OUT/n).relative_to(ROOT)),'bytes':(OUT/n).stat().st_size,'sha256':sha(OUT/n)} for n in ['Image.gz','sm8550-samsung-gts9wifi.dtb','config','kernel-notes.bin','modules-x710.tar.gz','kernel.release']},'upstream_revision':subprocess.check_output(['git','-C',str(TREE),'rev-parse','HEAD'],text=True).strip(),'source_inputs':'inputs-final.json','device_operations':[],'software_ocp_verified':False}
(RECORD/'artifact-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['valid','errors','config_diff','module_file_count','changed_builtin_metadata','linked']},indent=2))
raise SystemExit(bool(errors))
