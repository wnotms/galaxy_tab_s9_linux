#!/usr/bin/env python3
"""One SSC discovery scope; exact reused native kernel, bounded SSH, no PPS."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import shlex
import sys
import time

ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).resolve().parent


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


base=load('ssc365_early_boot',R.parent/'test-364-early-adsp-socinfo/host_flow.py')
ready=load('ssc365_ssh_admission',ROOT/'userspace/sensors/ssh_readiness.py')
p=base.p
PLAN=json.loads((R/'registration.json').read_text())
PACKAGE=json.loads((R/'PACKAGE.json').read_text())
base.R=R;base.PLAN=PLAN;base.PACKAGE=PACKAGE
base.LOCAL=Path('/mnt/d/android/gts9-active/gts9-test365');base.STAGE='D:/android/gts9-active/gts9-test365';base.TMP='/tmp/gts9-test365'
base.CAPTURE='python3 -c '+shlex.quote((R/'capture.py').read_text())


def wifi(rec,name,d):
    trust=Path(PLAN['known_hosts'])
    if trust.is_symlink() or trust.read_text()!=PLAN['alias']+' '+PLAN['host_ed25519_key']+'\n':raise ValueError('SSH trust changed')
    addresses=re.findall(r'\bwlp1s0\s+inet\s+(\d+\.\d+\.\d+\.\d+)/',d['network'])
    if len(addresses)!=1:raise ValueError('WiFi address not unique')
    phase='candidate' if d['config_sha256']==PLAN['candidate_config_sha256'] else 'baseline'
    counters=dict(device=0,probe=0)
    def check(remaining):
        counters['device']+=1
        raw,_=rec.adb(name+'-device-%02d'%counters['device'],base.CAPTURE,timeout=min(8,remaining))
        packet=json.loads(raw);base.identity(packet,phase,d['boot_id'].replace('-',''))
        if phase=='candidate':base.native_gate(packet)
        return packet['boot_id']
    def probe(remaining):
        counters['probe']+=1;n=name+'-probe-%02d'%counters['probe']
        argv=base.ssh_argv(PLAN['key'],trust,PLAN['alias'],addresses[0],'cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id',transport=PLAN['ssh_transport'],windows_python=PLAN['windows_python'])
        # Distinguish Windows process startup from the former fragile3s deadline.
        argv=[x.replace('ConnectTimeout=3','ConnectTimeout=5') for x in argv]
        raw,status=rec.command(n,argv,timeout=min(12,remaining),required=False)
        return dict(stdout=raw,stderr=(rec.folder/(n+'.stderr')).read_text(),status=status)
    try:
        result=ready.admit(probe,check,machine_id=PLAN['machine_id'],boot_id=d['boot_id'],seconds=PLAN['ssh_readiness_seconds'],max_attempts=PLAN['ssh_max_attempts'])
    except ready.ReadinessError as exc:
        base.write(rec.folder/(name+'-admission.json'),exc.summary);raise
    base.write(rec.folder/(name+'-admission.json'),result)
    return addresses[0]


base.wifi=wifi


def stage():
    result=base.stage()
    sources={n:R/n for n in ('runtime.py','runtime-packages.json','runtime-overrides.json','capture.py')}
    sources['map-socinfo.py']=ROOT/'userspace/sensors/map-socinfo.py'
    for row in json.loads((R/'runtime-packages.json').read_text()):sources[row['filename']]=ROOT/row['path']
    import shutil
    rows=base.read(R/'staged-files.json')
    for n,source in sources.items():
        target=base.LOCAL/n
        if target.exists() and base.sha(target)!=base.sha(source):raise ValueError('stage duplicate')
        shutil.copyfile(source,target);rows[n]=dict(bytes=source.stat().st_size,sha256=base.sha(source))
    base.write(R/'staged-files.json',rows)
    return dict(result,files=len(rows))


def sample(raw):
    rows=re.findall(r'Accelerometer sensor measurement: X=([^\s]+) Y=([^\s]+) Z=([^\s]+) m/s²',raw)
    if not rows:return None
    values=tuple(float(x) for x in rows[-1])
    if not all(math.isfinite(x) for x in values) or not 1<=math.sqrt(sum(x*x for x in values))<=40:
        raise ValueError('invalid accelerometer measurement')
    return dict(x=values[0],y=values[1],z=values[2],unit='m/s²')


def runtime(rec,mode,boot):
    name='runtime-'+mode
    if mode=='prepare':
        plan=dict(PLAN,boot_id=boot)
        rec.adb('live-runtime-plan','python3 -c '+shlex.quote('from pathlib import Path; p=Path('+repr(base.TMP+'/live-plan.json')+'); p.write_text('+repr(json.dumps(plan))+')'),timeout=8)
    command='python3 '+base.TMP+'/runtime.py '+mode+' --incoming '+base.TMP+' --plan '+base.TMP+'/live-plan.json'
    raw,_=rec.adb(name,command,timeout=70 if mode=='prepare' else 20)
    value=json.loads(raw);base.write(rec.folder/(name+'.json'),value);return value


def collect_runtime(rec):
    rec.adb('unit-journal','journalctl -b -u hexagonrpcd-adsp-rootpd -u hexagonrpcd-adsp-sensorspd -u iio-sensor-proxy -o json --no-pager',timeout=15,required=False)
    rec.adb('unit-state','systemctl status --no-pager -l hexagonrpcd-adsp-rootpd hexagonrpcd-adsp-sensorspd iio-sensor-proxy; echo @@fastrpc; ls -l /dev/fastrpc*; echo @@native-mapper; ls -l /sys/bus/platform/drivers/qcom-pd-mapper; echo @@registry; ls -la /usr/share/qcom/sm8550/Samsung/gts9wifi/socinfo /usr/share/qcom/sm8550/Samsung/gts9wifi/sensors',timeout=12,required=False)


def discover():
    state=base.read(R/'mutation-state.json')
    if state['phase']!='accepted-candidate-kept-text' or (R/'runtime-discovery').exists():raise ValueError('one discovery only from accepted candidate')
    # Transfer was in recovery /tmp, so boot discarded it. Re-push only small
    # runtime tools/packages, not another kernel/bundle or module replacement.
    p.SERIAL='gts9wifi-0001';rec=p.Recorder(R/'runtime-discovery')
    boot=state['boot_id'];d=base.snapshot(rec,'boundary','candidate',boot);base.native_gate(d);wifi(rec,'wifi',d)
    rows=base.verify_stage();wanted=['runtime.py','capture.py','map-socinfo.py','runtime-packages.json','runtime-overrides.json']+[x['filename'] for x in base.read(R/'runtime-packages.json')]
    rec.adb('incoming-dir','mkdir '+base.TMP,timeout=8)
    for i,n in enumerate(wanted):
        rec.host_adb('push-%02d'%i,'-s',p.SERIAL,'push',base.STAGE+'/'+n,base.TMP+'/'+n,timeout=12)
    checks=''.join(rows[n]['sha256']+'  '+base.TMP+'/'+n+'\n' for n in wanted)
    rec.adb('incoming-hashes','printf %s '+shlex.quote(checks)+' | sha256sum -c -',timeout=8)
    try:
        runtime(rec,'prepare',d['boot_id']);runtime(rec,'start',d['boot_id'])
        started=time.monotonic();index=0;measurement=None
        while time.monotonic()-started<PLAN['ssc_readiness_seconds']:
            current=base.snapshot(rec,'ssc-health-%02d'%index,'candidate',boot);base.native_gate(current)
            remaining=PLAN['ssc_readiness_seconds']-(time.monotonic()-started)
            if remaining<=0:break
            raw,status=rec.adb('accelerometer-%02d'%index,'timeout '+str(min(4,remaining))+' ssccli --sensor accelerometer --timeout 2',timeout=min(6,remaining+0.2),required=False)
            measurement=sample(raw)
            if measurement and time.monotonic()-started<PLAN['ssc_readiness_seconds']:break
            if time.monotonic()-started>=PLAN['ssc_readiness_seconds']:
                measurement=None;break
            # Process timeout is a pending client-discovery probe, not a service
            # restart. Actual failed daemon stops immediately rather than retry.
            states,_=rec.adb('ssc-units-%02d'%index,'systemctl is-active hexagonrpcd-adsp-rootpd hexagonrpcd-adsp-sensorspd',timeout=5)
            if states.splitlines()!=['active','active']:raise ValueError('SSC daemon not active')
            index+=1;time.sleep(2)
        if measurement is None:raise TimeoutError('bounded SSC accelerometer discovery')
        base.write(rec.folder/'accelerometer-proof.json',dict(boot_id=d['boot_id'],measurement=measurement,seconds=time.monotonic()-started,probes=index+1))
        runtime(rec,'start-proxy',d['boot_id'])
        proxy_start=time.monotonic();i=0
        while time.monotonic()-proxy_start<15:
            raw,status=rec.adb('dbus-%02d'%i,'busctl get-property net.hadess.SensorProxy /net/hadess/SensorProxy net.hadess.SensorProxy HasAccelerometer',timeout=5,required=False)
            if status==0 and raw.strip()=='b true':break
            i+=1;time.sleep(2)
        else:raise TimeoutError('sensor proxy did not expose accelerometer')
        collect_runtime(rec)
        current=base.snapshot(rec,'final-identity','candidate',boot);base.native_gate(current);wifi(rec,'final-wifi',current)
        faults=base.scan(rec,boot,current['uptime'])
        result=dict(verdict='SSC_ACCELEROMETER_DBUS_BACKEND_PASS',boot_id=d['boot_id'],measurement=measurement,HasAccelerometer=True,
                    ADB=True,device_NCM=True,authenticated_WiFi=True,kernel_fault_counts=faults['fault_counts'],PPS=False,pump_ON=False,
                    physical_rotation_tested=False,desktop_started=False,packages_retained=True)
        base.write(rec.folder/'summary.json',result)
        state.update(phase='SSC-backend-accepted-candidate-kept-text');base.write(R/'mutation-state.json',state)
        return result
    except Exception as exc:
        base.write(R/'first-runtime-failure.json',dict(error=str(exc),stopped=True,no_retry=True))
        collect_runtime(rec)
        # Remove gate/stop owned daemons before hardware rollback. If a command
        # cannot return, leave explicit recovery evidence; never launch twice.
        try:runtime(rec,'deactivate',d['boot_id'])
        except Exception as cleanup:base.write(rec.folder/'runtime-cleanup-error.json',dict(error=str(cleanup)))
        try:base.restore()
        except Exception as cleanup:base.write(R/'recovery-required.json',dict(error=str(cleanup),manual_TWRP_required=True))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('verify','stage','preflight','install','discover','restore'))
    a=parser.parse_args()
    if a.mode=='stage':result=stage()
    elif a.mode=='verify':result=base.verify_inputs()
    elif a.mode=='preflight':result=base.preflight()
    elif a.mode=='install':result=base.install()
    elif a.mode=='discover':result=discover()
    else:result=base.restore()
    print(json.dumps(result,indent=2))
