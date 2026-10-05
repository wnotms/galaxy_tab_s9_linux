#!/usr/bin/env python3
"""Registered one unchanged normal reboot before the candidate; no flash."""
import importlib.util,json,time
from pathlib import Path
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('pc322_host',R/'host_flow.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

def main():
    h.configure();h.verify_inputs(require_push=True)
    folder=R/'normal-reentry'
    if (folder/'reboot-requested.json').exists(): raise ValueError('one request only; no replay')
    rec=h.p.Recorder(folder)
    raw,_=rec.adb('before',h.PLAN['current_command'],timeout=15)
    sec=h.h.g.baseline.sections(raw);boot=sec['boot'].strip().replace('-','')
    if boot!=h.PLAN['normalization']['incoming_boot_id'].replace('-','') or sec['boot-end'].strip().replace('-','')!=boot: raise ValueError('incoming boot changed')
    if [x.split()[0] for x in sec['identity'].splitlines()]!=[h.PLAN['baseline_config_sha256'],h.PLAN['baseline_notes_sha256']]: raise ValueError('wrong incoming config/notes')
    h.gate.battery_entry(sec['battery']);h.gate.source_budget(sec['tcpm'])
    if sec['roles'].splitlines()!=['[sink]','[device]'] or sec['dcc'].strip()!='absent' or sec['failed'].strip() or sec['services'].splitlines()!=['active']*3: raise ValueError('incoming role/service/health')
    snap=h.gate.values(sec['snapshot'])
    if snap.get('pump_enable_supported')!='0' or snap.get('last_sample_error')!='0' or int(snap.get('sample_faults','-1'),0)!=0 or any(int(snap[k],0)&12 for k in ('sample_mode_before','sample_mode_after')): raise ValueError('incoming passive fault/not OFF')
    h.wifi_rescue(rec,sec,boot)
    before,_=rec.adb('boots-before','journalctl --list-boots --no-pager',timeout=20)
    journal,_=rec.adb('kernel-before','journalctl -k -b -o json --no-pager',timeout=15)
    h.old.scan_journal(journal,boot,float(sec['uptime'].split()[0]),snap)
    h.write(folder/'reboot-requested.json',dict(before_boot_id=boot,software_change=False,flash=False))
    rec.adb('normal-reboot','systemctl reboot',timeout=8,required=False)
    result,_=h.admission(folder/'after','baseline',boot,before)
    h.write(folder/'summary.json',dict(verdict='UNCHANGED_NORMAL_REENTRY_PASS',result=result))
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
