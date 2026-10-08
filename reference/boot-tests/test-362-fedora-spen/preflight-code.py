from pathlib import Path
import json,hashlib,gzip,subprocess
b=Path('/sys/class/power_supply/sm5714-battery')
clients=[]
for f in Path('/sys/bus/i2c/devices').glob('*-0056'):
 clients.append({'path':str(f),'name':(f/'name').read_text().strip(),'modalias':(f/'modalias').read_text().strip(),'driver':str((f/'driver').resolve()) if (f/'driver').exists() else None,'of_node':str((f/'of_node').resolve()),'irq':(f/'irq').read_text().strip() if (f/'irq').exists() else None})
print(json.dumps({'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'config':hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest(),'notes':hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest(),'cmdline':Path('/proc/cmdline').read_text().strip(),'uname':subprocess.check_output(['uname','-a'],text=True).strip(),'battery':{n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')},'gdm':subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,text=True).stdout.strip(),'pen_clients':clients,'touch_loaded':Path('/sys/module/fts1ba90a').exists(),'pen_loaded':Path('/sys/module/wacom_wez01').exists(),'taint':Path('/proc/sys/kernel/tainted').read_text().strip()}))
print('=== Input ===');print(Path('/proc/bus/input/devices').read_text())
print('=== CRC location ===')
for line in Path('/proc/kallsyms').read_text().splitlines():
 name=line.split()[2]
 if name in ('_text','_stext','_end','__start___kcrctab','__stop___kcrctab','__start___ksymtab','__stop___ksymtab'): print(line)
print('=== Failed units ===');print(subprocess.check_output(['systemctl','--failed','--no-pager','--plain'],text=True))
