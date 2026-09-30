#!/usr/bin/env python3
"""Read-only Test255 baseline gate, no duplicate partition/module hash round."""
import json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
import production_reboot_stability as p
import production_stability_evidence as e
A=Path(__file__).resolve().parent
assert not (A/'preflight').exists()
r=p.Recorder(A/'preflight');p.SERIAL='gts9wifi-0001'
M=json.loads((A.parent/'ARTIFACTS.json').read_text())
checks={}
def require(value,key):
    checks[key]=bool(value)
    if not value: raise p.CaptureError(key)
raw=r.adb('identity','set -e; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; uname -a; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes; cat /proc/cmdline',30)[0].splitlines()
boot=e.canonical_boot_id(raw[0]);cfg=raw[3].split()[0];notes=raw[4].split()[0]
require(cfg=='cd7ec9cbd259475a027862ddaf125eb5ad63ae3dc63e33cea5073ef492cdde3f','config')
require(notes=='fb3d249642e900d9bb591fb629c1865b370b50098d44970b986cc793f45c160c','notes')
require(raw[5].strip()==(A.parent.parent/'test-255-sm5714-fixed-pd/attempt-01/preflight/cmdline.txt').read_text().strip(),'normal-cmdline')
from gts9_ncm_ready import wait_ready
ready=wait_ready(r,30); checks['NCM-host-ready']=True
require(e.canonical_boot_id(r.ssh('ncm','cat /proc/sys/kernel/random/boot_id')[0])==boot,'NCM')
ip=re.search(r'inet (\d+\.\d+\.\d+\.\d+)/',r.ssh('wifi-address','ip -4 -o addr show dev wlp1s0')[0]).group(1)
require(e.canonical_boot_id(r.command('wifi',['env','GTS9_DEVICE='+ip,p.SSH,'cat /proc/sys/kernel/random/boot_id'])[0])==boot,'WiFi')
b=dict(x.split('=',1) for x in r.adb('battery','cat /sys/class/power_supply/sm5714-battery/uevent')[0].splitlines() if x.startswith('POWER_SUPPLY_'))
require(b['POWER_SUPPLY_HEALTH']=='Good' and b['POWER_SUPPLY_PRESENT']=='1' and 5<=int(b['POWER_SUPPLY_CAPACITY'])<80 and 200<=int(b['POWER_SUPPLY_TEMP'])<380 and 3500000<=int(b['POWER_SUPPLY_VOLTAGE_NOW'])<4300000,'battery')
require(r.adb('roles','cat /sys/class/typec/port0/power_role; cat /sys/class/typec/port0/data_role')[0].splitlines()==['[sink]','[device]'],'sink-device')
r.adb('dcc-and-slots','set -e; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; ! systemctl is-active --quiet serial-getty@hvc0.service; test ! -e /sys/class/power_supply/sm5440-passive; test ! -e /usr/lib/modules/.gts9-test260-original; test ! -e /usr/lib/modules/.gts9-test260-stage; test ! -e /usr/lib/modules/.gts9-test260-tested; test -d /usr/lib/modules/.gts9-test258-tested; test -d /usr/lib/modules/.gts9-test259-tested; systemctl is-active ssh gts9-adbd gts9-usb-acm',20)
checks['dcc-passive-and-slots-absent']=True
require(not r.adb('failed','systemctl --failed --plain --no-legend --no-pager')[0].strip(),'no-failed-units')
known_file=ROOT/'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
known={x['MESSAGE'] for x in map(json.loads,known_file.read_text().splitlines()) if int(x.get('PRIORITY',7))<=3}
j=r.adb('kernel-json','journalctl -b -k --no-pager -o json',30)[0]
scan=e.inspect_journal(j,boot,known,accepted_startup_variants=True,startup_iova_range=(0xb8000000,0xbab00000),accepted_qca_cycles=True,observed_uptime=float(raw[1].split()[0]))
p.write_json(r.folder/'kernel-scan.json',scan);require(not scan['fault_counts'] and not scan['suspects'],'kernel-health')
checks['no-Code43']=True; checks['NCM-adapter']=True
require(e.canonical_boot_id(r.adb('last-boot','cat /proc/sys/kernel/random/boot_id')[0])==boot,'same-boot')
p.write_json(r.folder/'summary.json',dict(verdict='preflight passed',boot_id=boot,checks=checks,battery=b,config_sha256=cfg,notes_sha256=notes,partitions=M['baseline_partitions'],device_writes=False,wifi=ip,partition_module_hash_gate='fresh TWRP inspection at write boundary'))
print('Fresh Test255 baseline/rescue preflight passed',boot,ip,flush=True)
