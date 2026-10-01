#!/usr/bin/env python3
"""150s read-only discharge endpoint after owner confirms unplug; no retry/flash."""
import json,re,shlex,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e
from sample_gate import properties,validate_sample,gauge_entry_hint
A=Path(__file__).resolve().parent

def require(ok,reason):
    if not ok:raise p.CaptureError(reason)

def main():
    require((A/'OWNER_UNPLUG.json').exists(),'owner unplug confirmation required; no human-wait timer')
    require(not (A/'battery-only').exists(),'never overwrite/retry physical window')
    plan=json.loads((A/'registration.json').read_text());boot=plan['boot_id'];wifi=plan['wifi']
    r=p.Recorder(A/'battery-only');samples=[];cursor=None
    def ssh(name,command,timeout=20,required=True):
        return r.command(name,['env','GTS9_DEVICE='+wifi,p.SSH,command],timeout,required)[0]
    known_path=ROOT/'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
    known={x['MESSAGE'] for x in map(json.loads,known_path.read_text().splitlines()) if int(x.get('PRIORITY',7))<=3}
    def journal(raw,name,uptime,first=False):
        nonlocal cursor
        lines=raw.splitlines();data='\n'.join(x for x in lines if x.startswith('{'))
        require(bool(data) or not first,'empty full journal')
        if data:
            scan=e.inspect_journal(data,boot,known,require_start=first,accepted_startup_variants=True,
                startup_iova_range=(0xb8000000,0xbab00000),accepted_qca_cycles=True,observed_uptime=uptime)
            p.write_json(r.folder/(name+'-scan.json'),scan)
            require(not scan['fault_counts'] and not scan['suspects'],'kernel/CPU fault or suspect')
            if not first:
                for row in map(json.loads,data.splitlines()):
                    msg=row['MESSAGE']
                    require(not ('sm5440-passive' in msg and any(x in msg for x in ['fault bitmap=','ADC fault','confirmation failed'])), 'new SM5440 fault event')
        elif not first:
            require(all(not x.strip() or x=='-- No entries --' or x.startswith('-- cursor: ') for x in lines),'malformed incremental journal')
        rows=[x[len('-- cursor: '):] for x in lines if x.startswith('-- cursor: ')]
        if rows:
            require(len(rows)==1 and bool(rows[0]),'ambiguous cursor');cursor=rows[0]
        require(cursor is not None,'missing journal cursor')
    try:
        identity=ssh('identity','set -e; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes').splitlines()
        require(e.canonical_boot_id(identity[0])==boot,'boot changed')
        require(identity[2].split()[0]==plan['config_sha256'] and identity[3].split()[0]==plan['notes_sha256'],'Test263 identity changed')
        raw=ssh('initial-kernel-json','journalctl -b -k --no-pager -o json --show-cursor',25)
        journal(raw,'initial',float(identity[1].split()[0]),True)
        original=json.loads((A/'preflight/summary.json').read_text())['cached_snapshot']
        initial_temperature=None;start=time.monotonic()
        while True:
            n=len(samples)
            raw=ssh(f'sample-{n:03}','set -e; echo @@boot; cat /proc/sys/kernel/random/boot_id; echo @@uptime; cat /proc/uptime; '
                'echo @@battery; cat /sys/class/power_supply/sm5714-battery/uevent; echo @@usb; cat /sys/class/power_supply/sm5714-usb/uevent; '
                'echo @@snapshot; cat /sys/kernel/debug/sm5440-0-0063/snapshot; echo @@failed; systemctl --failed --no-legend --plain --no-pager; '
                'echo @@kernel; journalctl -b -k --no-pager -o json --show-cursor --after-cursor='+shlex.quote(cursor))
            pieces=re.split(r'^@@([^\n]+)\n',raw,flags=re.M);sec=dict(zip(pieces[1::2],pieces[2::2]))
            require(e.canonical_boot_id(sec['boot'])==boot,'unexpected reboot')
            b,u=properties(sec['battery']),properties(sec['usb']);s=dict(x.split('=',1) for x in sec['snapshot'].splitlines())
            if initial_temperature is None:
                initial_temperature=int(b['POWER_SUPPLY_TEMP']);require(200<=initial_temperature<380,'initial temperature')
            validate_sample(b,u,s,initial_temperature)
            for key,value in original.items():
                if key not in ('capture_jiffies','sample_age_ms','sample_fresh'):
                    require(s.get(key)==value,'cached monitor unexpectedly changed: '+key)
            require(not sec['failed'].strip(),'new failed systemd unit')
            journal(sec['kernel'],f'sample-{n:03}',float(sec['uptime'].split()[0]))
            elapsed=time.monotonic()-start
            samples.append({'elapsed_s':round(elapsed,3),'device_uptime_s':float(sec['uptime'].split()[0]),'battery':b,'usb':u,'cached_snapshot':s})
            if n%6==0:print('Discharge',round(elapsed,1),'s;',b['POWER_SUPPLY_VOLTAGE_NOW'],'uV;',b['POWER_SUPPLY_CURRENT_NOW'],'uA;',int(b['POWER_SUPPLY_TEMP'])/10,'C',flush=True)
            if elapsed>=150:break
            time.sleep(min(5,150-elapsed))
        raw=ssh('final-kernel-json','journalctl -b -k --no-pager -o json --show-cursor',25)
        journal(raw,'final',samples[-1]['device_uptime_s'],True)
        ssh('final-kernel-journal','journalctl -b -k --no-pager -o short-monotonic',25)
        final=ssh('final-identity','cat /proc/sys/kernel/random/boot_id; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes').splitlines()
        require(e.canonical_boot_id(final[0])==boot and final[1].split()[0]==plan['config_sha256'] and final[2].split()[0]==plan['notes_sha256'],'final identity changed')
        p.write_json(r.folder/'summary.json',{'verdict':'BATTERY_ONLY_WINDOW_COMPLETED_MONITOR_UNQUALIFIED','boot_id':boot,'observation_seconds':samples[-1]['elapsed_s'],'samples':samples,
            'gauge_entry_hint':gauge_entry_hint(samples[-1]['battery']),'fresh_SM5440_ADC_available':False,'passive_monitor_acceptance':False,
            'old_fault_cleared':False,'PPS':False,'pump_ON':False,'reboot_or_flash':False,'physical_unplug_transition_latency_measured':False,
            'next_step':'Do not restart/flash on stale ADC; full-pack monitor audit or a separately registered fresh in-range boot still required.'})
        print('Battery-only window complete; SM5440 remains unqualified; entry hint:',gauge_entry_hint(samples[-1]['battery']),flush=True)
    except Exception as exc:
        ssh('first-failure-kernel-json','journalctl -b -k --no-pager -o json',25,False)
        p.write_json(r.folder/'summary.json',{'verdict':'STOP_BATTERY_ONLY_WINDOW','error':str(exc),'boot_id':boot,'samples':samples,'PPS':False,'pump_ON':False,'reboot_or_flash':False})
        raise
if __name__=='__main__':main()
