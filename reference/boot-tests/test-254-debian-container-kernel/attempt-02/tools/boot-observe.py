import sys,json,time,re,subprocess
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()));import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05';base=p.baseline()
A=Path('reference/boot-tests/test-254-debian-container-kernel/attempt-02');reg=json.loads((A/'registration.json').read_text());r=p.Recorder(A/'boot-observation')
start=time.monotonic();first=None
for n in range(60):
    raw,code=r.adb('wait-native-%02d'%n,'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; ip -4 -o addr show wlp1s0',timeout=5,required=False)
    if code==0 and len(raw.splitlines())>=3:
        lines=raw.splitlines();boot=p.evidence.canonical_boot_id(lines[0]);assert boot!=reg['preflight_boot_id'];ip=re.search(r'inet ([0-9.]+)/',raw).group(1);first=dict(boot_id=boot,wifi_address=ip,first_uptime_seconds=float(lines[1].split()[0]),host_seconds_to_first=time.monotonic()-start);p.write_json(A/'boot-observation/first-boot.json',first);print('CANDIDATE BOOT',first,flush=True);break
    time.sleep(2)
else:raise RuntimeError('no attributed native boot within bounded wait')
identity=r.adb('early-kernel-identity','zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes; systemctl --failed --no-legend --plain')[0].splitlines()
assert identity[0].split()[0]==reg['candidate_config_sha256'] and identity[1].split()[0]==reg['candidate_notes_sha256'] and len(identity)==2,identity
raw=r.adb('boot-history','journalctl --list-boots --no-pager',25)[0];assert p.evidence.boot_list(raw)[-2:]==[reg['preflight_boot_id'],boot]
obs=time.monotonic();polls=[]
for n in range(100):
    raw,_=r.adb('native-sample-%02d'%n,'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/class/power_supply/sm5714-battery/health; cat /sys/class/power_supply/sm5714-battery/temp; cat /sys/class/power_supply/sm5714-battery/voltage_now; systemctl --failed --no-legend --plain',timeout=12)
    lines=raw.splitlines();assert len(lines)==5 and p.evidence.canonical_boot_id(lines[0])==boot and lines[2]=='Good' and 100<=int(lines[3])<420 and int(lines[4])<=4440000,raw
    for channel,argv in [('ncm',[p.SSH]),('wifi',['env','GTS9_DEVICE='+ip,p.SSH])]:
        out,status=r.command(channel+'-sample-%02d'%n,argv+['cat /proc/sys/kernel/random/boot_id'],timeout=12);assert p.evidence.canonical_boot_id(out)==boot
    raw,_=r.adb('kernel-json-%02d'%n,'journalctl -b -k --no-pager -o json',timeout=30);scan=p.inspect(raw,boot,base,float(lines[1].split()[0]));assert not scan['fault_counts'] and not scan['suspects'],scan
    elapsed=time.monotonic()-obs;polls.append(dict(poll=n,elapsed_seconds=elapsed,uptime=float(lines[1].split()[0]),temperature_deciC=int(lines[3]),voltage_uv=int(lines[4])))
    print('RESPONSIVE',round(elapsed,1),'seconds',flush=True)
    if elapsed>=150:break
    time.sleep(10)
else:raise RuntimeError('observation did not complete')
r.adb('kernel-journal','journalctl -b -k --no-pager -o short-monotonic',30)
p.write_json(A/'boot-observation/summary.json',dict(verdict='passed bounded boot responsiveness',boot_id=boot,wifi_address=ip,observation_seconds=elapsed,polls=polls,ADB=True,NCM_SSH=True,WiFi_SSH=True,kernel_scan=scan,boot_attribution_unique=True))
