import json,hashlib,tarfile,shutil
from pathlib import Path
R=Path('/home/ms/Samsung/galaxy_tab_s9_linux');report=R/'reference/host-storage-cleanup/2026-10-02';d=json.loads((report/'manifest.json').read_text());actions=d['actions']
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def members(path):
 data={};links={}
 with tarfile.open(path) as t:
  for x in t:
   name=x.name.removeprefix('lib/modules/')
   if x.isfile():
    h=hashlib.sha256();f=t.extractfile(x)
    for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    if name in data:raise ValueError('duplicate archive member')
    data[name]=(x.size,h.hexdigest())
   elif x.issym():links[name]=x.linkname
   elif not x.isdir():raise ValueError('unexpected archive member')
 return data,links
for a in actions:
 if a['action']!='retained_unmatched_large':continue
 f=Path(a['windows']);target=None
 if f.name=='kallsyms.txt':
  n=f.parts[f.parts.index('gts9-active')+1].replace('gts9-test','test-');roots=list((R/'reference/boot-tests').glob(n+'-*'))
  candidates=[z for root in roots for z in root.rglob(f.name)]
  for z in candidates:
   if sha(z)==a['sha256']:target=z;break
  if target:a.update(action='removed_verified_duplicate',retained=str(target));f.unlink()
 else:
  n=f.parent.name[-3:];target=R/('out/kernel-gts9wifi/modules-sm5714-stage1.tar.gz' if n=='252' else 'out/kernel-container-candidate/modules-container-candidate.tar.gz')
  if not target.exists():continue
  actual,links=members(f);expected,wlinks=members(target)
  if actual!=expected:continue
  allowed='/home/ms/Samsung/galaxy_tab_s9_linux/.work/build/linux-out'
  if any(not k.endswith('/build') or v!=allowed for k,v in (links|wlinks).items()):continue
  a.update(action='removed_verified_module_content_duplicate',retained=str(target),retained_archive_sha256=sha(target),matched_file_count=len(actual),matched_file_names_and_bytes=True,container_metadata_identical=False,reason='obsolete uncompressed staging tar; exact module file set retained in WSL compressed archive; directory/tar metadata excluded')
  f.unlink()
for folder in Path('/mnt/d/android/gts9-active').glob('gts9-test*'):
 if folder.name in ('gts9-test263','gts9-test292'):continue
 for z in sorted([x for x in folder.rglob('*') if x.is_dir()],key=lambda x:len(x.parts),reverse=True):
  if not any(z.iterdir()):z.rmdir()
 if not any(folder.iterdir()):folder.rmdir()
# Retain unique records in the tracked archive too; metadata/scripts already saved under .work.
byname={}
for f in (R/'reference/boot-tests').rglob('*'):
 if f.is_file() and f.suffix in ('.txt','.stderr','.stats','.filter','.format','.json'):byname.setdefault(f.name,[]).append(f)
preserved=[]
for a in actions:
 if a['action']!='archived_small_then_removed':continue
 f=Path(a['retained'])
 if f.suffix not in ('.txt','.stderr','.stats','.filter','.format','.json'):continue
 target=next((x for x in byname.get(f.name,[]) if x.stat().st_size==a['bytes'] and sha(x)==a['sha256']),None)
 if target:a['tracked_evidence_copy']=str(target)
 else:
  relative=f.relative_to(R/'.work/host-storage-cleanup/2026-10-02/unique-windows');target=report/'preserved'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target);assert sha(target)==a['sha256'];a['tracked_evidence_copy']=str(target);preserved.append(str(target.relative_to(report)))
(report/'manifest.json').write_text(json.dumps(d,indent=2)+'\n');after=shutil.disk_usage('/mnt/d');deleted=[x for x in actions if x['action']!='retained_unmatched_large']
s=dict(deleted_files=len(deleted),removed_staging_bytes=sum(x['bytes'] for x in deleted),verified_byte_duplicates=sum(x['bytes'] for x in deleted if x['action']=='removed_verified_duplicate'),verified_module_payload_duplicates=sum(x['bytes'] for x in deleted if x['action']=='removed_verified_module_content_duplicate'),small_archived_bytes=sum(x['bytes'] for x in deleted if x['action']=='archived_small_then_removed'),retained_unmatched_files=len(actions)-len(deleted),before_free_bytes=d['before_free_bytes'],after_free_bytes=after.free,observed_free_increase_bytes=after.free-d['before_free_bytes'],preserved_unique_tracked_records=preserved,other_windows_directories_touched=False,WSL_VHD_touched=False,current263_292_stock_rescue_and_ADB_preserved=True)
(report/'summary.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s,indent=2))
