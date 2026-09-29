import sys,json,time,subprocess
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()));import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05';base=p.baseline()
A=Path('reference/boot-tests/test-254-debian-container-kernel/attempt-03');reg=json.loads((A/'registration.json').read_text())
class Guarded(p.Recorder):
    def command(self,name,argv,timeout=15,required=True):
        result=super().command(name,argv,timeout,required)
        if result[1]==0:
            raw,_=super().command(name+'-kernel-json',[p.ADB,'-s',p.SERIAL,'shell','journalctl -b -k --no-pager -o json'],30)
            scan=p.inspect(raw,reg['boot_id'],base)
            assert not scan['fault_counts'] and not scan['suspects'],scan
            raw,_=super().command(name+'-health',[p.ADB,'-s',p.SERIAL,'shell','cat /proc/sys/kernel/random/boot_id; cat /sys/class/power_supply/sm5714-battery/health; cat /sys/class/power_supply/sm5714-battery/temp; systemctl --failed --no-legend --plain'],15)
            lines=raw.splitlines();assert len(lines)==3 and p.evidence.canonical_boot_id(lines[0])==reg['boot_id'] and lines[1]=='Good' and 100<=int(lines[2])<420,raw
        return result
r=Guarded(A/'docker-acceptance')
info=r.adb('docker-info','docker info --format "{{json .}}"',30)[0];data=json.loads(info);assert data['CgroupVersion']=='2' and data['Driver']=='overlay2' and any('seccomp' in x for x in data['SecurityOptions']),data
r.adb('docker-info-text','docker info',30)
def stream(name,script,limit=150):
    argv=[p.ADB,'-s',p.SERIAL,'shell',script];start=time.monotonic();started=p.now()
    with (r.folder/(name+'.txt')).open('wb') as f,(r.folder/(name+'.stderr')).open('wb') as e:
        proc=subprocess.Popen(argv,stdout=f,stderr=e)
        while proc.poll() is None:
            if time.monotonic()-start>limit:proc.terminate();raise RuntimeError(name+' host limit; no later tests')
            time.sleep(2)
    p.write_json(r.folder/(name+'.command.json'),dict(argv=argv,started_utc=started,ended_utc=p.now(),status=proc.returncode,elapsed_seconds=time.monotonic()-start));assert proc.returncode==0,name
    print(name,'PASSED',time.monotonic()-start,flush=True)
r.adb('image-digests','docker image inspect hello-world debian:trixie-slim nginx:alpine alpine --format "{{json .RepoDigests}}"',25)
r.adb('hello-world','timeout 30 docker run --pull=never --rm hello-world',40)
r.adb('container-uname','timeout 30 docker run --pull=never --rm debian:trixie-slim uname -a',40)
r.adb('container-mqueue','timeout 30 docker run --pull=never --rm debian:trixie-slim sh -c "mount | grep mqueue"',40)
r.adb('container-limited-run','timeout 30 docker run --pull=never --rm --memory=256m --cpus=1 --pids-limit=64 debian:trixie-slim sh -c "echo container-ok"',40)
r.adb('resource-container-start','docker run --pull=never -d --rm --name gts9-test254-limits --memory=256m --cpus=1 --pids-limit=64 --cpuset-cpus=0 --device-read-bps /dev/mmcblk1:1mb --device-write-bps /dev/mmcblk1:1mb debian:trixie-slim sleep 180',30)
raw=r.adb('resource-controls',r'''set -eu
+pid=$(docker inspect --format '{{.State.Pid}}' gts9-test254-limits)
+cg=$(awk -F: '$1=="0" {print $3}' /proc/$pid/cgroup)
+echo "$cg"
+for n in cpu.max memory.max pids.max cpuset.cpus cpuset.cpus.effective io.max; do echo "$n"; cat "/sys/fs/cgroup$cg/$n"; done
+docker inspect gts9-test254-limits --format '{{json .HostConfig}}'
'''.replace('\n+','\n'),25)[0]
assert '100000 100000' in raw and '268435456' in raw and '\n64\n' in raw and 'rbps=1048576' in raw and 'wbps=1048576' in raw,raw
r.adb('resource-container-stop','docker stop gts9-test254-limits',20)
r.adb('dns','timeout 30 docker run --pull=never --rm debian:trixie-slim getent hosts deb.debian.org',40)
r.adb('ipv4-outbound','timeout 30 docker run --pull=never --rm alpine sh -c "wget -T 15 -O /dev/null http://deb.debian.org/debian/README"',40)
r.adb('nginx-start','docker run --pull=never -d --rm --name gts9-test254-nginx -p 8080:80 nginx:alpine',30)
r.adb('published-http','curl --fail --max-time 10 http://127.0.0.1:8080/',20)
r.adb('network-inspect','docker inspect gts9-test254-nginx; docker network inspect bridge; ip -d link show docker0; iptables --version; ip6tables --version; iptables-save; ip6tables-save; nft list ruleset',30)
r.adb('nginx-stop','docker stop gts9-test254-nginx',20)
p.write_json(r.folder/'summary.json',dict(verdict='passed',cgroup_version=data['CgroupVersion'],storage=data['Driver'],seccomp=True,hello_world=True,container_mqueue=True,memory_cpu_pids_cpuset_io_controls=True,DNS=True,IPv4_outbound=True,bridge_NAT=True,published_http=True,rootless_daemon_tested=False))
print('DOCKER ACCEPTANCE PASSED',flush=True)
