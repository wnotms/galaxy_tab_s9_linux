"""Capture one owner-operated cable cycle; no device/host state mutations."""
from pathlib import Path
import sys,time,json,datetime
sys.path.insert(0,'scripts');import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05';base=p.baseline();root=Path('reference/boot-tests/test-253-adbd-usb-reconnect/attempt-03');cycle=sys.argv[1];r=p.Recorder(root/cycle);boot='461c1408e42643afae5b48162771d077';start=time.monotonic();off=None;off_last=None;seen=0
try:
 for i in range(1,700):
  raw,_=r.command(f'poll-{i:03}-wifi',['env','GTS9_DEVICE=10.191.121.29',p.SSH,'set -eu; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/class/udc/a600000.usb/state; systemctl show -p MainPID --value gts9-adbd.service; cat /sys/class/power_supply/sm5714-usb/uevent'],timeout=12)
  rows=raw.splitlines();assert p.evidence.canonical_boot_id(rows[0])==boot and rows[3]=='834';up=float(rows[1].split()[0]);configured=rows[2]=='configured';online='POWER_SUPPLY_ONLINE=1' in rows
  if not configured and not online:
   off=up if off is None else off;off_last=up;seen+=1
  if i%5==1 or (off is not None and configured):
   r.host_adb(f'poll-{i:03}-adb','devices','-l',required=False)
  print(json.dumps(dict(poll=i,uptime=up,configured=configured,usb_online=online,unplug_observed=off is not None)),flush=True)
  if off is not None and configured and online:
   # Conservative lower bound from observed samples (owner waits>=15s).
   assert off_last-off>=10, 'physical unplug interval not established'
   reconnect_mark=time.monotonic();last_off_mark=reconnect_mark-2
   for attempt in range(1,25):
    native,rc=r.host_adb(f'reconnect-native-{attempt:02}','-s',p.SERIAL,'shell','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime',timeout=5,required=False)
    elapsed=time.monotonic()-last_off_mark
    if rc==0:
     assert p.evidence.canonical_boot_id(native.splitlines()[0])==boot
     assert elapsed<=60
     break
    assert elapsed<60, 'native USB recovery deadline exceeded';time.sleep(1)
   else:raise RuntimeError('native recovery not established')
   kernel,_=r.command('kernel-journal-json',['env','GTS9_DEVICE=10.191.121.29',p.SSH,'journalctl -k -b --no-pager -o json'],timeout=30);scan=p.inspect(kernel,boot,base,up);assert not scan['fault_counts'] and not scan['suspects'];p.write_json(r.folder/'kernel-scan.json',scan)
   r.command('adbd-journal-json',['env','GTS9_DEVICE=10.191.121.29',p.SSH,'journalctl -b -u gts9-adbd --no-pager -o json'],timeout=30)
   pnp,_=r.ps('windows-pnp-after',p.PS_USB,timeout=30);assert not p.has_code43(pnp)
   banner,_=r.ps('windows-ncm-after',p.PS_NCM_BOUND_BANNER,timeout=30);assert p.bound_banner_ok(banner),banner
   text,_=r.ssh('ncm-ssh-after','cat /proc/sys/kernel/random/boot_id',timeout=18);assert p.evidence.canonical_boot_id(text.strip())==boot
   p.write_json(r.folder/'recovery.json',dict(verdict='recovered-awaiting-150s-window',boot_id=boot,off_first_uptime=off,off_last_uptime=off_last,observed_unplug_lower_bound_seconds=off_last-off,configured_uptime=up,native_recovery_seconds_after_detection=elapsed,native_attempts=attempt,wifi_ssh_continuous=True,ncm_ssh_recovered=True,device_daemon_pid=834,host_server_restarts=0,kernel_fault_counts={}))
   print('cycle recovered; requires separate150s observation',flush=True);break
  if time.monotonic()-start>=900:
   if off is not None:raise RuntimeError('cable did not return within owner-action capture')
   p.write_json(r.folder/'pending.json',dict(verdict='awaiting-owner-action',physical_cycle_observed=False));break
  time.sleep(1)
except Exception as exc:
 p.write_json(r.folder/'failure.json',dict(verdict='stopped',error=repr(exc),unplug_observed=off is not None));raise
