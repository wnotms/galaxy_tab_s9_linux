#!/usr/bin/env python3
"""Bounded, process-private executable-permission exercise; no fault injection."""
import ctypes,os,time,json,pathlib,sys,signal
libc=ctypes.CDLL(None,use_errno=True)
libc.mmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_long];libc.mmap.restype=ctypes.c_void_p
libc.mprotect.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int];libc.mprotect.restype=ctypes.c_int
libc.munmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t];libc.munmap.restype=ctypes.c_int
clear=ctypes.CDLL('libgcc_s.so.1').__clear_cache;clear.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
PAGE=os.sysconf('SC_PAGE_SIZE');assert PAGE==4096
assert os.uname().machine=='aarch64'
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
trace=pathlib.Path('/sys/kernel/tracing');event='gts9_bbm_240';instance=trace/'instances'/event
created_event=False;created_instance=False;maps=[]
def emit(**kw):print(json.dumps({'boot_id':boot,'monotonic':time.monotonic(),**kw}),flush=True)
def protect(addr,length,prot):
 if libc.mprotect(addr,length,prot):raise OSError(ctypes.get_errno(),'mprotect')
def cycle(addr,length,fn):
 protect(addr,length,5) # RX: never RWX
 if fn()!=42:raise RuntimeError('generated return value mismatch')
 protect(addr,length,3) # remove execute permission; exercise BBM workaround
 if ctypes.c_uint32.from_address(addr).value!=0x52800540:raise RuntimeError('code bytes changed')
def abort(signum,frame):raise TimeoutError('bounded workload watchdog')
signal.signal(signal.SIGALRM,abort);signal.alarm(35)
try:
 assert not instance.exists() and event not in (trace/'kprobe_events').read_text()
 assert {3,4}.issubset(os.sched_getaffinity(0))
 # CPU identities, rather than CPU numbering alone, establish A715 coverage.
 for cpu in (3,4):
  midr=int(pathlib.Path(f'/sys/devices/system/cpu/cpu{cpu}/regs/identification/midr_el1').read_text(),0)
  assert (midr>>4)&0xfff==0xd4d
  emit(phase='cpu_identity',cpu=cpu,midr=hex(midr))
 for pages in (1,2,16):
  length=pages*PAGE;addr=libc.mmap(None,length,3,0x22,-1,0)
  if addr==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_errno(),'mmap')
  # ARM64 mov w0,#42; ret. Private generated page, no existing code changed.
  ctypes.memmove(addr,bytes.fromhex('40058052c0035fd6'),8);clear(addr,addr+8)
  maps.append((addr,length,ctypes.CFUNCTYPE(ctypes.c_int)(addr)))
  emit(phase='mapping',address=hex(addr),length=length)
 with (trace/'kprobe_events').open('a') as f:f.write(f'p:{event} modify_prot_start_ptes addr=%x1:u64 nr=%x3:u32\n')
 created_event=True;instance.mkdir();created_instance=True
 (instance/'buffer_size_kb').write_text('16')
 ep=instance/'events/kprobes'/event
 (ep/'filter').write_text(f'common_pid == {os.getpid()}')
 (ep/'enable').write_text('1');(instance/'tracing_on').write_text('1')
 os.sched_setaffinity(0,{3})
 for addr,length,fn in maps:cycle(addr,length,fn)
 (ep/'enable').write_text('0');(instance/'tracing_on').write_text('0')
 sample=(instance/'trace').read_text();print('GTS9_BBM_TRACE_BEGIN',flush=True);print(sample,flush=True);print('GTS9_BBM_TRACE_END',flush=True)
 assert event+':' in sample, 'no actual modify_prot_start_ptes trace'
 emit(phase='trace_verified',pid=os.getpid())
 for cpu in (3,4):
  os.sched_setaffinity(0,{cpu});start=time.monotonic();deadline=start+8;iterations=0
  while time.monotonic()<deadline:
   for addr,length,fn in maps:cycle(addr,length,fn)
   iterations+=1
  emit(phase='cpu_complete',cpu=cpu,iterations=iterations,mprotect_calls=iterations*6,seconds=time.monotonic()-start)
 assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
 emit(phase='complete',result='permission_workload_passed',cpu_stall_fix_established=False)
finally:
 signal.alarm(0)
 if created_instance:
  (instance/'events/kprobes'/event/'enable').write_text('0')
  (instance/'tracing_on').write_text('0');instance.rmdir()
 if created_event:
  with (trace/'kprobe_events').open('a') as f:f.write(f'-:{event}\n')
 for addr,length,fn in maps:libc.munmap(addr,length)
