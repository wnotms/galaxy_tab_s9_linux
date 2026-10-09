from pathlib import Path
import json,hashlib,importlib.util,marshal,base64,struct
p=Path('/usr/local/libexec/__pycache__/gts9-usb-typec-lifecyclecpython-313.pyc')
print(json.dumps({'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'cache_directory': [{'path':str(x),'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest(),'mtime_ns':x.stat().st_mtime_ns} for x in Path('/usr/local/libexec/__pycache__').glob('*typec*')],'unit_state': __import__('subprocess').run(['systemctl','is-active','gts9-test367-lifecycle.service'],capture_output=True,text=True).stdout}))
