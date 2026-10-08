PREFIX_BYTES=139493376
PREFIX_SHA='5fc70d719a170f4b03f76034778c50fae03c1ac323e5744f85202a9d6172d87a'
EXPECTED_BOOT='be1baaaa-47fc-41f5-8255-8f7092c01653'
EXPECTED_SHA='83d7db40c190d68522cfce4d9d552149f6759a4a7d7d6f265feba4eee0d46458'
EXPECTED_BYTES=166492160
from pathlib import Path
import sys,json,hashlib,shutil,tarfile
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot==EXPECTED_BOOT,'boot changed'
root=Path('/var/tmp/gts9-test351');root.mkdir(exist_ok=False)
print(json.dumps(dict(stage='RECEIVING_BUNDLE',boot_id=boot)),flush=True)
prefix=Path('/var/tmp/gts9-test350/deploy.tar')
assert prefix.stat().st_size==PREFIX_BYTES,'prefix size changed'
with prefix.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==PREFIX_SHA,'prefix hash changed'
p=root/'deploy.tar'
shutil.copyfile(prefix,p)
with p.open('ab') as stream:shutil.copyfileobj(sys.stdin.buffer,stream,1048576)
assert p.stat().st_size==EXPECTED_BYTES,'bundle size'
with p.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
assert actual==EXPECTED_SHA,'bundle hash'
with tarfile.open(p) as tar:
 rows=tar.getmembers();assert len(rows)==381
 assert all(m.isfile() and m.name.startswith('gts9-gnome/') and '..' not in Path(m.name).parts for m in rows)
 tar.extractall(root,filter='data')
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
print(json.dumps(dict(verdict='BUNDLE_TRANSFERRED_EXTRACTED',boot_id=boot,sha256=actual,bytes=p.stat().st_size,members=381,installation_executed=False)),flush=True)
