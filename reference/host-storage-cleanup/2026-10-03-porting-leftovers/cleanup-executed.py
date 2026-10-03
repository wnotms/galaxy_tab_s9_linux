"""One-time cleanup of verified redundant porting files; no device commands."""
import gzip, hashlib, json, os, shutil, subprocess, tarfile
from pathlib import Path
ROOT=Path.cwd().resolve()
assert ROOT==Path('/home/ms/Samsung/galaxy_tab_s9_linux')
SAVE=ROOT/'.work/host-storage-cleanup/2026-10-03-porting-leftovers'
REPORT=ROOT/'reference/host-storage-cleanup/2026-10-03-porting-leftovers'
SOURCE_NAMES=['linux-src-container','linux-src-poweroff-trace','linux-src-sm5714-stage2']
PROTECTED_MODULES={'kernel-gts9wifi','kernel-sm5714-stage2','kernel-x710-263-passive',
 'kernel-x710-272-passive','kernel-x710-290-passive','kernel-x710-299-passive',
 'kernel-x710-301-passive','kernel-x710-302-passive','kernel-x710-303-policy',
 'kernel-x710-305-adc-condition','kernel-x710-308-passive'}
manifest={'sources':[],'modules':[],'adbd_jobs':[],'compressed_files':[],
 'compressed_debug_trees':[],'protected_module_directories':sorted(PROTECTED_MODULES)}

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def walk(base):
 for d,ds,fs in os.walk(base,followlinks=False):
  for n in ds[:]:
   p=Path(d)/n
   if p.is_symlink():ds.remove(n);yield p
  for n in fs:yield Path(d)/n

def info(p):
 if p.is_symlink():return {'symlink':os.readlink(p)}
 s=p.stat();return {'bytes':s.st_size,'sha256':sha(p)}
def filemap(base):return {p.relative_to(base).as_posix():info(p) for p in walk(base)}
def usage(base):
 return sum(p.stat().st_blocks*512 for p in walk(base) if not p.is_symlink())
def guard():
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   cmd=(p/'cmdline').read_bytes().split(b'\0');exe=Path(os.fsdecode(cmd[0])).name
   cwd=(p/'cwd').resolve()
  except (OSError,IndexError):continue
  if exe in ('make','clang','clang-22','ld.lld','ninja','sparse'):
   raise RuntimeError('Build process running: '+str(p))
  if any((ROOT/'.work/build'/n)==cwd or (ROOT/'.work/build'/n) in cwd.parents for n in SOURCE_NAMES):
   raise RuntimeError('Source worktree in use: '+str(cwd))
def journal():
 with gzip.open(REPORT/'manifest.json.gz','wt') as f:json.dump(manifest,f,indent=2)
def packed(base, paths, dest):
 wanted={str(p):info(base/p) for p in paths}
 with dest.open('wb') as raw:
  with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=3,mtime=0) as gz:
   with tarfile.open(fileobj=gz,mode='w',dereference=False) as tf:
    for rel in paths:tf.add(base/rel,arcname=str(rel),recursive=False)
 assert readtar(dest,normalize=False)==wanted,dest
 return {'path':str(dest.relative_to(ROOT)),'bytes':dest.stat().st_size,'sha256':sha(dest),'members':wanted}
def readtar(path,normalize=True):
 result={}
 with tarfile.open(path,'r:*') as tf:
  for m in tf:
   if m.isdir():continue
   n=m.name
   if normalize:
    parts=Path(n).parts
    idx=next((i for i,x in enumerate(parts) if x.startswith('7.2.0-rc3-gts9wifi')),None)
    if idx is None:raise RuntimeError('Unknown archive prefix: '+n)
    n='/'.join(parts[idx:])
   if m.isfile() or m.islnk():
    f=tf.extractfile(m);result[n]={'bytes':m.size if m.isfile() else None,'sha256':hashlib.file_digest(f,'sha256').hexdigest()}
    if m.islnk():result[n]['bytes']=tf.getmember(m.linkname).size
   elif m.issym():result[n]={'symlink':m.linkname}
   else:raise RuntimeError('Unknown member '+m.name)
 return result

def snapshot(excluded):
 result={}
 for area in ('out','reference'):
  for p in walk(ROOT/area):
   if REPORT in p.parents or 'test-308-ordinary-program-recovery' in p.parts:continue
   if any(p==x or x in p.parents for x in excluded):continue
   result[p.relative_to(ROOT).as_posix()]=info(p)
 # Current sources / generated identities must remain byte-identical.
 for p in list((ROOT/'kernel').rglob('*'))+list((ROOT/'tests').glob('*.py')):
  if p.is_file() and not p.is_symlink():result[p.relative_to(ROOT).as_posix()]=info(p)
 for b in (ROOT/'.work/build').glob('linux-out*'):
  for rel in ('.config','vmlinux','Module.symvers','include/config/auto.conf'):
   p=b/rel
   if p.is_file():result[p.relative_to(ROOT).as_posix()]=info(p)
 return result

