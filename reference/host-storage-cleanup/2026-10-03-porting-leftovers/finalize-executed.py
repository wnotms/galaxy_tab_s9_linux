import gzip,hashlib,json,os,shutil,tarfile
from collections import defaultdict
from pathlib import Path
ROOT=Path.cwd();R=ROOT/'reference/host-storage-cleanup/2026-10-03-porting-leftovers';S=ROOT/'.work/host-storage-cleanup/2026-10-03-porting-leftovers'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
with gzip.open(R/'manifest.json.gz','rt') as f:m=json.load(f)
v=json.loads((R/'validation.json').read_text())
with gzip.open(ROOT/'reference/host-storage-cleanup/2026-10-03-image-retention/manifest.json.gz','rt') as f:prior=json.load(f)
removed_files={x['original'] for x in m['compressed_files']}
removed_prefixes={x['original']+'/' for k in ('sources','modules','adbd_jobs','compressed_debug_trees') for x in m[k]}
shared=defaultdict(list)
for x in prior['untouched_nonimages']:
 if x['nlink']>1 and (x['path'] in removed_files or any(x['path'].startswith(p) for p in removed_prefixes)):
  shared[x['inode']].append(x)
correction=sum((len(xs)-1)*xs[0]['allocated'] for xs in shared.values())
m['hardlink_accounting']={'metadata_source':'reference/host-storage-cleanup/2026-10-03-image-retention/manifest.json.gz','removed_shared_inode_groups':list(shared.values()),'summed_allocation_overcount_bytes':correction}
extra=[];start=os.statvfs(ROOT)
for p in sorted((ROOT/'.work/d-drive-test-archive').rglob('*modules.tar')):
 h=sha(p);matches=list((S/'compressed-files').glob(h+'-*'))
 if matches:dst=matches[0]
 else:
  dst=S/'compressed-files'/(h+'-'+p.name+'.gz')
  with p.open('rb') as src,dst.open('wb') as raw:
   with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=3,mtime=0) as gz:shutil.copyfileobj(src,gz,8*1024*1024)
 with gzip.open(dst,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==h
 row={'original':str(p.relative_to(ROOT)),'kind':'migration module tar','bytes':p.stat().st_size,'allocated_bytes':p.stat().st_blocks*512,'sha256':h,'retained':str(dst.relative_to(ROOT)),'retained_sha256':sha(dst),'byte_exact_reconstruction_verified':True}
 extra.append(row)
 (R/'additional-cleanup.json').write_text(json.dumps(extra,indent=2)+'\n');p.unlink()
for name in ('kout-pcie-off','kout-power-trace'):
 base=ROOT/'.work/build'/name
 assert not base.is_symlink() and {p.name for p in base.iterdir()}=={'Image.gz','kernel.release','sm8550-samsung-gts9wifi.dtb'}
 records={p.name:{'bytes':p.stat().st_size,'allocated_bytes':p.stat().st_blocks*512,'sha256':sha(p)} for p in base.iterdir()}
 dst=S/(name+'-metadata.tar.gz')
 with tarfile.open(dst,'w:gz') as tf:
  for n in ('kernel.release','sm8550-samsung-gts9wifi.dtb'):tf.add(base/n,arcname=n)
 with tarfile.open(dst) as tf:
  actual={x.name:{'bytes':x.size,'sha256':hashlib.file_digest(tf.extractfile(x),'sha256').hexdigest()} for x in tf if x.isfile()}
 assert actual=={n:{'bytes':r['bytes'],'sha256':r['sha256']} for n,r in records.items() if n!='Image.gz'}
 extra.append({'original':str(base.relative_to(ROOT)),'kind':'obsolete image staging','allocated_bytes':sum(x['allocated_bytes'] for x in records.values()),'members':records,'retained':str(dst.relative_to(ROOT)),'retained_sha256':sha(dst),'image_content_retained':False})
 (R/'additional-cleanup.json').write_text(json.dumps(extra,indent=2)+'\n');shutil.rmtree(base)
saved=sum(p.stat().st_blocks*512 for p in S.rglob('*') if p.is_file() and not p.is_symlink())
extra_removed=sum(x['allocated_bytes'] for x in extra)
v['summed_allocation_hardlink_overcount_bytes']=correction
v['removed_original_unique_allocated_bytes']=v['removed_original_allocated_bytes']-correction+extra_removed
v['saved_reconstruction_allocated_bytes']=saved
v['net_file_allocated_byte_reduction']=v['removed_original_unique_allocated_bytes']-saved
v['additional_removed_migration_tars']=sum(x['kind']=='migration module tar' for x in extra)
v['additional_removed_image_staging_directories']=sum(x['kind']=='obsolete image staging' for x in extra)
end=os.statvfs(ROOT);v['additional_observed_linux_available_byte_change']=end.f_bavail*end.f_frsize-start.f_bavail*start.f_frsize
with gzip.open(R/'manifest.json.gz','wt') as f:json.dump(m,f,indent=2)
(R/'validation.json').write_text(json.dumps(v,indent=2)+'\n')
print(json.dumps(v))
