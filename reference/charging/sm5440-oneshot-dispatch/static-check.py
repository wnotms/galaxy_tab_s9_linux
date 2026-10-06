"""Inspect changed driver only; restore exact qualified build object afterward."""
from pathlib import Path
import subprocess,os,time,json,gzip,hashlib
ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).parent
T=ROOT/'.work/build/linux-src-x710-charging';B=ROOT/'.work/build/linux-out-x710-308-passive'
obj=B/'drivers/power/supply/sm5440-direct.o';original=obj.read_bytes();digest=hashlib.sha256(original).hexdigest()
cmd=['make','-C',str(T),'O='+str(B),'ARCH=arm64','LLVM=1','CC=ccache clang','-j8'];target='drivers/power/supply/sm5440-direct.o';start=time.monotonic()
p=subprocess.run(cmd+['W=1','C=2',target],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(R/'static.log.gz').write_bytes(gzip.compress(p.stdout,mtime=0))
normal=subprocess.run(cmd+[target],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(R/'static-standard.log.gz').write_bytes(gzip.compress(normal.stdout,mtime=0))
obj.write_bytes(original)
record=dict(argv=cmd+['W=1','C=2',target],returncode=p.returncode,standard_flags_returncode=normal.returncode,seconds=time.monotonic()-start,warnings=[x for x in p.stdout.decode().splitlines() if 'warning:' in x],qualified_object_sha256=digest,qualified_object_restored=hashlib.sha256(obj.read_bytes()).hexdigest()==digest,formal_artifacts_relinked=False)
(R/'static.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(p.returncode or normal.returncode)
