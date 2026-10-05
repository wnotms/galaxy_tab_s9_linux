#!/usr/bin/env python3
"""Qualify this exact native controller candidate locally; no device operations."""
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
OUT=ROOT/'out/kernel-x710-active-session'
TREE=ROOT/'.work/build/linux-src-x710-charging'
BUILD=ROOT/'.work/build/linux-out-x710-303-policy'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((RECORD/'inputs-before.json').read_text())
errors=[]
for name,d in inputs['formal_artifacts'].items():
    if sha(ROOT/name)!=d:errors.append('formal artifact changed: '+name)
for name,h in inputs['protected_sources'].items():
    if sha(ROOT/name)!=h:errors.append('protected source changed: '+name)
final_inputs=json.loads((RECORD/'inputs-final.json').read_text())
for name,h in final_inputs['compiled_inputs'].items():
    if sha(ROOT/name)!=h:errors.append('build input changed: '+name)
spec=importlib.util.spec_from_file_location('gate',ROOT/'scripts/verify-x710-charging-profile.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
config=(OUT/'config').read_text();parsed=gate.STAGE2.CONTAINER.read_config(config)
gated=gate.verify(config,profile='sm5440-native-control');errors+=gated['errors']
deltas={}
for label,path in [('accepted311','out/kernel-x710-308-passive/config'),('Test303','out/kernel-x710-303-policy/config'),('native-control','out/kernel-sm5440-native-control/config'),('OFF-controller','out/kernel-x710-native-controller/config')]:
    old=gate.STAGE2.CONTAINER.read_config((ROOT/path).read_text())
    deltas[label]={k:[old.get(k,'absent'),parsed.get(k,'absent')] for k in sorted(old.keys()|parsed.keys()) if old.get(k,'absent')!=parsed.get(k,'absent')}
expected={
 'accepted311':{'CONFIG_X710_CHARGING_POLICY':['n','y'],'CONFIG_SM5440_ADC_CONDITION_TEST':['n','absent'],'CONFIG_X710_NATIVE_CONTROL':['absent','y']},
 'Test303':{'CONFIG_X710_NATIVE_CONTROL':['absent','y']},
 'native-control':{},
 'OFF-controller':{},
}
if deltas!=expected:errors.append('unexpected config difference')
for name,value in {'CONFIG_HVC_DCC':'n','CONFIG_USER_NS':'y','CONFIG_POSIX_MQUEUE':'y','CONFIG_BATTERY_SM5714':'y','CONFIG_QCOM_SPMI_ADC5_GEN3':'y'}.items():
    if parsed.get(name)!=value:errors.append(name+' mismatch')
dtb=OUT/'sm8550-samsung-gts9wifi.dtb'
if sha(dtb)!=sha(ROOT/'out/kernel-x710-308-passive/sm8550-samsung-gts9wifi.dtb'):errors.append('DTB changed')
compiled={}
for name in ['x710-charge-controller.c','x710-charge-controller.h','x710-charge-observer.c','x710-charge-observer.h','x710-charging-policy.c','x710-charging-policy.h','x710-pd-session.c','sm5440-direct.c','sm5440-hw.h','sm5440-native.h','sm5440-control.c','sm5440-control.h','sm5440-actuator.c','sm5440-actuator.h','sm5440-watchdog.c','sm5440-watchdog.h','sm5440-conversion.c','sm5440-conversion.h','sm5440-supervisor.c','sm5440-supervisor.h','sm5714-battery.c','sm5714-stage2.h']:
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
def elf_layout(data):
    h=struct.unpack_from('<HHIQQQIHHHHHH',data,16)
    es=[struct.unpack_from('<IIQQQQIIQQ',data,h[5]+n*h[10]) for n in range(h[11])]
    st=es[h[12]];names=data[st[4]:st[4]+st[5]]
    labels=[names[e[0]:].split(b'\0',1)[0].decode() for e in es]
    return dict(zip(labels,es)),labels,es

def semantic_symbols(data):
    layout,labels,es=elf_layout(data);sy=layout['.symtab'];st=es[sy[6]]
    strings=data[st[4]:st[4]+st[5]];result=[]
    for off in range(sy[4],sy[4]+sy[5],sy[9]):
        n,info,other,index,value,size=struct.unpack_from('<IBBHQQ',data,off)
        name=strings[n:].split(b'\0',1)[0].decode()
        result.append((name,info,other,labels[index] if index<len(labels) else index,value,size))
    return result

changed={};metadata=[];module_runtime_proof={}
for n in new:
    if new[n]==old[n]:continue
    if not n.endswith('.ko'):
        metadata.append(n);continue
    a,b=sections(old[n]),sections(new[n]);changed[n]=[k for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)]
    la,_,_=elf_layout(old[n]);lb,_,_=elf_layout(new[n])
    runtime_names={k for k,e in la.items() if e[2]&2}|{k for k,e in lb.items() if e[2]&2}
    # Build ID follows debug directory/BTF. All other allocated runtime bytes,
    # NOBITS sizes, flags/type/alignment and runtime relocations must be equal.
    exceptions={'.BTF','.note.gnu.build-id'}
    bad_runtime=[k for k in sorted(runtime_names-exceptions) if k not in la or k not in lb or
        a[k]!=b[k] or tuple(la[k][i] for i in (1,2,5,8))!=tuple(lb[k][i] for i in (1,2,5,8))]
    sa,sb=semantic_symbols(old[n]),semantic_symbols(new[n])
    symbol_changes=[];bad_symbols=[]
    if len(sa)!=len(sb):bad_symbols.append('symbol count')
    for i,(x,y) in enumerate(zip(sa,sb)):
        if x==y:continue
        symbol_changes.append({'index':i,'before':x,'after':y})
        if x[:4]!=y[:4] or x[5]!=y[5] or x[3]!='.debug_str':bad_symbols.append(i)
    oldstr=set(a['.debug_str'].split(b'\0'));newstr=set(b['.debug_str'].split(b'\0'))
    allowed_directory=str(BUILD).encode()
    unexpected_strings=(newstr-oldstr)-{allowed_directory}
    removed_strings=oldstr-newstr
    allowed_removed={str(ROOT/'.work/build/linux-out-x710-308-passive').encode()}
    unexpected_removed=removed_strings-allowed_removed
    allowed={'.BTF','.note.gnu.build-id','.debug_str','.rela.debug_info','.symtab'}
    unexpected_sections=set(changed[n])-allowed
    proof={'allocated_runtime_bytes_and_shape_unchanged':not bad_runtime,
        'bad_runtime':bad_runtime,'non_debug_symbols_unchanged':not bad_symbols,
        'changed_debug_symbols':symbol_changes,'debug_strings_added':[x.decode() for x in sorted(newstr-oldstr)],
        'debug_strings_removed':[x.decode() for x in sorted(removed_strings)],
        'unexpected_sections':sorted(unexpected_sections),
        'allowed_build_directory':str(BUILD)}
    module_runtime_proof[n]=proof
    if bad_runtime or bad_symbols or unexpected_strings or unexpected_removed or unexpected_sections:
        errors.append('unexpected module runtime/debug change: '+n)
