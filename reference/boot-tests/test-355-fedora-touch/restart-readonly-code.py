from pathlib import Path
import subprocess,json,gzip,hashlib
b=Path('/sys/class/power_supply/sm5714-battery')
print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),uname=subprocess.check_output(['uname','-a'],text=True).strip(),uptime=Path('/proc/uptime').read_text().strip(),cmdline=Path('/proc/cmdline').read_text().strip(),config=hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest(),notes=hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest(),battery={n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now','voltage_now')},touch_module_loaded=Path('/sys/module/fts1ba90a').exists(),touch_log_exists=Path('/var/log/gts9-test355-touch').exists())))
print(subprocess.run(['journalctl','--list-boots','--no-pager'],capture_output=True,text=True,timeout=10).stdout)
print(subprocess.run(['systemctl','--failed','--no-legend','--plain'],capture_output=True,text=True,timeout=5).stdout)
