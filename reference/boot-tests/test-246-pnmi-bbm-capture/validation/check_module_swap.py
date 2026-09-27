"""Local filesystem rehearsal only; never invokes ADB, mounts or device writes."""
from pathlib import Path
import hashlib,json,shutil,subprocess,tarfile,tempfile

out=Path('out/test246').resolve()
here=Path(__file__).resolve().parent
release='7.2.0-rc3-gts9wifi-dirty'
script=here/'module-swap.sh'
orig=here/'original-module-checksums.txt'
cand=here/'candidate-module-checksums.txt'
def read_checksums(path):
 return {line.split(maxsplit=1)[1].strip():line.split()[0] for line in path.read_text().splitlines()}
old,new=read_checksums(orig),read_checksums(cand)
results=[]
with tempfile.TemporaryDirectory(prefix='gts9-module-swap-') as d:
 root=Path(d);base=root/'usr/lib/modules';base.mkdir(parents=True)
 (root/'etc').mkdir();(root/'etc/machine-id').write_text('3c2a1b8f2d624db4b5ffdc836050fcf6\n')
 backup=json.loads((here/'module-backup.json').read_text())
 assert hashlib.sha256((out/'original-modules.tar').read_bytes()).hexdigest()==backup['backup_sha256']
 candidate=json.loads((here/'candidate-modules.json').read_text())
 assert hashlib.sha256((out/'candidate-modules.tar').read_bytes()).hexdigest()==candidate['tar_sha256']
 # These owned archives have separately verified paths, hashes and a build symlink.
 with tarfile.open(out/'original-modules.tar') as t:
  for m in t:
   assert '..' not in Path(m.name).parts and (m.name==release or m.name.startswith(release+'/'))
  t.extractall(base,filter='fully_trusted')
 def hashes():
  return {str(f.relative_to(base/release)):hashlib.sha256(f.read_bytes()).hexdigest()
          for f in (base/release).rglob('*') if f.is_file() and not f.is_symlink()}
 def run(mode,expected):
  return subprocess.run(['sh',str(script),str(root),mode,str(expected),
                         str(out/'candidate-modules.tar'),str(orig)],capture_output=True)
 assert hashes()==old
 bad=root/'bad-checksums';bad.write_text(cand.read_text().replace(next(iter(new.values())),'0'*64))
 r=run('install',bad)
 assert r.returncode!=0 and hashes()==old and not (base/'.gts9-test246-original').exists()
 results.append({'case':'corrupt candidate manifest stops before replacing originals','status':'passed'})
 shutil.rmtree(base/'.gts9-test246-stage')
 for mode,expected,target in [('install',cand,new),('restore',orig,old)]:
  r=run(mode,expected);assert r.returncode==0,(mode,r.stderr)
  assert hashes()==target
  results.append({'case':mode+' all 181 files verified','status':'passed'})
 shutil.rmtree(base/'.gts9-test246-tested')
 (base/release).rename(base/'.gts9-test246-original')
 r=run('restore',orig);assert r.returncode==0 and hashes()==old
 results.append({'case':'restore after interrupted first install rename','status':'passed'})
result={'device_modified':False,'cases':results}
(here/'module-swap-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