if any(n not in ('modules.builtin','modules.builtin.bin','modules.builtin.modinfo') for n in metadata):errors.append('unexpected module metadata change')
native_modules=archived(ROOT/'out/kernel-x710-native-controller/modules-x710.tar.gz')
builtin_identity={}
for name,sep in [('modules.builtin',b'\n'),('modules.builtin.modinfo',b'\0')]:
    before=set(native_modules[name].split(sep));after=set(new[name].split(sep))
    added=after-before;removed=before-after
    builtin_identity[name]={'added':[v.decode() for v in sorted(added)],'removed':[v.decode() for v in sorted(removed)]}
    if removed:errors.append('previous builtin metadata removed: '+name)
    expected_added=set()
    if added!=expected_added:errors.append('unexpected builtin metadata additions: '+name)
    (RECORD/(name+'.diff.json')).write_text(json.dumps(builtin_identity[name],indent=2)+'\n')
# Existing controller metadata must remain exactly paired with the preceding profile.
builtin_identity['modules.builtin.bin']={'changed':new['modules.builtin.bin']!=native_modules['modules.builtin.bin']}

names=subprocess.check_output(['llvm-nm','--defined-only',str(BUILD/'vmlinux')],text=True)
required_refs=['sm5440_control_prepare','sm5440_watchdog_arm_off','sm5440_actuator_start',
 'sm5440_actuator_stop','sm5440_actuator_pause','sm5440_actuator_resume',
 'sm5440_conversion_begin','sm5440_conversion_advance','sm5440_conversion_finish',
 'sm5440_conversion_cancel','sm5440_supervisor_begin','sm5440_supervisor_advance',
 'sm5440_supervisor_cancel']