def archive_gzip_file(p):
 h=sha(p);dest=SAVE/'compressed-files'/(h+'-'+p.name+'.gz')
 dest.parent.mkdir(exist_ok=True)
 if not dest.exists():
  with p.open('rb') as src,dest.open('wb') as raw:
   with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=3,mtime=0) as gz:shutil.copyfileobj(src,gz,8*1024*1024)
 with gzip.open(dest,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==h
 row={'original':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,
      'allocated_bytes':p.stat().st_blocks*512,'sha256':h,
      'archive':dest.relative_to(ROOT).as_posix(),'archive_sha256':sha(dest)}
 manifest['compressed_files'].append(row);journal();p.unlink()
 print('Compressed historical file',row['original'],flush=True)

# Module candidates: only old inactive package expansions, never current/default providers.
module_roots=[]
for out in sorted((ROOT/'out').glob('kernel-*')):
 p=out/'modules-root'
 if p.is_dir() and out.name not in PROTECTED_MODULES:module_roots.append(p)
old_debug_files=sorted(p for p in (ROOT/'out').rglob('vmlinux') if p.is_file())
old_tars=sorted(p for p in (ROOT/'out').glob('test*/**/*modules.tar') if p.is_file())
excluded=module_roots+old_debug_files+old_tars
start=os.statvfs(ROOT);guard()
protected=snapshot(excluded)
with gzip.open(REPORT/'protected-before.json.gz','wt') as f:json.dump(protected,f,indent=2)
print('Protected hash snapshot complete',len(protected),flush=True)

# Preserve exact prepared-source overlays and prove they reconstruct against pinned HEAD.
for name in SOURCE_NAMES:
 guard();src=ROOT/'.work/build'/name
 for b in (ROOT/'.work/build').glob('linux-out*'):
  link=b/'source'
  assert not link.is_symlink() or link.resolve()!=src,'Still referenced: '+str(b)
 head=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
 assert head=='a13c140cc289c0b7b3770bce5b3ad42ab35074aa'
 patch=subprocess.check_output(['git','-C',str(src),'diff','HEAD','--binary'])
 folder=SAVE/name;folder.mkdir()
 patchfile=folder/'tracked.patch';patchfile.write_bytes(patch)
 env=os.environ.copy();env['GIT_INDEX_FILE']=str(folder/'verify.index')
 subprocess.run(['git','-C',str(src),'read-tree',head],env=env,check=True)
 if patch:subprocess.run(['git','-C',str(src),'apply','--cached','--binary',str(patchfile)],env=env,check=True)
 changed=subprocess.check_output(['git','-C',str(src),'diff','HEAD','--name-only','-z']).split(b'\0')
 tracked={}
 for raw in changed:
  if not raw:continue
  rel=os.fsdecode(raw);p=src/rel
  if p.exists():
   blob=subprocess.check_output(['git','-C',str(src),'show',':'+rel],env=env)
   assert hashlib.sha256(blob).hexdigest()==sha(p),p
   tracked[rel]=info(p)
  else:
   r=subprocess.run(['git','-C',str(src),'cat-file','-e',':'+rel],env=env,capture_output=True)
   assert r.returncode!=0;tracked[rel]={'deleted':True}
 (folder/'verify.index').unlink()
 others=[Path(os.fsdecode(x)) for x in subprocess.check_output(['git','-C',str(src),'ls-files','--others','-z']).split(b'\0') if x]
 archive=packed(src,others,folder/'untracked.tar.gz')
 row={'original':src.relative_to(ROOT).as_posix(),'head':head,'allocated_bytes':usage(src),
      'patch':patchfile.relative_to(ROOT).as_posix(),'patch_sha256':sha(patchfile),
      'changed_tracked_files':tracked,'untracked_archive':archive,
      'reconstruction_in_isolated_index_verified':True,'force_reason':'Prepared overlays are archived and verified; no active consumer remains.'}
 manifest['sources'].append(row);journal();guard()
 assert subprocess.check_output(['git','-C',str(src),'diff','HEAD','--binary'])==patch
 subprocess.run(['git','-C',str(ROOT/'.work/linux-mainline'),'worktree','remove','--force',str(src)],check=True)
 subprocess.run(['git','-C',str(ROOT/'.work/linux-mainline'),'cat-file','-e',head+'^{commit}'],check=True)
 assert not src.exists();print('Removed obsolete prepared source',name,flush=True)

# Verify the complete regular-file set against a retained package, then discard duplicate expansions.
for base in module_roots:
 guard();actual=filemap(base)
 regular={k:v for k,v in actual.items() if 'sha256' in v}
 # Normalize the lib/modules prefix; keep original file names in the manifest.
 normalized={k.removeprefix('lib/modules/'):v for k,v in regular.items()}
 archives=list(base.parent.glob('*modules*.tar.gz'))
 verified=None
 for archive in archives:
  archived=readtar(archive)
  archived_regular={k:v for k,v in archived.items() if 'sha256' in v}
  if archived_regular==normalized:verified=archive;break
 if verified is None:
  # Rare historical profiles without a full existing install archive.
  archive=SAVE/(base.parent.name+'-modules.tar.gz')
  packed(base,[Path(k) for k in regular],archive);verified=archive
 row={'original':base.relative_to(ROOT).as_posix(),'allocated_bytes':usage(base),
      'archive':verified.relative_to(ROOT).as_posix(),'archive_sha256':sha(verified),
      'members':actual,'complete_regular_file_set_verified':True}
 manifest['modules'].append(row);journal()
 assert filemap(base)==actual
 shutil.rmtree(base);print('Removed archived module expansion',base.parent.name,flush=True)

# adbd mktemp jobs are independent extraction/build leftovers. Keep deltas to retained canonical source.
canonical=ROOT/'.work/adbd-reconnect-build/source';canon=filemap(canonical)
for job in sorted((ROOT/'.work').glob('adbd-reconnect.??????')):
 guard();src=job/'source';actual=filemap(src)
 unique=[Path(k) for k,v in actual.items() if canon.get(k)!=v]
 delta=packed(src,unique,SAVE/(job.name+'-source-delta.tar.gz'))
 outer=[p for p in walk(job) if src not in p.parents and p!=src]
 # Outer source tarballs must have identical copies in the retained downloads/cache.
 counterparts={}
 for p in outer:
  if p.is_symlink():raise RuntimeError('Unexpected outer symlink '+str(p))
  h=sha(p);matches=[q for area in (ROOT/'.work/downloads',ROOT/'.work/adbd-reconnect-source')
                  for q in area.rglob(p.name) if q.is_file() and sha(q)==h]
  assert matches,'No retained source-package counterpart: '+str(p)
  counterparts[p.relative_to(job).as_posix()]={'sha256':h,'retained':matches[0].relative_to(ROOT).as_posix()}
 row={'original':job.relative_to(ROOT).as_posix(),'allocated_bytes':usage(job),
      'canonical_source':canonical.relative_to(ROOT).as_posix(),'original_members':actual,
      'source_delta_archive':delta,'source_package_counterparts':counterparts}
 manifest['adbd_jobs'].append(row);journal()
 assert filemap(src)==actual;shutil.rmtree(job)
 print('Removed adbd mktemp job',job.name,'retained differing source files',len(unique),flush=True)

# Preserve historical ELF symbols and original tar bytes in one compressed copy per hash.
for p in old_debug_files+old_tars:archive_gzip_file(p)

# Repack previous raw debug retention once; this is not another full build-tree backup.
old=ROOT/'.work/host-storage-cleanup/2026-10-02-reclaim/retained-build-inputs'
for base in sorted(old.iterdir()):
 if not base.is_dir():continue
 guard();actual=filemap(base)
 archive=packed(base,[Path(k) for k in actual],SAVE/(base.name+'-old-debug.tar.gz'))
 row={'original':base.relative_to(ROOT).as_posix(),'allocated_bytes':usage(base),'archive':archive}
 manifest['compressed_debug_trees'].append(row);journal()
 assert filemap(base)==actual;shutil.rmtree(base)
 print('Compressed previous raw debug retention',base.name,flush=True)
if old.exists() and not any(old.iterdir()):old.rmdir()

assert snapshot(excluded)==protected,'Protected files changed'
# Verify all surviving reconstruction artifacts once more.
for row in manifest['sources']:
 assert sha(ROOT/row['patch'])==row['patch_sha256']
for key in ('modules','compressed_files'):
 for row in manifest[key]:assert sha(ROOT/row['archive'])==row['archive_sha256']
for row in manifest['adbd_jobs']:
 a=row['source_delta_archive'];assert readtar(ROOT/a['path'],normalize=False)==a['members']
for row in manifest['compressed_debug_trees']:
 a=row['archive'];assert readtar(ROOT/a['path'],normalize=False)==a['members']
new_saved=usage(SAVE)
removed=sum(row['allocated_bytes'] for key in ('sources','modules','adbd_jobs','compressed_files','compressed_debug_trees') for row in manifest[key])
end=os.statvfs(ROOT)
result={'removed_source_worktrees':len(manifest['sources']),'removed_module_expansions':len(manifest['modules']),
 'removed_adbd_mktemp_jobs':len(manifest['adbd_jobs']),'compressed_historical_files':len(manifest['compressed_files']),
 'repacked_debug_trees':len(manifest['compressed_debug_trees']),'removed_original_allocated_bytes':removed,
 'saved_reconstruction_allocated_bytes':new_saved,'net_file_allocated_byte_reduction':removed-new_saved,
 'observed_linux_available_byte_change':end.f_bavail*end.f_frsize-start.f_bavail*start.f_frsize,
 'protected_files_hash_verified':len(protected),'all_reconstruction_archives_verified':True,
 'kernel_build':{'executed':False},'host_regression':{'executed':False},'device_commands':{'executed':False},'ci':{'executed':False}}
(REPORT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');journal()
print(json.dumps(result),flush=True)
