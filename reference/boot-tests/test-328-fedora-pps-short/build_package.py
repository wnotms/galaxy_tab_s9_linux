#!/usr/bin/env python3
"""Reuse qualified kernel/modules; generate only the explicit boot opt-in."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).resolve().parent
Q=ROOT/'reference/charging/sm5440-fedora-port'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    old=json.loads((Q/'PACKAGE.json').read_text());a=old['artifacts']
    for key in ['Image.gz','sm8550-samsung-gts9wifi.dtb','config','kernel-notes.bin','modules-x710.tar.gz','boot.img','rollback-boot.img']:
        if sha(ROOT/a[key]['path'])!=a[key]['sha256']:raise ValueError('qualified artifact drift '+key)
    out=ROOT/'out/boot-bundle-x710-fedora-pps';out.mkdir(exist_ok=True)
    boot=out/'boot.img';flag='sm5440_fedora.direct_charge=1'
    with tempfile.TemporaryDirectory() as tmp:
        t=Path(tmp);payload=(ROOT/a['Image.gz']['path']).read_bytes()+(ROOT/a['sm8550-samsung-gts9wifi.dtb']['path']).read_bytes();(t/'kernel').write_bytes(payload)
        subprocess.run(['python3',str(ROOT/'.work/tools/mkbootimg.py'),'--kernel',str(t/'kernel'),'--cmdline',flag,'--header_version','4','--os_version','13','--os_patch_level','2025-07','-o',str(boot)],check=True)
        subprocess.run(['python3',str(ROOT/'.work/tools/avbtool.py'),'add_hash_footer','--image',str(boot),'--partition_name','boot','--partition_size','100663296','--salt',sha(boot)],check=True)
        header=subprocess.check_output(['python3',str(ROOT/'.work/tools/unpack_bootimg.py'),'--boot_img',str(boot),'--out',str(t/'unpacked')],text=True)
        if (t/'unpacked/kernel').read_bytes()!=payload or 'command line args: '+flag not in header or boot.stat().st_size!=100663296:raise ValueError('package payload/argument')
        (R/'boot-header.txt').write_text(header)
    baseline=old['candidate_partitions'];package=dict(test='Test328',source_revision=old['source_revision'],baseline_partitions=baseline,candidate_partitions=dict(baseline,boot=sha(boot)),emergency323_partitions=old['baseline_partitions'],modules_unchanged=True,modules=181,write_partitions=['boot'],kernel_build_executed=False,cmdline_flag=flag,artifacts=dict(a,**{'boot.img':dict(path=str(boot.relative_to(ROOT)),bytes=boot.stat().st_size,sha256=sha(boot)),'rollback-boot.img':a['boot.img'],'emergency323-boot.img':a['rollback-boot.img']}))
    (R/'PACKAGE.json').write_text(json.dumps(package,indent=2)+'\n');return package
if __name__=='__main__':print(json.dumps(build(),indent=2))
