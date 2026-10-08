#!/usr/bin/env python3
"""Freeze Test348 offline inputs; no transport, build, staging or device action."""
from pathlib import Path
import hashlib,importlib.util,json,types
ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,d:p.write_text(json.dumps(d,indent=2)+'\n')
old=json.loads((R.parent/'test-347-confirmed-c1-five-minute/INPUTS.json').read_text())
protected=('kernel/drivers/sm5440-fedora.c','kernel/drivers/sm5714-battery.c','kernel/drivers/sm5714_usbpd.c','kernel/drivers/sm5714-stage2.h','kernel/config/gts9wifi-mainline.fragment','kernel/dts/sm8550-samsung-gts9wifi.dts')
qpath=ROOT/'reference/charging/test347-twenty-minute-followup/summary.json';q=json.loads(qpath.read_text())
if q['verdict']!='OFFLINE_TWENTY_MINUTE_DURATION_PASS':raise ValueError('qualified1200s candidate required')
for name in protected:
    expected=q['compiled_sources']['power/supply/sm5440-fedora.c'] if name=='kernel/drivers/sm5440-fedora.c' else old[name]
    if sha(ROOT/name)!=expected:raise ValueError('qualified/protected input drift: '+name)
write(R/'qualification-reference.json',dict(source_revision=q['source_revision'],offline_reference=str(qpath.relative_to(ROOT)),qualification_sha256=sha(qpath),build_reused=True,kernel_rebuilt=False,hardware_setpoint_ma=1700,PPS_cap_ma=1800,raw_stop_cap_ua=1800000,refresh_reserve_ms=2000,pump_window_ms=1200000))
spec=importlib.util.spec_from_file_location('freeze348_flow',R/'host_flow.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
paths=set();pending=[f];seen=set()
while pending:
    m=pending.pop()
    if id(m) in seen:continue
    seen.add(id(m));name=getattr(m,'__file__',None)
    if not name:continue
    p=Path(name).resolve()
    if not p.is_relative_to(ROOT):continue
    paths.add(p);pending.extend(v for v in vars(m).values() if isinstance(v,types.ModuleType))
paths.update(R/name for name in ('registration.json','PACKAGE.json','guard.py','observe-post-return.py','operations.py','module-swap.sh','mount-debian.sh','read-pump.py','freeze_inputs.py','build_package.py','runtime-commands.json','staged-files.json','qualification-reference.json','retention-check.json','candidate-modules.sha256','rollback-modules.sha256'))
paths.update(ROOT/name for name in (*protected,'scripts/windows_ssh_transport.py','scripts/charging_wifi_discovery.py','scripts/ordinary_charge_window.py','scripts/sm5440_bounded_evidence.py','tests/test_sm5440_twenty_minute_deployment.py','tests/test_sm5440_duration_evidence.py','tests/test_windows_ssh_transport.py','reference/boot-tests/test-326-fixed9-native-dispatch/final-acceptance/kernel-json.txt'))
write(R/'INPUTS.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)})
scope=json.loads((R/'execution-scope.json').read_text());scope['registration_sha256']=sha(R/'INPUTS.json');write(R/'execution-scope.json',scope)
write(R/'EXECUTION_INPUTS.json',{str((R/name).relative_to(ROOT)):sha(R/name) for name in ('README.md','AUTHORIZATION.md','execution-scope.json','staged-files.json')})
print('Frozen',len(paths),'inputs; execution authorization:',scope['execution_authorized'])
