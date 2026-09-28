import sys,time,json,datetime,subprocess,re
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()))
import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05';base=p.baseline()
root=Path('reference/boot-tests/test-252-sm5714-stage1/attempt-01');phase=sys.argv[1]
accept=json.loads((root/'boot/acceptance/summary.json').read_text());boot=accept['boot_id'];wifi=accept['wifi_ip']
folder=root/phase;folder.mkdir(exist_ok=True);started=time.monotonic();window_start=None;samples=[]
window=150 if phase in ['battery-only','plug-out'] else 1200
script="set -e; echo __boot__; cat /proc/sys/kernel/random/boot_id; echo __uptime__; cat /proc/uptime; echo __battery__; cat /sys/class/power_supply/sm5714-battery/uevent; echo __usb__; cat /sys/class/power_supply/sm5714-usb/uevent; echo __failed__; systemctl --failed --no-legend --plain --no-pager; echo __journal__; journalctl -k -b --no-pager -o json"
try:
    for number in range(1,1000):
        stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic();r=subprocess.run(['env','GTS9_DEVICE='+wifi,'scripts/gts9-ssh.sh',script],capture_output=True,timeout=18)
        name=f'sample-{number:03d}';(folder/(name+'.txt')).write_bytes(r.stdout);(folder/(name+'.stderr')).write_bytes(r.stderr)
        meta=dict(utc=stamp,status=r.returncode,host_elapsed_s=round(time.monotonic()-started,3));p.write_json(folder/(name+'.command.json'),meta)
        if r.returncode!=0:raise RuntimeError('WiFi SSH/evidence collection failure')
        raw=r.stdout.decode();blocks={}
        for marker in ['boot','uptime','battery','usb','failed','journal']:
            pieces=raw.split('__'+marker+'__\n',1)
            if len(pieces)!=2:raise RuntimeError('missing '+marker+' marker')
            blocks[marker]=re.split(r'^__[a-z]+__\n',pieces[1],maxsplit=1,flags=re.M)[0].strip()
        if p.evidence.canonical_boot_id(blocks['boot'])!=boot:raise RuntimeError('unexpected reboot')
        if blocks['failed']:raise RuntimeError('systemd failed unit')
        props={k:v for text in [blocks['battery'],blocks['usb']] for line in text.splitlines() if '=' in line for k,v in [line.split('=',1)]}
        for key in ['HEALTH','TEMP','VOLTAGE_NOW','CURRENT_NOW','CAPACITY','ONLINE','STATUS','INPUT_CURRENT_LIMIT']:
            if 'POWER_SUPPLY_'+key not in props:raise RuntimeError('missing supply '+key)
        temp=int(props['POWER_SUPPLY_TEMP']);voltage=int(props['POWER_SUPPLY_VOLTAGE_NOW']);capacity=int(props['POWER_SUPPLY_CAPACITY']);online=int(props['POWER_SUPPLY_ONLINE']);current=int(props['POWER_SUPPLY_CURRENT_NOW'])
        if props['POWER_SUPPLY_HEALTH']!='Good' or not 100<=temp<420 or not 3400000<=voltage<=4440000 or not 0<=capacity<=100:raise RuntimeError('battery health/temperature/voltage/SOC stop gate')
        if samples and abs(capacity-samples[-1]['soc'])>3:raise RuntimeError('unexplained SOC jump')
        uptime=float(blocks['uptime'].split()[0]);scan=p.inspect(blocks['journal'],boot,base,uptime)
        if scan['fault_counts']:raise RuntimeError('CPU/kernel fault signature')
        gpu='adreno 3d00000.gpu: [drm:adreno_request_fw] *ERROR* failed to load a740_sqe.fw'
        unexpected=[s for s in scan['suspects'] if s['message']!=gpu]
        if unexpected:raise RuntimeError('new unclassified kernel error/warning: '+unexpected[0]['message'])
        if any(s['message']==gpu for s in scan['suspects']):
            rows=[json.loads(line) for line in blocks['journal'].splitlines()];indices=[i for i,row in enumerate(rows) if row['MESSAGE']==gpu]
            if len(indices)!=1 or rows[indices[0]-1]['MESSAGE']!='adreno 3d00000.gpu: Direct firmware load for qcom/a740_sqe.fw failed with error -2':raise RuntimeError('GPU error differs from registered known missing-file class')
        target=0 if phase in ['battery-only','plug-out'] else 1
        row=dict(utc=stamp,host_elapsed_s=meta['host_elapsed_s'],uptime_s=uptime,boot_id=boot,online=online,status=props['POWER_SUPPLY_STATUS'],health=props['POWER_SUPPLY_HEALTH'],temp_deciC=temp,voltage_uv=voltage,current_ua=current,soc=capacity,usb_type=props.get('POWER_SUPPLY_USB_TYPE'),input_limit_ua=int(props['POWER_SUPPLY_INPUT_CURRENT_LIMIT']),kernel_rows=scan['rows'],kernel_fault_counts=scan['fault_counts'])
        if online==target and window_start is None:window_start=t;print('OBSERVATION START '+json.dumps(row),flush=True)
        if window_start is not None:
            if online!=target:raise RuntimeError('unexpected attach/detach within registered observation')
            if target==0 and props['POWER_SUPPLY_STATUS']!='Discharging':raise RuntimeError('offline status is not Discharging')
            row['observation_s']=round(time.monotonic()-window_start,3)
        samples.append(row);p.write_json(folder/'samples.json',samples)
        p.write_json(folder/'progress.json',dict(phase=phase,state='observing' if window_start else 'waiting for physical transition',last=row))
        if window_start is not None and time.monotonic()-window_start>=window:
            p.write_json(folder/'summary.json',dict(verdict='bounded observation completed; acceptance requires cross-phase current/SOC review',phase=phase,boot_id=boot,window_s=round(time.monotonic()-window_start,3),samples=len(samples),first=samples[0],last=row))
            print('OBSERVATION COMPLETE '+json.dumps(row),flush=True);break
        if window_start is None and time.monotonic()-started>600:raise RuntimeError('physical transition wait expired; no observation started')
        time.sleep(max(0,10-(time.monotonic()-t)))
    else:raise RuntimeError('sample bound exceeded')
except Exception as e:
    p.write_json(folder/'summary.json',dict(verdict='stopped',phase=phase,reason=str(e),samples=len(samples),boot_id=boot));print('STOP '+str(e),flush=True);raise
