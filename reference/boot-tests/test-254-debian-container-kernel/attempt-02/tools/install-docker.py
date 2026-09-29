import sys,json,subprocess,time,datetime
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()));import production_reboot_stability as p
A=Path('reference/boot-tests/test-254-debian-container-kernel/attempt-02');r=p.Recorder(A/'docker-install')
out=r.adb('existing-docker-state','test ! -f /etc/docker/daemon.json; test ! -d /var/lib/docker; command -v docker || true; iptables --version 2>/dev/null || true; ip -br addr; ip route')[0]
assert not any(x.startswith('/usr/bin/docker') for x in out.splitlines())
script='set -eu; export DEBIAN_FRONTEND=noninteractive; apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 update; apt-get -y --no-install-recommends -o Acquire::Retries=1 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 install docker.io docker-cli iptables curl uidmap ipvsadm'
argv=[p.ADB,'-s',p.SERIAL,'shell',script];started=p.now();start=time.monotonic()
with (r.folder/'apt-install.txt').open('wb') as f,(r.folder/'apt-install.stderr').open('wb') as e:
    proc=subprocess.Popen(argv,stdout=f,stderr=e)
    while proc.poll() is None:
        if time.monotonic()-start>360:proc.terminate();raise RuntimeError('apt outer timeout; preserve raw state')
        time.sleep(2)
status=proc.returncode;p.write_json(r.folder/'apt-install.command.json',dict(argv=argv,started_utc=started,ended_utc=p.now(),status=status,elapsed_seconds=time.monotonic()-start))
assert status==0,(status,(r.folder/'apt-install.stderr').read_text()[-1200:])
out=r.adb('installed-versions','dpkg-query -W docker.io docker-cli containerd runc iptables curl uidmap ipvsadm; docker version; iptables --version; update-alternatives --query iptables; systemctl is-active docker containerd; systemctl --failed --no-legend --plain',30)[0];print(out[:4000],flush=True)
r.adb('packages-after','dpkg-query -W',25)
r.adb('daemon-journal','journalctl -b -u docker -u containerd --no-pager -o short-monotonic',30)
p.write_json(r.folder/'summary.json',dict(verdict='installed',explicit_packages=['docker.io','docker-cli','iptables','curl','uidmap','ipvsadm'],docker_cli_reason='CLI is a separately recommended Debian package, required for requested docker commands; other recommendations not installed',upgrades=0,hardware_or_usb_configs_changed=False))
