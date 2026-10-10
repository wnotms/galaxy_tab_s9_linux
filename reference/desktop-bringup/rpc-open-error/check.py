import hashlib, json, pathlib, shutil, tarfile, subprocess, ast
R=pathlib.Path.cwd(); B=R/'out/rpc-open-error/build'; E=R/'reference/desktop-bringup/rpc-open-error'
E.mkdir(parents=True,exist_ok=True)
def save(n,v): (E/n).write_text(json.dumps(v,indent=2)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
modes=['missing','present','permission','io-error','readonly-write','unknown-env','bad-mode','missing-dir','repeat-missing']
rows=[]
for profile in ['original','final']:
 for mode in modes:
  text=(B/f'{profile}-{mode}.stdout').read_text(); stderr=(B/f'{profile}-{mode}.stderr').read_text()
  row=json.loads(text.splitlines()[-1]); expected=(69 if profile=='final' else 1) if mode in ['missing','repeat-missing'] else 0 if mode=='present' else 14 if mode in ['unknown-env','bad-mode'] else 1
  assert row==dict(case=mode,status=expected,loops=1024 if mode=='repeat-missing' else 1,remaining_fds=1),row
  if mode=='missing': assert ('No such file or directory' if profile=='final' else 'Input/output error') in stderr
  if profile=='final' and mode=='permission': assert 'Permission denied' in stderr
  if profile=='final' and mode=='readonly-write': assert 'Read-only file system' in stderr
  assert 'runtime error' not in stderr
  rows.append(dict(profile=profile,**row,asserted=True,stdout_sha256=sha(B/f'{profile}-{mode}.stdout'),stderr_sha256=sha(B/f'{profile}-{mode}.stderr')))
  for suffix in ['stdout','stderr']: shutil.copyfile(B/f'{profile}-{mode}.{suffix}',E/f'{profile}-{mode}.{suffix}')
assert (B/'original-present.stdout').read_bytes()==(B/'final-present.stdout').read_bytes()
assert (B/'payload').read_bytes()==b'private-payload'
tests=[json.loads(x) for x in (B/'build/meson-logs/testlog.json').read_text().splitlines()]
assert len(tests)==2 and all(x['result']=='OK' and x['returncode']==0 for x in tests)
source=json.loads((B/'OPEN_ERROR_SOURCE.json').read_text()); files={str(p.relative_to(B/'work/hexagonrpc')):sha(p) for p in (B/'work/hexagonrpc').rglob('*') if p.is_file() and p.name!='OPEN_ERROR_SOURCE.json'}
assert files==source['source_hashes'] and len(files)==56
save('ARM64_CASES.json',dict(executed=True,cases=rows,successful=True,real_C_and_VFS=True,hardware_or_DSP=False))
for src,dst in [('BUILD.json','BUILD.json'),('build.log','build.log'),('OPEN_ERROR_SOURCE.json','OPEN_ERROR_SOURCE.json'),('compiler.txt','compiler.txt'),('packages.tsv','packages.tsv'),('build/meson-logs/testlog.json','upstream-tests.jsonl'),('build/meson-logs/testlog.txt','upstream-tests.txt')]: shutil.copyfile(B/src,E/dst)
fileset={'hexagonrpcd':B/'stage/usr/bin/hexagonrpcd','libhexagonrpc.so.0.4':B/'stage/usr/lib/aarch64-linux-gnu/libhexagonrpc.so.0.4','COPYING':B/'work/hexagonrpc/COPYING'}
assert sha(fileset['libhexagonrpc.so.0.4'])=='1be44d2fe0c9b5ca785ef27730fba586a7f678f82f91cfbfb01613b3dad76f6e'
assert sha(fileset['hexagonrpcd'])!='bf0a9fa112f9182b808324c131a2373ee2b98cc6600c56aa07378b1ea754b115'
archive=R/'out/rpc-open-error/runtime.tar.gz'
with tarfile.open(archive,'w:gz') as tf:
 for name,p in fileset.items(): tf.add(p,arcname=name,recursive=False)
with tarfile.open(archive) as tf:
 assert sorted(tf.getnames())==sorted(fileset)
 for m in tf.getmembers(): assert m.isfile() and hashlib.sha256(tf.extractfile(m).read()).hexdigest()==sha(fileset[m.name])
save('RUNTIME.json',dict(archive=str(archive.relative_to(R)),sha256=sha(archive),bytes=archive.stat().st_size,files={n:sha(p) for n,p in fileset.items()},installed=False))
save('ELF.json',dict(files={n:subprocess.check_output(['readelf','-h',str(p)],text=True) for n,p in fileset.items() if n!='COPYING'}))
py=['userspace/sensors/rpc_open_error_profile.py','tests/test_rpc_open_error_profile.py']
for p in py: ast.parse((R/p).read_text(),filename=p)
subprocess.run(['sh','-n','userspace/sensors/compile-rpc-open-error.sh'],check=True)
save('SYNTAX.json',dict(python_AST=py,shell='sh -n userspace/sensors/compile-rpc-open-error.sh',successful=True))
save('first-native-fixture-stop.json',dict(reason='Initial host fixture binary path final collided with prepared source directory final. Linker failure was a fixture pathname error; binary outputs renamed to original-harness/final-harness.',raw_compiler_stderr_available=False,device_operations=False))
print(json.dumps(dict(cases=len(rows),upstream_tests=len(tests),compiled_sources=len(files),runtime={n:sha(p) for n,p in fileset.items()}),indent=2))
