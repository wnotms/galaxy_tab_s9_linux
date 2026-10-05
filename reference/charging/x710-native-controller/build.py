#!/usr/bin/env python3
"""Build a separate formal candidate using the existing native-profile cache."""
from pathlib import Path
import gzip,json,os,subprocess,time,datetime
R=Path(__file__).resolve().parents[3];D=Path(__file__).resolve().parent
values={'JOBS':'8','USE_CCACHE':'1','BUILD_MODULES':'1','GTS9_CHARGING_PROFILE':'sm5440-native-control','KERNEL_WORKTREE':str(R/'.work/build/linux-src-x710-charging'),'KERNEL_BUILD_DIR':str(R/'.work/build/linux-out-x710-303-policy'),'KERNEL_OUT_DIR':str(R/'out/kernel-x710-native-controller')}
env=dict(os.environ,**values);started=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic()
with (D/'build.log.tmp').open('wb') as f:
 p=subprocess.run(['bash','scripts/build-kernel.sh'],cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
d={'returncode':p.returncode,'seconds':time.monotonic()-t,'started_utc':started,'environment':values,'device_operations':[]}
(D/'build.json').write_text(json.dumps(d,indent=2)+'\n');log=D/'build.log.tmp';(D/'build.log.gz').write_bytes(gzip.compress(log.read_bytes(),mtime=0));log.unlink()
print(json.dumps(d));raise SystemExit(p.returncode)
