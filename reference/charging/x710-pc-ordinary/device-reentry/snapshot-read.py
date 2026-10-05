import pathlib,gzip,hashlib,json,subprocess
p=pathlib.Path
r={'boot_before':p('/proc/sys/kernel/random/boot_id').read_text().strip(),'uname':subprocess.check_output(['uname','-a'],text=True).strip(),'cmdline':p('/proc/cmdline').read_text().strip(),'uptime':p('/proc/uptime').read_text().strip(),'config_sha256':hashlib.sha256(gzip.decompress(p('/proc/config.gz').read_bytes())).hexdigest(),'notes_sha256':hashlib.sha256(p('/sys/kernel/notes').read_bytes()).hexdigest(),'supplies':{},'roles':{},'hvc0_present':p('/dev/hvc0').exists() or p('/sys/class/tty/hvc0').exists()}
for x in p('/sys/class/power_supply').glob('*/uevent'): r['supplies'][x.parent.name]=x.read_text()
for x in p('/sys/class/typec').glob('*/*'):
 if x.name in ['power_role','data_role','power_operation_mode','port_type']:
  try: r['roles'][str(x)]=x.read_text().strip()
  except OSError: pass
r['ip']=subprocess.check_output(['ip','-j','address'],text=True)
x=p('/sys/kernel/debug/sm5440-0-0063/snapshot')
if x.exists(): r['cached_sm5440']=x.read_text()
r['failed_units']=subprocess.run(['systemctl','--failed','--no-legend','--plain'],capture_output=True,text=True,timeout=3).stdout
r['boot_after']=p('/proc/sys/kernel/random/boot_id').read_text().strip()
print(json.dumps(r,indent=2))
