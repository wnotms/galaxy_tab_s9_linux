from pathlib import Path
import struct,mmap,bisect,json,sys,hashlib
P=Path('reference/boot-tests/test-245-bbm-low-address')
relocation=json.loads((P/'analysis/runtime-relocation.json').read_text())
delta=relocation['runtime_minus_link']
f=Path('out/test240/vmlinux');assert hashlib.sha256(f.read_bytes()).hexdigest()=='f502b50130a750d3cd692abecaf32d27a3f0b4c2f6d082fd82303aaa2269f3af'
symbols=[]
for line in Path('out/test240/System.map').read_text().splitlines():
 a,t,n=line.split()[:3];symbols.append((int(a,16),t,n))
symbols.sort();addresses=[s[0] for s in symbols]
def symbol(addr):
 addr -= delta
 i=bisect.bisect_right(addresses,addr)-1
 if i<0:return None
 a,t,n=symbols[i];return n+'+0x'+format(addr-a,'x')+' ['+t+']'
with f.open('rb') as handle:
 data=mmap.mmap(handle.fileno(),0,access=mmap.ACCESS_READ)
 assert data[:6]==b'\x7fELF\x02\x01'
 phoff=struct.unpack_from('<Q',data,32)[0];size,num=struct.unpack_from('<HH',data,54)
 segments=[struct.unpack_from('<IIQQQQQQ',data,phoff+i*size) for i in range(num)]
 def string(addr):
  addr -= delta
  for typ,flags,off,va,pa,fs,ms,align in segments:
   if typ==1 and va<=addr<va+fs:
    start=off+addr-va;raw=data[start:min(start+128,off+fs)].split(b'\0',1)[0]
    try:return raw.decode('ascii')
    except UnicodeDecodeError:return None
  return None
 snap=json.loads(Path(sys.argv[1]).read_text());rows=[]
 identity=json.loads((P/'target/identity.json').read_text())
 assert identity['boot_id']==relocation['target_boot_id'], 'relocation belongs to another boot'
 assert snap['capture_id']==identity['capture_id'], 'capture belongs to another boot'
 for r in snap['records']:
  q=dict(r);k=r['kind']
  if k<=2:
   addr=int(r['b' if k==0 else 'a'],16);q['function']=symbol(addr) if addr else None
  else:
   addr=int(r['b' if k==3 else 'a'],16);q['reason_string']=string(addr) if addr else None
  rows.append(q)
 result={'capture_id':snap['capture_id'],'relocation':relocation,'valid_cpus':snap['cpus'],'records':rows,'interpretation':'last positive observations only; no missing-event or causal inference'}
 Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
 for r in rows:
  print(r['cpu'],r['kind'],r['count'],round(r['ns']/1e9,6),r.get('function',r.get('reason_string')))
