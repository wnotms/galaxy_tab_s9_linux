#!/usr/bin/env python3
"""One registered bulk upload; full digest gate precedes remote extraction."""
from pathlib import Path
import hashlib
import json
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
R=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
from windows_ssh_bulk import bulk_ssh_argv

reg=json.loads((R/'registration.json').read_text())
# Physical mutation follows publication of this exact registration/code.
for path in ('scripts/windows_ssh_bulk.py',str(R.relative_to(ROOT))):
    if subprocess.check_output(['git','status','--porcelain','--',path],cwd=ROOT).strip():
        raise ValueError('uncommitted deployment input')
subprocess.run(['git','merge-base','--is-ancestor','HEAD','origin/test'],cwd=ROOT,check=True)
archive=ROOT/'out/gnome-trixie-arm64/gts9-gnome-deploy.tar'
with archive.open('rb') as stream:
    actual=hashlib.file_digest(stream,'sha256').hexdigest()
if actual!=reg['bundle_sha256'] or archive.stat().st_size!=166492160:
    raise ValueError('qualified archive changed')
evidence=R/'transfer';evidence.mkdir(exist_ok=False)
argv=bulk_ssh_argv('/home/ms/.ssh/gts9_ed25519','/home/ms/.ssh/gts9-test292-known-hosts',
                   'gts9-test292','10.175.236.175','python3 -c '+shlex.quote((R/'transfer-code.py').read_text()))
start=time.time()
with archive.open('rb') as source,(evidence/'stdout.txt').open('w') as out,(evidence/'stderr.txt').open('w') as err:
    child=subprocess.Popen(argv,stdin=source,stdout=out,stderr=err)
    (evidence/'command.json').write_text(json.dumps(dict(argv=argv,pid=child.pid,started_epoch=start),indent=2)+'\n')
    try:
        status=child.wait(timeout=reg['bulk_transfer_timeout_seconds'])
    except subprocess.TimeoutExpired:
        child.terminate()
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.kill();child.wait()
        status=124
summary=dict(returncode=status,elapsed_seconds=time.time()-start,installation_executed=False)
(evidence/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
if status:sys.exit(status)
rows=(evidence/'stdout.txt').read_text().splitlines()
result=json.loads(rows[-1])
if result['verdict']!='BUNDLE_TRANSFERRED_EXTRACTED' or result['boot_id']!=reg['expected_boot_id'] or result['sha256']!=actual:
    raise ValueError('incomplete remote transfer attribution')