linked={n:any(line.endswith(' '+n) for line in names.splitlines()) for n in
 ['sm5440_native_control','sm5440_native_quiesce','x710_charge_request_observation','x710_charge_controller_request','x710_charge_controller_status','x710_charge_controller_cancel','x710_controller_work','x710_controller_pm','x710_controller_tick']+required_refs}
if not all(linked.values()):errors.append('native API/PM/hardware helpers not linked')
obj=BUILD/'drivers/power/supply/sm5440-direct.o'
native_references=subprocess.check_output(['llvm-nm','-u',str(obj)],text=True)
if not all(any(line.endswith(' '+n) for line in native_references.splitlines()) for n in required_refs):
    errors.append('bound driver does not reference actual hardware helpers')
(RECORD/'native-object-references.txt').write_text(native_references)
for name in ['sm5714_pd_read_owned_snapshot','sm5714_battery_switching_check']:
    if not any(line.endswith(' '+name) for line in native_references.splitlines()):errors.append('missing native source binding reference: '+name)
controller_refs=['sm5440_native_control','sm5440_passive_request_fresh','sm5714_battery_read_pack',
 'sm5714_battery_switching_acquire','sm5714_pd_read_snapshot','sm5714_pd_read_owned_snapshot',
 'sm5714_pd_request_pps','sm5714_pd_restore_fixed','sm5714_pd_release_fixed',
 'x710_charge_request_observation','x710_charge_start','x710_charge_stop',
 'x710_charge_refresh','x710_charge_retarget','x710_charge_monitor']
controller_object=subprocess.check_output(['llvm-nm','-u',str(BUILD/'drivers/power/supply/x710-charge-controller.o')],text=True)
(RECORD/'controller-object-references.txt').write_text(controller_object)
if not all(any(line.endswith(' '+n) for line in controller_object.splitlines()) for n in controller_refs):
    errors.append('controller is not linked to actual supplier/core operations')

report={'valid':not errors,'errors':errors,'profile_gate':gated,'config_diff':deltas,'DTB_diff':[],'embedded_config_identical':embedded==(OUT/'config').read_bytes(),'compiled_sources':compiled,'protected_source_count':len(inputs['protected_sources']),'preserved_formal_artifact_count':len(inputs['formal_artifacts']),'module_file_count':len(new),'changed_module_sections':changed,'module_runtime_proof':module_runtime_proof,'native_references':required_refs,'changed_builtin_metadata':metadata,'builtin_metadata_delta_from_native_control':builtin_identity,'controller_references':controller_refs,'linked':linked,'artifacts':{n:{'path':str((OUT/n).relative_to(ROOT)),'bytes':(OUT/n).stat().st_size,'sha256':sha(OUT/n)} for n in ['Image.gz','sm8550-samsung-gts9wifi.dtb','config','kernel-notes.bin','modules-x710.tar.gz','kernel.release']},'upstream_revision':subprocess.check_output(['git','-C',str(TREE),'rev-parse','HEAD'],text=True).strip(),'source_inputs':'inputs-before.json/inputs-final.json','device_operations':[],'software_ocp_verified':False,'conversion_freshness_proven':False,'pump_activation_available':False,'physical_executed':False}
(RECORD/'artifact-audit.json.gz').write_bytes(gzip.compress((json.dumps(report,indent=2)+'\n').encode(),mtime=0))
print(json.dumps({k:report[k] for k in ['valid','errors','config_diff','module_file_count','changed_builtin_metadata','linked']},indent=2))
raise SystemExit(bool(errors))
