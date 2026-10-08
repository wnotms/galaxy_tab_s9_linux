from pathlib import Path
import base64, gzip, hashlib, json, re, subprocess, sys, time
CAPTURE_B64='IiIiTm9uLWdyYWJiaW5nIHRvdWNoLW9ubHkgcmVhZGVyOiBwcmVzZXJ2ZSByYXcgZXZkZXYgcmVjb3JkcyBmb3Igb3duZXIgdGVzdGluZy4iIiIKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCmltcG9ydCBmY250bCwganNvbiwgb3MsIHNlbGVjdCwgc3RydWN0LCBzeXMsIHRpbWUKcm9vdCA9IFBhdGgoJy92YXIvbG9nL2d0czktdGVzdDM1NS10b3VjaCcpCmV2ZW50ID0gc3lzLmFyZ3ZbMV0KYXNzZXJ0IGV2ZW50LnN0YXJ0c3dpdGgoJy9kZXYvaW5wdXQvZXZlbnQnKSBhbmQgZXZlbnRbMTY6XS5pc2RpZ2l0KCkKZmQgPSBvcy5vcGVuKGV2ZW50LCBvcy5PX1JET05MWSB8IG9zLk9fTk9OQkxPQ0spCmxheW91dCA9IHN0cnVjdC5TdHJ1Y3QoJ0BsbEhIaScpCmFzc2VydCBsYXlvdXQuc2l6ZSA9PSAyNAptZXRhID0gZGljdChldmVudD1ldmVudCwgcGlkPW9zLmdldHBpZCgpLCBib290X2lkPVBhdGgoJy9wcm9jL3N5cy9rZXJuZWwvcmFuZG9tL2Jvb3RfaWQnKS5yZWFkX3RleHQoKS5zdHJpcCgpLAogICAgICAgICAgICBwcm9jX3N0YXJ0X3RpY2tzPVBhdGgoJy9wcm9jL3NlbGYvc3RhdCcpLnJlYWRfdGV4dCgpLnNwbGl0KClbMjFdLCBncmFiYmluZz1GYWxzZSwKICAgICAgICAgICAgZXZlbnRfc3RydWN0PSdAbGxISGknLCBkZWFkbGluZV9zZWNvbmRzPTkwMCwgYXhlcz17fSkKZm9yIGNvZGUgaW4gKDB4MmYsIDB4MzUsIDB4MzYsIDB4MzkpOgogICAgYnVmID0gYnl0ZWFycmF5KDI0KQogICAgZmNudGwuaW9jdGwoZmQsIDB4ODAxODQ1NDAgKyBjb2RlLCBidWYsIFRydWUpCiAgICBtZXRhWydheGVzJ11bc3RyKGNvZGUpXSA9IGRpY3QoemlwKCgndmFsdWUnLCdtaW5pbXVtJywnbWF4aW11bScsJ2Z1enonLCdmbGF0JywncmVzb2x1dGlvbicpLHN0cnVjdC51bnBhY2soJzZpJyxidWYpKSkKKHJvb3QvJ2NhcHR1cmUtbWV0YS5qc29uJykud3JpdGVfdGV4dChqc29uLmR1bXBzKG1ldGEsaW5kZW50PTIpKydcbicpCnN0YXJ0PXRpbWUubW9ub3RvbmljKCk7Y291bnQ9MDtmcmFtZXM9MDtyZWFzb249J2RlYWRsaW5lJztwZW5kaW5nPWInJwp0cnk6CiAgICB3aXRoIChyb290LydldmVudHMuYmluJykub3BlbigneGInKSBhcyByYXcsIChyb290LydldmVudHMuanNvbmwnKS5vcGVuKCd4JykgYXMgb3V0OgogICAgICAgIHdoaWxlIHRpbWUubW9ub3RvbmljKCktc3RhcnQgPCA5MDA6CiAgICAgICAgICAgIGlmIChyb290LydzdG9wLWV2ZW50cycpLmV4aXN0cygpOgogICAgICAgICAgICAgICAgcmVhc29uPSdob3N0X3JlcXVlc3RlZF9hZnRlcl9vd25lcl9yZXN1bHQnO2JyZWFrCiAgICAgICAgICAgIHJlYWR5LF8sXz1zZWxlY3Quc2VsZWN0KFtmZF0sW10sW10sMSkKICAgICAgICAgICAgaWYgbm90IHJlYWR5OmNvbnRpbnVlCiAgICAgICAgICAgIGRhdGE9b3MucmVhZChmZCxsYXlvdXQuc2l6ZSoyNTYpCiAgICAgICAgICAgIGlmIG5vdCBkYXRhOnJhaXNlIFJ1bnRpbWVFcnJvcigndG91Y2ggZXZkZXYgY2xvc2VkJykKICAgICAgICAgICAgcmF3LndyaXRlKGRhdGEpO3Jhdy5mbHVzaCgpO3BlbmRpbmcrPWRhdGEKICAgICAgICAgICAgd2hpbGUgbGVuKHBlbmRpbmcpPj1sYXlvdXQuc2l6ZToKICAgICAgICAgICAgICAgIHNlYyx1c2VjLHR5cCxjb2RlLHZhbHVlPWxheW91dC51bnBhY2socGVuZGluZ1s6bGF5b3V0LnNpemVdKTtwZW5kaW5nPXBlbmRpbmdbbGF5b3V0LnNpemU6XQogICAgICAgICAgICAgICAgb3V0LndyaXRlKGpzb24uZHVtcHMoZGljdChzZWM9c2VjLHVzZWM9dXNlYyx0eXBlPXR5cCxjb2RlPWNvZGUsdmFsdWU9dmFsdWUpKSsnXG4nKQogICAgICAgICAgICAgICAgY291bnQrPTE7ZnJhbWVzKz1pbnQodHlwPT0wIGFuZCBjb2RlPT0wKQogICAgICAgICAgICBvdXQuZmx1c2goKQogICAgICAgICAgICBpZiByYXcudGVsbCgpPjMyKjEwMjQqMTAyNDpyYWlzZSBSdW50aW1lRXJyb3IoJ3VuZXhwZWN0ZWQgZXZlbnQgdm9sdW1lJykKZXhjZXB0IEJhc2VFeGNlcHRpb24gYXMgZXhjOgogICAgcmVhc29uPXJlcHIoZXhjKTtyYWlzZQpmaW5hbGx5OgogICAgb3MuY2xvc2UoZmQpCiAgICAocm9vdC8nY2FwdHVyZS10ZXJtaW5hbC5qc29uJykud3JpdGVfdGV4dChqc29uLmR1bXBzKGRpY3QocGlkPW9zLmdldHBpZCgpLHJlYXNvbj1yZWFzb24sCiAgICAgICBzZWNvbmRzPXRpbWUubW9ub3RvbmljKCktc3RhcnQsZXZlbnRzPWNvdW50LGZyYW1lcz1mcmFtZXMsdHJhaWxpbmdfYnl0ZXM9bGVuKHBlbmRpbmcpKSxpbmRlbnQ9MikrJ1xuJykK'
BOOT='be1baaaa-47fc-41f5-8255-8f7092c01653'
MODULE='ac2fbdc6489b847771a65a1971d28f0b5d601c796c50d68c92f85a70feaf5e45'
root=Path('/var/log/gts9-test355-touch');stage=Path('/var/tmp/gts9-test355')
client=Path('/sys/bus/i2c/devices/7-0049');b=Path('/sys/class/power_supply/sm5714-battery')
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest()=='51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a'
assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest()=='03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95'
assert b'st,fts1ba90a\x00' in (client/'of_node/compatible').read_bytes()
assert not (client/'driver').exists() and not Path('/sys/module/fts1ba90a').exists()
assert (b/'health').read_text().strip()=='Good' and int((b/'temp').read_text())<380 and int((b/'capacity').read_text())>=20
assert subprocess.check_output(['systemctl','is-active','gdm.service'],text=True).strip()=='active'
root.mkdir(exist_ok=False);stage.mkdir(exist_ok=False)
state=dict(boot_id=BOOT,verdict='STARTED',insmod_attempts=0,module_sha256=MODULE,touch_driver='Fedora X710 ab123e7d byte-identical',autoload=False)
def run(name,argv,check=True):
 p=subprocess.run(argv,capture_output=True,timeout=15)
 (root/(name+'.stdout')).write_bytes(p.stdout);(root/(name+'.stderr')).write_bytes(p.stderr)
 (root/(name+'.command.json')).write_text(json.dumps(dict(argv=argv,returncode=p.returncode,monotonic=time.monotonic())))
 if check and p.returncode:raise RuntimeError(name+' failed '+str(p.returncode))
 return p
