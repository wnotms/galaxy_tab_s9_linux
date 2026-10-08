from pathlib import Path
import subprocess,json
b=Path('/sys/class/power_supply/sm5714-battery')
print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),gdm=subprocess.check_output(['systemctl','is-active','gdm.service'],text=True).strip(),backlight_service=subprocess.check_output(['systemctl','is-active','gts9-power-key.service'],text=True).strip(),battery={n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')},power_key_state={str(f):f.read_text() for f in Path('/run/gts9-power-key').glob('*') if f.is_file()})))
p=subprocess.run(['journalctl','-b','--after-cursor','s=0e9cc8651fa34ae5875adb1b7f906071;i=f890d;b=1adc0f13a2104856bb15c6e9df17867a;m=1cb4e89b;t=65c9ba946ec8f;x=40ff68df5c7a3a97','-o','json','--no-pager'],capture_output=True,timeout=10);print(p.stdout.decode());assert p.returncode==0
