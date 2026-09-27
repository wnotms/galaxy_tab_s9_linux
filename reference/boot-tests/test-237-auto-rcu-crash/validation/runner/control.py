import subprocess,pathlib,json,datetime,time
ROOT=pathlib.Path('/home/ms/Samsung/galaxy_tab_s9_linux')
P=ROOT/'reference/boot-tests/test-237-auto-rcu-crash'
ADB='/mnt/d/android/platform-tools/adb.exe'
LIVE='gts9wifi-0001'
RECOVERY='R52X10045LT'
def capture(phase,name,args,serial=LIVE,data=None,timeout=25,check=True):
 p=P/phase;p.mkdir(parents=True,exist_ok=True)
 assert not (p/(name+'.json')).exists(),name
 command=[ADB,'-s',serial]+args
 started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  r=subprocess.run(command,input=data,capture_output=True,timeout=timeout)
  status=r.returncode;out=r.stdout;err=r.stderr
 except subprocess.TimeoutExpired as e:
  status='timeout';out=e.stdout or b'';err=e.stderr or b''
 (p/(name+'.txt')).write_bytes(out);(p/(name+'.stderr')).write_bytes(err)
 (p/(name+'.json')).write_text(json.dumps({'command':command,'status':status,'utc':started},indent=2)+'\n')
 print(phase,name,status,len(out),flush=True)
 if check:assert status==0,(phase,name,status,err)
 return out.decode(errors='replace'),status

def shell(phase,name,cmd,**kwargs):return capture(phase,name,['shell',cmd],**kwargs)
def recover(phase):
 script=(ROOT/'boot/gts9-debian-to-recovery.sh').read_bytes()
 shell(phase,'bcb-check','TMPDIR=/tmp sh -s -- --check',data=script)
 shell(phase,'bcb-write','TMPDIR=/tmp sh -s -- --yes --no-reboot',data=script,timeout=35)
 shell(phase,'reboot','systemctl reboot',timeout=15)

def poll(phase,recovery=False,tries=6):
 p=P/phase;p.mkdir(parents=True,exist_ok=True);rows=[]
 for i in range(tries):
  if recovery:
   r=subprocess.run([ADB,'devices','-l'],capture_output=True,timeout=8)
   ok=RECOVERY in r.stdout.decode(errors='replace')
  else:
   subprocess.run([ADB,'connect',LIVE],capture_output=True,timeout=6)
   r=subprocess.run([ADB,'-s',LIVE,'shell','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime'],capture_output=True,timeout=8)
   ok=r.returncode==0
  rows.append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':r.returncode,'stdout':r.stdout.decode(errors='replace'),'stderr':r.stderr.decode(errors='replace')})
  (p/'poll.json').write_text(json.dumps(rows,indent=2)+'\n')
  print(rows[-1],flush=True)
  if ok:return
  time.sleep(5)

def recovery_capture(phase):
 text,_=shell(phase,'identity','getprop ro.product.device; getprop ro.product.model; getprop ro.twrp.version; cat /proc/sys/kernel/random/boot_id; uname -a; cat /sys/class/power_supply/battery/capacity',serial=RECOVERY)
 assert 'gts9wifi' in text and 'SM-X710' in text and '3.7.1' in text
 shell(phase,'partitions','for n in boot vendor_boot init_boot dtbo vbmeta; do blockdev --getsize64 /dev/block/by-name/$n; sha256sum /dev/block/by-name/$n; done',serial=RECOVERY)
 shell(phase,'pstore','ls -la /sys/fs/pstore; for f in /sys/fs/pstore/*; do [ -f "$f" ] || continue; echo FILE=$f; cat "$f"; done',serial=RECOVERY)
 shell(phase,'dmesg','dmesg',serial=RECOVERY)
 shell(phase,'last_kmsg','cat /proc/last_kmsg',serial=RECOVERY)

def flash(phase,restore=False):
 import hashlib,re
 rows=json.loads((P/'backup-and-staging.json').read_text())
 text,_=shell(phase,'identity','getprop ro.product.device; getprop ro.twrp.version',serial=RECOVERY)
 assert 'gts9wifi' in text and '3.7.1' in text
 for row in rows:
  part=row['partition'];digest=row['backup_sha256' if restore else 'candidate_sha256']
  path=pathlib.Path(row['backup_path']) if restore else ROOT/'out/boot-bundle-auto-rcu-crash'/(part+'.img')
  assert path.stat().st_size==row['bytes']==100663296
  assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
  before,_=shell(phase,'before-'+part,'blockdev --getsize64 /dev/block/by-name/'+part+'; sha256sum /dev/block/by-name/'+part,serial=RECOVERY)
  assert before.split()[0]=='100663296' and before.split()[1]==row['candidate_sha256' if restore else 'backup_sha256']
  win=('D:\\android\\gts9-test230\\backup-' if restore else 'D:\\android\\gts9-test237\\')+part+'.img'
  remote='/tmp/gts9-test237-'+('restore-' if restore else '')+part+'.img'
  capture(phase,'push-'+part,['push',win,remote],serial=RECOVERY,timeout=45)
  staged,_=shell(phase,'staged-'+part,'sha256sum '+remote,serial=RECOVERY)
  assert staged.split()[0]==digest
  after,_=shell(phase,'readback-'+part,'dd if='+remote+' of=/dev/block/by-name/'+part+' bs=1048576 && sync && sha256sum /dev/block/by-name/'+part,serial=RECOVERY,timeout=45)
  assert after.split()[0]==digest
 shell(phase,'all-partitions','for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/block/by-name/$n; done',serial=RECOVERY)
 shell(phase,'reboot','twrp reboot system',serial=RECOVERY)
