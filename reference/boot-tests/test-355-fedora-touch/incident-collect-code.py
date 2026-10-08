import io,tarfile,subprocess,json,sys
from pathlib import Path
old='be1baaaa47fc41f582558f7092c01653'
items={}
commands={'previous-kernel.jsonl':['journalctl','-k','-b',old,'-o','json','--no-pager'],'previous-system-tail-3000.jsonl':['journalctl','-b',old,'-n','3000','-o','json','--no-pager'],'current-kernel.jsonl':['journalctl','-k','-b','-o','json','--no-pager'],'previous-power-units.jsonl':['journalctl','-b',old,'-u','systemd-logind.service','-u','upower.service','-u','gdm.service','-u','systemd-poweroff.service','-u','systemd-suspend.service','-o','json','--no-pager'],'current-gdm.txt':['systemctl','is-active','gdm.service']}
for name,argv in commands.items():
 p=subprocess.run(argv,capture_output=True,timeout=20);items[name]=p.stdout;items[name+'.stderr']=p.stderr;items[name+'.command.json']=json.dumps(dict(argv=argv,returncode=p.returncode)).encode()
items['pstore-state.json']=json.dumps({str(p):p.stat().st_size for p in Path('/sys/fs/pstore').glob('*')}).encode()
for f in Path('/sys/fs/pstore').glob('*'):
 if f.is_file() and f.stat().st_size<=4*1024*1024:items['pstore/'+f.name]=f.read_bytes()
t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz')
for name,data in items.items():
 i=tarfile.TarInfo(name);i.size=len(data);t.addfile(i,io.BytesIO(data))
t.close()
