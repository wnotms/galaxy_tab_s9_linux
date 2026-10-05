#!/usr/bin/env python3
"""Qualify ordinary/passive image and module pairing locally, never deploy."""
from pathlib import Path
import ast, gzip, hashlib, importlib.util, json, struct, subprocess, tarfile
ROOT=Path(__file__).resolve().parents[3]
R=Path(__file__).resolve().parent
OUT=ROOT/'out/kernel-x710-pc-ordinary'
TREE=ROOT/'.work/build/linux-src-x710-charging'
BUILD=ROOT/'.work/build/linux-out-x710-308-passive'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((R/'inputs-before.json').read_text())
for category in ('protected_sources','formal_artifacts'):
 for name,h in inputs[category].items():
  if sha(ROOT/name)!=h:raise ValueError('frozen input changed: '+name)
spec=importlib.util.spec_from_file_location('gate',ROOT/'scripts/verify-x710-charging-profile.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
config=(OUT/'config').read_bytes()
gated=gate.verify(config.decode(),profile='sm5440-passive')
if not gated['valid']:raise ValueError(gated['errors'])
before=gate.STAGE2.CONTAINER.read_config((ROOT/'out/kernel-x710-308-passive/config').read_text())
after=gate.STAGE2.CONTAINER.read_config(config.decode())
delta={k:[before.get(k,'absent'),after.get(k,'absent')] for k in sorted(before.keys()|after.keys()) if before.get(k,'absent')!=after.get(k,'absent')}
expected={'CONFIG_SM5440_ADC_RAW_TEST':['absent','n'],'CONFIG_SM5440_ADC_TIMING_TEST':['absent','n']}
if delta!=expected:raise ValueError('unexpected config delta: '+str(delta))
if sha(OUT/'sm8550-samsung-gts9wifi.dtb')!=sha(ROOT/'out/kernel-x710-308-passive/sm8550-samsung-gts9wifi.dtb'):raise ValueError('DTB changed')
if subprocess.check_output([str(TREE/'scripts/extract-ikconfig'),str(OUT/'Image.gz')])!=config:raise ValueError('embedded config differs')
compiled={}
for name,subsystem in [('sm5714-battery.c','power/supply'),('sm5440-direct.c','power/supply'),('sm5440-hw.h','power/supply'),('sm5714-stage2.h','power/supply'),('sm5714_usbpd.c','usb/typec/tcpm'),('sm5714-stage2.h','usb/typec/tcpm'),('sm5714-pd-policy.h','usb/typec/tcpm')]:
 compiled[subsystem+'/'+name]=sha(ROOT/'kernel/drivers'/name)
 if compiled[subsystem+'/'+name]!=sha(TREE/'drivers'/subsystem/name):raise ValueError('prepared source mismatch: '+name)
subprocess.run(['llvm-objcopy','--dump-section','.notes='+str(OUT/'kernel-notes.bin'),str(BUILD/'vmlinux'),'/dev/null'],check=True)
release=(OUT/'kernel.release').read_text().strip()
if release!='7.2.0-rc3-gts9wifi-dirty':raise ValueError('release changed')
module_dir=OUT/'modules-root/lib/modules'/release
new={str(p.relative_to(module_dir)):p.read_bytes() for p in sorted(module_dir.rglob('*')) if p.is_file()}
def archived(path):
 with tarfile.open(path,'r:gz') as t:
  result={}
  for m in t:
   if m.isdir():continue
   if not m.isfile() or not m.name.startswith(release+'/'):raise ValueError('unsafe archive member')
   n=m.name.removeprefix(release+'/')
   if n in result or '..' in Path(n).parts:raise ValueError('duplicate/unsafe module path')
   result[n]=t.extractfile(m).read()
  return result
old=archived(ROOT/'out/kernel-x710-308-passive/modules-x710.tar.gz')
if len(new)!=181 or new.keys()!=old.keys():raise ValueError('module file set')
def normalized(info):
 if info.issym() or info.islnk():return None
 info.uid=info.gid=info.mtime=0;info.uname=info.gname='root';return info
archive=OUT/'modules-x710.tar.gz'
with archive.open('wb') as raw:
 with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=3) as gz:
  with tarfile.open(fileobj=gz,mode='w') as t:t.add(module_dir,arcname=release,filter=normalized)
