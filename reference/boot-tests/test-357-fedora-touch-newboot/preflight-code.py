from pathlib import Path
import json,gzip,hashlib,subprocess
b=Path('/sys/class/power_supply/sm5714-battery')
print(json.dumps({'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'uname':subprocess.check_output(['uname','-a'],text=True).strip(),'cmdline':Path('/proc/cmdline').read_text().strip(),'config':hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest(),'notes':hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest(),'battery':{n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')},'gdm':subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,text=True).stdout.strip(),'touch_module_loaded':Path('/sys/module/fts1ba90a').exists()}))
print('=== Touch clients ===')
for f in Path('/sys/bus/i2c/devices').glob('*-0049'):
 print(str(f), 'name', (f/'name').read_text().strip(), 'driver',str((f/'driver').resolve()) if (f/'driver').exists() else None, 'modalias',(f/'modalias').read_text().strip())
print('=== Input ===');print(Path('/proc/bus/input/devices').read_text())
print('=== CRC location ===')
for line in Path('/proc/kallsyms').read_text().splitlines():
 name=line.split()[2]
 if name in ('_text','_stext','_end','__start___kcrctab','__stop___kcrctab','__start___ksymtab','__stop___ksymtab','__start___kcrctab_gpl','__stop___kcrctab_gpl','__start___ksymtab_gpl','__stop___ksymtab_gpl') or name.startswith('__crc_i2c_'): print(line)
print('=== Suspend ===');print(subprocess.run(['systemctl','list-timers','--all','--no-pager'],capture_output=True,text=True).stdout)
