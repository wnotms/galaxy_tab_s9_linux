"""Non-grabbing touch-only reader: preserve raw evdev records for owner testing."""
from pathlib import Path
import fcntl, json, os, select, struct, sys, time
root = Path('/var/log/gts9-test355-touch')
event = sys.argv[1]
assert event.startswith('/dev/input/event') and event[16:].isdigit()
fd = os.open(event, os.O_RDONLY | os.O_NONBLOCK)
layout = struct.Struct('@llHHi')
assert layout.size == 24
meta = dict(event=event, pid=os.getpid(), boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            proc_start_ticks=Path('/proc/self/stat').read_text().split()[21], grabbing=False,
            event_struct='@llHHi', deadline_seconds=900, axes={})
for code in (0x2f, 0x35, 0x36, 0x39):
    buf = bytearray(24)
    fcntl.ioctl(fd, 0x80184540 + code, buf, True)
    meta['axes'][str(code)] = dict(zip(('value','minimum','maximum','fuzz','flat','resolution'),struct.unpack('6i',buf)))
(root/'capture-meta.json').write_text(json.dumps(meta,indent=2)+'\n')
start=time.monotonic();count=0;frames=0;reason='deadline';pending=b''
try:
    with (root/'events.bin').open('xb') as raw, (root/'events.jsonl').open('x') as out:
        while time.monotonic()-start < 900:
            if (root/'stop-events').exists():
                reason='host_requested_after_owner_result';break
            ready,_,_=select.select([fd],[],[],1)
            if not ready:continue
            data=os.read(fd,layout.size*256)
            if not data:raise RuntimeError('touch evdev closed')
            raw.write(data);raw.flush();pending+=data
            while len(pending)>=layout.size:
                sec,usec,typ,code,value=layout.unpack(pending[:layout.size]);pending=pending[layout.size:]
                out.write(json.dumps(dict(sec=sec,usec=usec,type=typ,code=code,value=value))+'\n')
                count+=1;frames+=int(typ==0 and code==0)
            out.flush()
            if raw.tell()>32*1024*1024:raise RuntimeError('unexpected event volume')
except BaseException as exc:
    reason=repr(exc);raise
finally:
    os.close(fd)
    (root/'capture-terminal.json').write_text(json.dumps(dict(pid=os.getpid(),reason=reason,
       seconds=time.monotonic()-start,events=count,frames=frames,trailing_bytes=len(pending)),indent=2)+'\n')