if archived(archive)!=new:raise ValueError('archive contents differ')
# Reuse qualified ELF parsers only, not native-profile acceptance assumptions.
p=ROOT/'reference/charging/x710-pack-current/qualify.py'
ns={'struct':struct};parsed=ast.parse(p.read_text())
helpers=[n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name in ('sections','elf_layout','semantic_symbols')]
exec(compile(ast.Module(body=helpers,type_ignores=[]),str(p),'exec'),ns)
changes={}
for n in new:
 if old[n]==new[n]:continue
 if not n.endswith('.ko'):raise ValueError('builtin/index metadata changed: '+n)
 a,b=ns['sections'](old[n]),ns['sections'](new[n]);la,_,_=ns['elf_layout'](old[n]);lb,_,_=ns['elf_layout'](new[n])
 allocated={k for k,e in la.items() if e[2]&2}|{k for k,e in lb.items() if e[2]&2}
 exceptions={'.BTF','.note.gnu.build-id'}
 bad=[k for k in allocated-exceptions if k not in la or k not in lb or a[k]!=b[k] or tuple(la[k][i] for i in (1,2,5,8))!=tuple(lb[k][i] for i in (1,2,5,8))]
 if bad:raise ValueError('module runtime bytes/shape changed: '+n+str(bad))
 sa,sb=ns['semantic_symbols'](old[n]),ns['semantic_symbols'](new[n])
 if len(sa)!=len(sb):raise ValueError('module symbol count')
 for x,y in zip(sa,sb):
  if x!=y and (x[:4]!=y[:4] or x[5]!=y[5] or x[3]!='.debug_str'):raise ValueError('module runtime symbol changed')
 sections=[k for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)]
 if set(sections)-{'.BTF','.note.gnu.build-id','.debug_str','.rela.debug_info','.symtab'}:raise ValueError('unexplained module section change')
 # Same cache path should keep original debug directory strings.
 if set(a['.debug_str'].split(b'\0'))!=set(b['.debug_str'].split(b'\0')):raise ValueError('module debug string drift')
 changes[n]=sections
symbols=subprocess.check_output(['llvm-nm','--defined-only',str(BUILD/'vmlinux')],text=True)
forbidden=['x710_charge_controller_request','x710_charge_controller_cancel','x710_charge_request_observation','sm5440_native_control']
if any(any(line.endswith(' '+name) for line in symbols.splitlines()) for name in forbidden):raise ValueError('native/active helper linked')
required=['sm5714_battery_set_pd_contract','sm5714_battery_set_typec_charge','sm5440_probe']
if not all(any(line.endswith(' '+name) for line in symbols.splitlines()) for name in required):raise ValueError('ordinary provider missing')
artifacts={n:{'path':str((OUT/n).relative_to(ROOT)),'bytes':(OUT/n).stat().st_size,'sha256':sha(OUT/n)} for n in ['Image.gz','sm8550-samsung-gts9wifi.dtb','config','kernel-notes.bin','modules-x710.tar.gz','kernel.release']}
summary={'verdict':'OFFLINE_ORDINARY_PC_BUDGET_PASS','full_port_verdict':'NOT_READY','profile':'sm5440-passive','base_revision':inputs['base_revision'],'profile_gate':gated,'config_delta_from_accepted311':delta,'unexpected_config_delta':{},'DTB_delta':[],'compiled_sources':compiled,'protected_source_count':len(inputs['protected_sources']),'preserved_formal_artifact_count':len(inputs['formal_artifacts']),'module_file_count':181,'module_runtime_unchanged':True,'module_changes':changes,'native_symbols_absent':forbidden,'artifacts':artifacts,'device_commands_executed':False,'physical_executed':False,'pump_ON':False,'PPS_requested':False,'source_revision':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'upstream_revision':subprocess.check_output(['git','-C',str(TREE),'rev-parse','HEAD'],text=True).strip()}
(R/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('profile_gate','module_changes','compiled_sources','artifacts')},indent=2))
