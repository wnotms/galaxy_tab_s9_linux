from pathlib import Path
import json,subprocess,time,sys,tarfile
root=Path('/var/log/gts9-test357-touch');meta=json.loads((root/'capture-meta.json').read_text());proc=Path('/proc')/str(meta['pid'])
if (proc/'stat').exists():
 fields=(proc/'stat').read_text().split();assert fields[21]==meta['proc_start_ticks']
 (root/'stop-events').touch(exist_ok=False)
 for i in range(30):
  if (root/'capture-terminal.json').exists():break
  time.sleep(.1)
assert (root/'capture-terminal.json').exists(),'original capture has not completed; do not restart'
for name,argv in {'kernel-final':['journalctl','-k','-b','-o','json','--no-pager'],'gdm-final':['systemctl','is-active','gdm.service'],'failed-final':['systemctl','--failed','--no-legend','--plain'],'interrupts-final':['cat','/proc/interrupts'],'inhibitors-final':['systemd-inhibit','--list','--no-pager']}.items():
 p=subprocess.run(argv,capture_output=True,timeout=15);(root/(name+'.stdout')).write_bytes(p.stdout);(root/(name+'.stderr')).write_bytes(p.stderr);(root/(name+'.command.json')).write_text(json.dumps(dict(argv=argv,returncode=p.returncode)))
b=Path('/sys/class/power_supply/sm5714-battery')
(root/'final-state.json').write_text(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),battery={n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')},touch_driver=str(Path('/sys/bus/i2c/devices/7-0049/driver').resolve()),double_tap_to_wake=Path('/sys/bus/i2c/devices/7-0049/double_tap_to_wake').read_text().strip(),gdm='active',permanent_autoload=False)))
t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz');t.add(root,arcname='gts9-test357-touch');t.close()