try:
 assert not run('failed-before',['systemctl','--failed','--no-legend','--plain']).stdout.strip()
 state['journal_start_cursor']=json.loads(run('cursor',['journalctl','-n','1','-o','json','--no-pager']).stdout)['__CURSOR']
 run('kernel-before',['journalctl','-k','-b','-o','json','--no-pager'])
 (root/'taint-before.txt').write_text(Path('/proc/sys/kernel/tainted').read_text())
 data=sys.stdin.buffer.read(441777)
 assert len(data)==441776 and hashlib.sha256(data).hexdigest()==MODULE
 path=stage/'fts1ba90a.ko';path.write_bytes(data);path.chmod(0o600)
 state['insmod_attempts']=1
 run('insmod',['/usr/sbin/insmod',str(path)])  # No --force, CRC/signature/BTF bypass or retry.
 deadline=time.monotonic()+10
 while not (client/'driver').exists() and time.monotonic()<deadline:time.sleep(.2)
 assert (client/'driver').resolve().name=='fts1ba90a','touch client not bound'
 events=list(client.glob('input/input*/event*'))
 assert len(events)==1,'touch input not uniquely enumerated'
 event='/dev/input/'+events[0].name;assert Path(event).exists()
 state['event_device']=event;state['driver_bound']=str((client/'driver').resolve())
 attr=client/'double_tap_to_wake'
 assert attr.read_text().strip()=='0','double tap wake must remain off'
 run('udev-settle',['udevadm','settle','--timeout=5'])
 run('udev',['udevadm','info','--query=property','--name',event])
 run('interrupts-before',['cat','/proc/interrupts'])
 time.sleep(5)
 run('interrupts-after',['cat','/proc/interrupts'])
 def irq_count(name):
  lines=[x for x in (root/(name+'.stdout')).read_text().splitlines() if 'fts1ba90a' in x]
  assert len(lines)==1,'touch IRQ attribution ambiguous'
  return sum(int(x) for x in lines[0].split(':',1)[1].split() if x.isdigit())
 state['initial_irq_delta_5s']=irq_count('interrupts-after')-irq_count('interrupts-before')
 assert 0<=state['initial_irq_delta_5s']<15000,'unexpected interrupt rate'
 run('input-devices',['cat','/proc/bus/input/devices'])
 kernel=run('kernel-after',['journalctl','-k','-b','-o','json','--no-pager']).stdout
 records=[json.loads(x) for x in kernel.splitlines() if x]
 after=[x for x in records if x.get('__MONOTONIC_TIMESTAMP','0').isdigit() and int(x['__MONOTONIC_TIMESTAMP'])>int(state['journal_start_cursor'].split(';m=')[1].split(';')[0],16)]
 pattern=re.compile(r'soft lockup|rcu.*(?:stall|INFO)|CSD.*(?:stall|non.respon)|Kernel panic|Oops:|BUG:|Internal error|SError|GPU fault|GPU hang|GPU recovery|fts1ba90a.*(?:failed|error|unexpected)|BTF.*(?:invalid|failed)|disagrees about version|Unknown symbol',re.I)
 state['new_faults']=[x.get('MESSAGE') for x in after if pattern.search(str(x.get('MESSAGE','')))]
 assert not state['new_faults'],'new fault after touch load'
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
 assert (b/'health').read_text().strip()=='Good' and int((b/'temp').read_text())<420
 assert run('gdm',['systemctl','is-active','gdm.service']).stdout.strip()==b'active'
 assert not run('failed-after',['systemctl','--failed','--no-legend','--plain']).stdout.strip()
 props=(root/'udev.stdout').read_text();assert 'ID_INPUT_TOUCHSCREEN=1' in props
 capture=stage/'capture-events.py'
 capture.write_bytes(base64.b64decode(CAPTURE_B64))
 with (root/'capture.stdout').open('wb') as out,(root/'capture.stderr').open('wb') as err:
  worker=subprocess.Popen(['systemd-inhibit','--what=sleep','--mode=block','--who=Test355','--why=First touch validation, suspend not accepted','python3',str(capture),event],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
 state['capture_launcher_pid']=worker.pid
 for i in range(20):
  if (root/'capture-meta.json').exists():break
  assert worker.poll() is None,'capture worker exited';time.sleep(.1)
 assert (root/'capture-meta.json').exists(),'capture did not start'
 meta=json.loads((root/'capture-meta.json').read_text())
 state['capture_pid']=meta['pid']
 state['capture_proc_start_ticks']=meta['proc_start_ticks']
 state.update(verdict='TOUCH_ENUMERATED_CAPTURE_LIVE_AWAITING_OWNER',double_tap_to_wake=False,
    battery={n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')})
except BaseException as exc:
 state.update(verdict='STOP_TOUCH_BRINGUP',error=repr(exc));raise
finally:
 (root/'taint-after.txt').write_text(Path('/proc/sys/kernel/tainted').read_text())
 (root/'summary.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state),flush=True)
