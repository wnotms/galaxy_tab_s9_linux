#!/usr/bin/env python3
"""Exact331 restoration; ordinary battery limits are separate from bring-up entry."""
import importlib.util,json,hashlib,subprocess
from pathlib import Path
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('test333_restore_flow',R/'host_flow.py')
flow=importlib.util.module_from_spec(spec);spec.loader.exec_module(flow)

def restored_identity(sections,plan,phase,expected=None):
    if phase!='baseline':raise ValueError('restoration-only baseline gate')
    normal=dict(plan,flash_soc_max=101,vbat_max_uv=4440001)
    # No charger activation: accept ordinary SOC 0..100 only within prior minimum,
    # unchanged 4.44V design, temperature/health/identity/OFF/transport requirements.
    return flow.gate.identity(sections,normal,'baseline',expected)

def main():
    inputs=json.loads((R/'RESTORE_INPUTS.json').read_text())
    for name,expected in inputs.items():
        if hashlib.sha256((R/name).read_bytes()).hexdigest()!=expected:raise ValueError('restore input drift')
    subprocess.run(['git','-C',str(flow.ROOT),'ls-files','--error-unmatch',*[str((R/name).relative_to(flow.ROOT)) for name in inputs]],check=True,stdout=subprocess.DEVNULL)
    if subprocess.check_output(['git','-C',str(flow.ROOT),'status','--porcelain','--',*[str((R/name).relative_to(flow.ROOT)) for name in inputs]],text=True).strip():raise ValueError('uncommitted restore input')
    flow.configure()
    def identity(raw,phase,expected=None):
        sections=flow.h.g.baseline.sections(raw)
        boot,battery=restored_identity(sections,flow.PLAN,phase,expected)
        return sections,boot,battery,{}
    flow.identity=identity;flow.base.identity=identity
    result=flow.restore()
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
