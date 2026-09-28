import sys,json,hashlib,datetime
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()))
import production_reboot_stability as p
p.P=p.TEST250_ROOT/'attempt-05'
folder=Path('reference/boot-tests/test-252-sm5714-stage1/attempt-01/preflight')
assert not folder.exists()
rec=p.Recorder(folder)
try:
    base=p.baseline()
    state=p.production_state(rec,base,full=True)
    link=p.transport(rec,state['boot_id'],source_bound=True)
    journal=rec.adb('kernel-journal-json','journalctl -b -k --no-pager -o json',35)[0]
    rec.adb('kernel-journal','journalctl -b -k --no-pager -o short-monotonic',35)
    scan=p.inspect(journal,state['boot_id'],base,state['uptime_seconds'])
    rec.adb('boot-history','journalctl --list-boots --no-pager',20)
    wifi=rec.command('wifi-ssh',['timeout','15','env','GTS9_DEVICE=10.191.121.224','scripts/gts9-ssh.sh','cat /proc/sys/kernel/random/boot_id'],timeout=18)
    if not all(link[k] for k in ['adb_ok','ssh_ok','ncm_banner_ok']) or link['code43'] or link['ncm_initial_failure']:
        raise RuntimeError('transport preflight not clean')
    if scan.get('kernel_fault_counts') and any(scan['kernel_fault_counts'].values()):
        raise RuntimeError('kernel fault signature detected')
    if scan.get('kernel_suspects'):
        raise RuntimeError('unclassified kernel suspect')
    assert wifi[1]==0 and wifi[0].strip()==state['boot_id']
    p.write_json(folder/'summary.json',dict(verdict='accepted',production_state=state,transport=link,kernel_scan=scan,wifi_ssh=True,device_writes=False))
    print(json.dumps({'verdict':'accepted','boot_id':state['boot_id'],'uptime':state['uptime_seconds'],'wifi_ssh':True,'transport':link}))
except Exception as e:
    p.write_json(folder/'summary.json',dict(verdict='stopped',reason=str(e),device_writes=False))
    raise
