from pathlib import Path
import json,io,tarfile,sys,os,time
root=Path('/var/log/gts9-test362-pen');m=json.loads((root/'capture-meta.json').read_text());p=Path('/proc')/str(m['pid'])
alive=p.exists();match=False;state=None
if alive:
 fields=(p/'stat').read_text().rsplit(')',1)[1].split();match=fields[19]==m['proc_start_ticks'];state=fields[0]
b=Path('/sys/class/power_supply/sm5714-battery')
record={'pid':m['pid'],'proc_alive':alive,'start_match':match,'proc_state':state,'terminal_exists':(root/'capture-terminal.json').exists(),'events_bytes':(root/'events.bin').stat().st_size,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'battery':{n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')}}
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as t:
 for f in sorted(root.iterdir()):
  if f.is_file() and f.name not in ('events.bin','events.jsonl','capture.stdout','capture.stderr','capture-terminal.json'):
   data=f.read_bytes();info=tarfile.TarInfo(f.name);info.size=len(data);t.addfile(info,io.BytesIO(data))
 data=(json.dumps(record,indent=2)+'\n').encode();info=tarfile.TarInfo('live-check.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
sys.stdout.buffer.write(buf.getvalue())
