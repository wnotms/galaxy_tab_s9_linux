import hashlib,json,shutil,time,os
from pathlib import Path
from collections import defaultdict
R=Path('/home/ms/Samsung/galaxy_tab_s9_linux');D=Path('/mnt/d/android/gts9-active');save=R/'.work/host-storage-cleanup/2026-10-02';save.mkdir(parents=True,exist_ok=True)
report=R/'reference/host-storage-cleanup/2026-10-02';report.mkdir(parents=True,exist_ok=True)
keep={'gts9-stock','gts9-test263','gts9-test292'}
local=defaultdict(list)
for root in [R/'out',R/'.work/d-drive-test-archive']:
 for f in root.rglob('*'):
  if f.is_file():
   size=f.stat().st_size
   if size>=1024*1024:local[size].append(f)
cache={};actions=[];before=shutil.disk_usage('/mnt/d')
def digest(f):
 key=str(f)
 if key not in cache:
  h=hashlib.sha256()
  with f.open('rb') as s:
   for b in iter(lambda:s.read(8*1024*1024),b''):h.update(b)
  cache[key]=h.hexdigest()
 return cache[key]
def checkpoint():
 (report/'manifest.json').write_text(json.dumps(dict(scope='only historical project staging under D:/android/gts9-active',preserved=sorted(keep)+['D:/android/platform-tools'],before_free_bytes=before.free,actions=actions),indent=2)+'\n')
for folder in sorted(D.iterdir()):
 if not folder.is_dir() or not folder.name.startswith('gts9-test') or folder.name in keep:continue
 number=folder.name.removeprefix('gts9-test').split('-')[0]
 for f in sorted(folder.rglob('*')):
  if not f.is_file():continue
  size=f.stat().st_size;sha=digest(f);relative=f.relative_to(D)
  if size<1024*1024:
   # Preserve even unique scripts/packets/raw before removing the Windows staging copy.
   target=save/'unique-windows'/relative;target.parent.mkdir(parents=True,exist_ok=True)
   if target.exists():assert digest(target)==sha
   else:shutil.copyfile(f,target);assert digest(target)==sha
   action=dict(windows=str(f),bytes=size,sha256=sha,action='archived_small_then_removed',retained=str(target))
  else:
   candidates=local[size]
   def rank(x):
    z=str(x);return (0 if number in z else 1,0 if x.name==f.name else 1,0 if z.startswith(str(R/'out')) else 1,z)
   candidates=sorted(candidates,key=rank)
   target=None
   for candidate in candidates:
    if digest(candidate)==sha:target=candidate;break
   if target is None:
    actions.append(dict(windows=str(f),bytes=size,sha256=sha,action='retained_unmatched_large'));checkpoint();continue
   action=dict(windows=str(f),bytes=size,sha256=sha,action='removed_verified_duplicate',retained=str(target))
  f.unlink();actions.append(action);checkpoint()
 for directory in sorted([x for x in folder.rglob('*') if x.is_dir()],key=lambda x:len(x.parts),reverse=True):
  if not any(directory.iterdir()):directory.rmdir()
 if not any(folder.iterdir()):folder.rmdir()
 print(folder.name,'processed; freed MiB',round(sum(x['bytes'] for x in actions if x['action']!='retained_unmatched_large')/1024**2,1),flush=True)
after=shutil.disk_usage('/mnt/d');removed=[x for x in actions if x['action']!='retained_unmatched_large'];summary=dict(deleted_files=len(removed),verified_duplicate_bytes=sum(x['bytes'] for x in removed if x['action']=='removed_verified_duplicate'),small_archived_bytes=sum(x['bytes'] for x in removed if x['action']=='archived_small_then_removed'),retained_unmatched_files=len(actions)-len(removed),before_free_bytes=before.free,after_free_bytes=after.free,observed_free_increase_bytes=after.free-before.free,other_windows_directories_touched=False,WSL_VHD_touched=False,current_rescue_preserved=True)
(report/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
