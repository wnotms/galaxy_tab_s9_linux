from pathlib import Path
import datetime,hashlib,json,os,shutil,struct,subprocess,tarfile
root=Path.cwd();p=root/'reference/boot-tests/test-249-no-dcc-production/validation';out=root/'out/test249';kernel=root/'out/kernel-no-dcc-production';bundle=root/'out/boot-bundle-no-dcc-production'
assert json.loads((p/'build.json').read_text())['status']==0
for name in ('vmlinux','System.map','Module.symvers'):
 shutil.copyfile(root/'.work/build/linux-out'/name,out/name)
with (p/'build-check.txt').open('wb') as f:
 subprocess.run(['python3',str(out/'check_build.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
# Read-only ELF notes extraction; objcopy without an output can mutate the input.
raw=(out/'vmlinux').read_bytes();shoff=struct.unpack_from('<Q',raw,40)[0];size,num,idx=struct.unpack_from('<HHH',raw,58)
rows=[struct.unpack_from('<IIQQQQIIQQ',raw,shoff+i*size) for i in range(num)]
st=rows[idx];names=raw[st[4]:st[4]+st[5]]
notes=[r for r in rows if names[r[0]:].split(b'\0',1)[0]==b'.notes'];assert len(notes)==1
r=notes[0];(out/'kernel-notes.bin').write_bytes(raw[r[4]:r[4]+r[5]])
# Save the actual compiled chain, not just source text or symbol existence.
defined=subprocess.check_output(['llvm-nm','--defined-only',str(out/'vmlinux')],text=True)
assert not any('hvc_dcc' in line or line.split()[-1]=='hvc_write' for line in defined.splitlines()), 'DCC/HVC write code still linked'
for name in ('__csd_lock_wait','csdlock_debug_enabled','gts9_lastactivity','gts9_pnmi_test'):
 assert not any(name in line for line in defined.splitlines()),name
(p/'diagnostic-absence.json').write_text(json.dumps({'DCC_HVC_write_code_absent':True,'CSD_debug_code_absent':True,'lastactivity_and_calibration_absent':True},indent=2)+'\n')
release=(kernel/'kernel.release').read_text().strip()
cmd=['depmod','-e','-E',str(out/'Module.symvers'),'-b',str(kernel/'modules-root'),release]
r=subprocess.run(cmd,capture_output=True);(p/'module-symbol-check.txt').write_bytes(r.stdout+r.stderr)
assert r.returncode==0 and not r.stdout and not r.stderr
base=kernel/'modules-root/lib/modules';module_root=base/release
files={str(f.relative_to(base)):{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(module_root.rglob('*')) if f.is_file() and not f.is_symlink()}
assert len(files)==181
archive=out/'candidate-modules.tar'
with tarfile.open(archive,'w') as tar:tar.add(module_root,arcname=release)
with tarfile.open(archive) as tar:
 actual={m.name:{'bytes':m.size,'sha256':hashlib.sha256(tar.extractfile(m).read()).hexdigest()} for m in tar if m.isfile()}
 assert actual==files
 links=[m for m in tar.getmembers() if m.issym()];assert len(links)==1 and links[0].name==release+'/build' and links[0].linkname==str(root/'.work/build/linux-out')
checks=''.join(v['sha256']+'  '+name.removeprefix(release+'/')+'\n' for name,v in files.items())
(out/'candidate-module-checksums.txt').write_text(checks);(p/'candidate-module-checksums.txt').write_text(checks)
(p/'candidate-modules.json').write_text(json.dumps({'tar_path':str(archive.relative_to(root)),'tar_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'file_count':len(files),'all_tar_file_hashes_verified':True,'files':files},indent=2)+'\n')
with (p/'module-swap-check.txt').open('wb') as f:subprocess.run(['python3',str(p/'check_module_swap.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
env=os.environ|{'KERNEL_OUT_DIR':str(kernel),'MKBOOTIMG':str(root/'.work/tools/mkbootimg.py'),'AVBTOOL':str(root/'.work/tools/avbtool.py')}
command=['bash','scripts/build-boot-bundle.sh','--initramfs',str(out/'init-unpack/ramdisk'),'--cmdline','boot/cmdline.example.txt','--bootconfig','boot/bootconfig.example.txt','--out',str(bundle)]
meta={'command':command,'environment':{k:env[k] for k in ('KERNEL_OUT_DIR','MKBOOTIMG','AVBTOOL')},'utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat()}
with (p/'package.txt').open('wb') as f:r=subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT)
meta['status']=r.returncode;(p/'package.json').write_text(json.dumps(meta,indent=2)+'\n');assert r.returncode==0
command=['bash','scripts/validate-boot-bundle.sh','--dir',str(bundle),'--kernel-out',str(kernel),'--cmdline','boot/cmdline.example.txt','--bootconfig','boot/bootconfig.example.txt']
with (p/'bundle-validation.txt').open('wb') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
(p/'bundle-validation.json').write_text(json.dumps({'command':command,'status':r.returncode},indent=2)+'\n');assert r.returncode==0
for name in ('init_boot.img','dtbo.img'):
 assert (bundle/name).read_bytes()==(root/'out/boot-bundle-pnmi-bbm'/name).read_bytes()
(p/'package-artifacts.json').write_text(json.dumps({str(f.relative_to(root)):{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(bundle.iterdir()) if f.is_file()},indent=2)+'\n')
print('PASS: exact config/module audit, module rollback rehearsal, production diagnostic absence, package and validator. No flash.',flush=True)
