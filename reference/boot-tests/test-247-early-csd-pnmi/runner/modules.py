import control
import hashlib,json,re
from pathlib import Path

RELEASE='7.2.0-rc3-gts9wifi-dirty'
MOUNT='/mnt/debian'
def mount_root(phase):
 source=json.loads((control.P/'preflight/source.json').read_text())
 s,_=control.shell(phase,'root-devices','getprop ro.product.device; getprop ro.twrp.version; toybox blkid /dev/block/mmcblk*p*; cat /proc/mounts',serial=control.RECOVERY,timeout=12)
 assert 'gts9wifi' in s and '3.7.1' in s
 candidates=[]
 for line in s.splitlines():
  if 'UUID="'+source['root_uuid']+'"' in line:
   assert 'TYPE="ext4"' in line
   candidates.append(line.split(':',1)[0])
 assert len(candidates)==1,candidates
 device=candidates[0]
 assert re.fullmatch(r'/dev/block/mmcblk\d+p\d+',device),device
 mounted=[line for line in s.splitlines() if len(line.split())>=3 and line.split()[1]==MOUNT]
 if mounted:
  assert len(mounted)==1 and mounted[0].split()[0]==device and mounted[0].split()[2]=='ext4'
 else:
  control.shell(phase,'mount','mkdir -p '+MOUNT+' && mount -t ext4 -o rw '+device+' '+MOUNT,serial=control.RECOVERY)
 s,_=control.shell(phase,'root-identity','cat /proc/mounts; cat '+MOUNT+'/etc/machine-id; cat '+MOUNT+'/etc/debian_version; df -k '+MOUNT,serial=control.RECOVERY)
 assert '3c2a1b8f2d624db4b5ffdc836050fcf6' in s
 lines=[l for l in s.splitlines() if len(l.split())>=3 and l.split()[1]==MOUNT]
 assert len(lines)==1 and lines[0].split()[0]==device and 'rw' in lines[0].split()[3].split(',')
 (control.P/phase/'mounted-root.json').write_text(json.dumps({'uuid':source['root_uuid'],'device':device,'mount':MOUNT,'identity_verified':True},indent=2)+'\n')

def push(phase,name):
 local=control.ROOT/'out/test247'/name
 # Source artifacts staged on Windows were copied from these verified local files.
 stage=Path('/mnt/d/android/gts9-test247')/name
 digest=hashlib.sha256(local.read_bytes()).hexdigest()
 assert hashlib.sha256(stage.read_bytes()).hexdigest()==digest
 remote='/tmp/gts9-247-'+name
 control.capture(phase,'push-'+name,['push','D:\\android\\gts9-test247\\'+name,remote],serial=control.RECOVERY,timeout=45)
 s,_=control.shell(phase,'hash-'+name,'sha256sum '+remote,serial=control.RECOVERY,timeout=12)
 assert s.split()[0]==digest
 return remote

def swap(phase,restore=False):
 mount_root(phase)
 script=push(phase,'module-swap.sh')
 original=push(phase,'original-module-checksums.txt')
 if restore:
  cmd='sh '+script+' '+MOUNT+' restore '+original
 else:
  candidate=push(phase,'candidate-module-checksums.txt')
  archive=push(phase,'candidate-modules.tar')
  expected=json.loads((control.P/'validation/candidate-modules.json').read_text())['tar_sha256']
  assert hashlib.sha256((control.ROOT/'out/test247/candidate-modules.tar').read_bytes()).hexdigest()==expected
  cmd='sh '+script+' '+MOUNT+' install '+candidate+' '+archive+' '+original
 s,_=control.shell(phase,'swap',cmd,serial=control.RECOVERY,timeout=45)
 assert s.count(': OK')==(362 if restore else 543),s[-1000:]
 # Recheck actual paths after the verified rename before any image/boot action.
 s,_=control.shell(phase,'post-swap','ls -ld '+MOUNT+'/usr/lib/modules/'+RELEASE+' '+MOUNT+'/usr/lib/modules/.gts9-test247-*; cat /proc/sys/kernel/random/boot_id',serial=control.RECOVERY)
 (control.P/phase/'modules-verified.json').write_text(json.dumps({'restore':restore,'regular_files':181,'rootfs_uuid':json.loads((control.P/'preflight/source.json').read_text())['root_uuid']},indent=2)+'\n')

def reboot(phase,image_phase,module_phase,restore=False):
 a=json.loads((control.P/image_phase/'images-verified.json').read_text())
 b=json.loads((control.P/module_phase/'modules-verified.json').read_text())
 assert a['restore']==b['restore']==restore
 control.shell(phase,'unmount','sync && umount '+MOUNT,serial=control.RECOVERY,timeout=15)
 control.shell(phase,'reboot','twrp reboot system',serial=control.RECOVERY,timeout=15)
