from pathlib import Path
import shutil,hashlib,json,subprocess
p=Path('reference/boot-tests/test-243-pnmi-no-lastactivity');bundle=Path('out/boot-bundle-pnmi-no-lastactivity')
win=Path('/mnt/d/android/gts9-test243');win.mkdir(exist_ok=True)
parts={line.split()[1].rsplit('/',1)[-1]:line.split()[0] for line in (p/'twrp-before-flash/partitions.txt').read_text().splitlines() if '/dev/block/by-name/' in line}
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
rows=[]
for part in ('boot','vendor_boot'):
 backup=Path('/mnt/d/android/gts9-test230/backup-'+part+'.img');candidate=bundle/(part+'.img')
 assert backup.stat().st_size==candidate.stat().st_size==100663296 and sha(backup)==parts[part]
 shutil.copy2(candidate,win/candidate.name);assert sha(win/candidate.name)==sha(candidate)
 rows.append({'partition':part,'bytes':candidate.stat().st_size,'backup_path':str(backup),'backup_sha256':sha(backup),'candidate_sha256':sha(candidate),'windows_stage_sha256':sha(win/candidate.name)})
for part in ('init_boot','dtbo'):assert sha(bundle/(part+'.img'))==parts[part],part
# Generated vbmeta descriptors vary with boot payload; existing verification-
# disabled production vbmeta stays installed and is checked by the flash runner.
(p/'validation/unflashed-images.json').write_text(json.dumps({'init_boot_and_dtbo_match_production':True,'generated_vbmeta_sha256':sha(bundle/'vbmeta.img'),'installed_vbmeta_expected_sha256':parts['vbmeta'],'vbmeta_will_be_flashed':False},indent=2)+'\n')
(p/'backup-and-staging.json').write_text(json.dumps(rows,indent=2)+'\n')
for name in ('BUNDLE_INFO','SHA256SUMS'):shutil.copy2(bundle/name,p/'validation'/('bundle-'+name))
shutil.copy2('out/test243/stage_bundle.py',p/'runner/stage_bundle.py')
print('Candidate/Windows stage/original backups verified; init_boot/dtbo match; installed vbmeta unchanged')
