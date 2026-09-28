from pathlib import Path
import sys,time,json,os
sys.path.insert(0,'scripts');import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05';base=p.baseline();root=Path('reference/boot-tests/test-253-adbd-usb-reconnect/attempt-02');phase=sys.argv[1];limit=float(sys.argv[2]);boot='461c1408e42643afae5b48162771d077';r=p.Recorder(root/phase);start=time.monotonic();first=None;rows=[]
try:
 for n in range(1,100):
  raw,_=r.command(f'poll-{n:02}-wifi',['env','GTS9_DEVICE=10.191.121.29',p.SSH,'set -eu; cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; test "$(systemctl is-active gts9-adbd.service)" = active; test "$(cat /sys/kernel/config/usb_gadget/gts9/UDC)" = a600000.usb; journalctl -k -b --no-pager -o json'],timeout=20)
  lines=raw.splitlines();assert p.evidence.canonical_boot_id(lines[0])==boot;uptime=float(lines[1].split()[0]);first=uptime if first is None else first
  kernel='\n'.join(lines[2:])+'\n';scan=p.inspect(kernel,boot,base,uptime);assert not scan['fault_counts'] and not scan['suspects'],scan
  native,_=r.host_adb(f'poll-{n:02}-adb','-s',p.SERIAL,'shell','cat /proc/sys/kernel/random/boot_id',timeout=8);assert p.evidence.canonical_boot_id(native.strip())==boot
  row=dict(poll=n,boot_id=boot,uptime_seconds=uptime,elapsed_seconds=time.monotonic()-start,kernel_fault_counts=scan['fault_counts'],native_adb=True,wifi_ssh=True);rows.append(row);print(json.dumps(row),flush=True)
  if time.monotonic()-start>=limit:break
  time.sleep(5)
 else:raise ValueError('observation bound not completed')
 p.write_json(r.folder/'summary.json',dict(verdict='passed',boot_id=boot,registered_seconds=limit,first_uptime_seconds=first,last_uptime_seconds=uptime,elapsed_seconds=time.monotonic()-start,polls=rows,kernel_fault_counts={},native_adb_responsive=True,wifi_ssh_responsive=True))
except Exception as e:
 p.write_json(r.folder/'failure.json',dict(verdict='stopped',error=repr(e),polls=rows));raise
