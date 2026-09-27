from pathlib import Path
import subprocess,hashlib,json,shutil,os,datetime
root=Path.cwd();p=root/'reference/boot-tests/test-241-pnmi-calibration';validation=p/'validation'
assert 'Build complete' in Path('out/test241/build.log').read_text()
shutil.copy2('out/test241/build.log',validation/'build-initial.txt')
source=Path('out/test241/gts9_pnmi_test.c');built=Path('.work/build/linux-src-gts9wifi/arch/arm64/kernel/gts9_pnmi_test.c')
assert source.read_bytes()==built.read_bytes()
old=source.read_text();needle='/* Called only on the backtrace IPI path; never prints/waits/allocates. */'
new=old.replace(needle,'void gts9_pnmi_test_observe(struct pt_regs *regs);\n\n'+needle)
assert len(new.splitlines())==len(old.splitlines())+2
patch=Path('kernel/patches/diagnostic/0027-gts9-pnmi-calibration.patch')
text=patch.read_text();a=text.index('@@ -0,0 +1,')
patch.write_text(text[:a]+f'@@ -0,0 +1,{len(new.splitlines())} @@\n'+''.join('+'+line+'\n' for line in new.splitlines()))
source.write_text(new);built.write_text(new)
env=os.environ.copy();epoch=subprocess.check_output(['git','-C','.work/linux-mainline','log','-1','--format=%ct'],text=True).strip()
stamp=subprocess.check_output(['date','-u','-d','@'+epoch],env={**env,'LC_ALL':'C'},text=True).strip()
env.update(CCACHE_DIR=str(root/'.work/ccache'),CCACHE_BASEDIR=str(root/'.work'),CCACHE_SLOPPINESS='include_file_ctime,include_file_mtime',KBUILD_BUILD_USER='gts9-mainline',KBUILD_BUILD_HOST='reproducible',SOURCE_DATE_EPOCH=epoch,KBUILD_BUILD_TIMESTAMP=stamp)
Path('.work/build/linux-out/.version').write_text('0\n')
cmd=['make','-C',str(root/'.work/build/linux-src-gts9wifi'),'O='+str(root/'.work/build/linux-out'),'ARCH=arm64','LLVM=1','CC=ccache clang','-j12','Image.gz','qcom/sm8550-samsung-gts9wifi.dtb']
(validation/'incremental-command.json').write_text(json.dumps({'command':cmd,'reason':'add missing forward prototype; no behavior/config/DTB change; reuse initial complete build','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':hashlib.sha256(new.encode()).hexdigest(),'reproducible_environment':{k:env[k] for k in ('KBUILD_BUILD_USER','KBUILD_BUILD_HOST','SOURCE_DATE_EPOCH','KBUILD_BUILD_TIMESTAMP','CCACHE_DIR','CCACHE_BASEDIR','CCACHE_SLOPPINESS')}},indent=2)+'\n')
with (validation/'build-final.txt').open('wb') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
assert 'warning:' not in (validation/'build-final.txt').read_text() and 'error:' not in (validation/'build-final.txt').read_text()
out=Path('out/kernel-pnmi-calibration');shutil.copy2('.work/build/linux-out/arch/arm64/boot/Image.gz',out/'Image.gz')
for name in ('vmlinux','System.map'):shutil.copy2(Path('.work/build/linux-out')/name,Path('out/test241')/name)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
(out/'SHA256SUMS').write_text(''.join(sha(out/name)+'  '+name+'\n' for name in ('Image.gz','sm8550-samsung-gts9wifi.dtb','config','kernel.release')))
subprocess.run(['git','-C','.work/build/linux-src-gts9wifi','apply','--reverse','--check',str(root/patch)],check=True)
test=subprocess.run(['python3','out/test241/check_helper.py'],capture_output=True,text=True,check=True)
(validation/'helper-tests.json').write_text(test.stdout)
(validation/'source-check.json').write_text(json.dumps({'tested_helper_equals_build_source':source.read_bytes()==built.read_bytes(),'source_sha256':sha(source),'backtrace_hook_excluded_from_regular_IPI_tracepoints':True,'console_threshold':5,'runtime_and_physical_validation':'pending','final_incremental_build_warnings':0},indent=2)+'\n')
base=Path('out/kernel-lastactivity-ecc')
assert sha(out/'sm8550-samsung-gts9wifi.dtb')==sha(base/'sm8550-samsung-gts9wifi.dtb') and (out/'kernel.release').read_bytes()==(base/'kernel.release').read_bytes()
subprocess.run(['llvm-objcopy','--dump-section','.notes=out/test241/kernel-notes.bin','out/test241/vmlinux'],check=True)
files=[out/name for name in ('Image.gz','sm8550-samsung-gts9wifi.dtb','config','kernel.release')]+[Path('out/test241')/name for name in ('vmlinux','System.map','kernel-notes.bin')]
(validation/'build-artifacts.json').write_text(json.dumps({str(f):{'sha256':sha(f),'bytes':f.stat().st_size} for f in files},indent=2)+'\n')
diff=subprocess.run(['diff','-u',str(base/'config'),str(out/'config')],capture_output=True,text=True)
(validation/'config-difference.txt').write_text(diff.stdout);assert diff.returncode==1
assert 'CONFIG_ARM64_PSEUDO_NMI=y\n' in (out/'config').read_text() and '# CONFIG_HARDLOCKUP_DETECTOR is not set\n' in (out/'config').read_text()
for name in ('SHA256SUMS','config','kernel.release'):shutil.copy2(out/name,validation/name)
print('Final diagnostic build and helper checks passed',flush=True)
