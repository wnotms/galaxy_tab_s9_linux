#!/usr/bin/env python3
"""Test330 reuses frozen Test328 orchestration; fixes only opt-in separators."""
import argparse,hashlib,importlib.util,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('shared328',R.parent/'test-328-fedora-pps-short/host_flow.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
ORIGINAL_IDENTITY=f.identity
ORIGINAL_RESTORE=f.restore

def identity(raw,on,expected=None,final=False):
    if not on:return ORIGINAL_IDENTITY(raw,on,expected,final)
    sec=f.h.g.baseline.sections(raw);tokens=sec['cmdline'].split();flag=f.PACKAGE['cmdline_flag']
    if tokens.count(flag)!=1 or sec['direct-default'].strip() not in ('Y','1'):raise ValueError('boot opt-in identity')
    tokens.remove(flag)
    if tokens!=f.PLAN['runtime_cmdline'].split():raise ValueError('changed/ordered command-line tokens')
    normalized=dict(sec,cmdline=f.PLAN['runtime_cmdline'],**{'direct-default':'N'})
    limits=dict(f.PLAN,flash_soc_max=95,vbat_max_uv=4400000) if final else f.PLAN
    boot,battery=f.gate.identity(normalized,limits,'candidate',expected)
    return sec,boot,battery

def verify_inputs(push=False):
    for name,sha in json.loads((R/'INPUTS.json').read_text()).items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('registered input drift '+name)
    f.base.verify_stage(Path('/mnt/d/android/gts9-active/gts9-test330'))
    if push:
        git=lambda *a:subprocess.check_output(['git',*a],text=True).strip()
        if git('branch','--show-current')!='test' or git('rev-parse','HEAD')!=git('rev-parse','origin/test'):raise ValueError('registration not pushed')
        names=list(json.loads((R/'INPUTS.json').read_text()))+[str((R/'INPUTS.json').relative_to(ROOT))]
        if git('status','--porcelain','--',*names):raise ValueError('registered input uncommitted')
        subprocess.run(['git','ls-files','--error-unmatch',*names],check=True,stdout=subprocess.DEVNULL)

def restore(emergency=False):
    if emergency:f.old.R=R.parent/'test-327-fedora-default-off'
    return ORIGINAL_RESTORE(emergency)

def configure():
    f.R=R;f.configure();f.h.STAGE='D:/android/gts9-active/gts9-test330';f.h.TMP='/tmp/gts9-test330'
    f.restore=restore
    f.TRUST=Path('/tmp/gts9-test330-known-hosts');f.identity=identity;f.verify_inputs=verify_inputs

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['preflight','install','arm','status','collect','restore']);parser.add_argument('--emergency',action='store_true');args=parser.parse_args();configure()
    print(json.dumps(f.restore(args.emergency) if args.action=='restore' else getattr(f,args.action)(),indent=2),flush=True)
