#!/usr/bin/env python3
"""Resume the same already installed candidate after the host handle disappeared.
Never installs a second candidate. Original readiness evidence is retained.
"""
import importlib.util
import json
from pathlib import Path
import os
import time

R = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ssc383_resume_flow', R / 'host_flow.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.p.SERIAL = 'gts9wifi-0001'
m.write(R / 'host-continuation.json', dict(pid=os.getpid(), started_epoch=time.time(),
    original_process_handle='43196', original_handle_missing=True,
    original_process_missing=True, second_candidate=False,
    original_readiness_preserved=True, required_boot_id='16d836fc-cf62-498a-8153-69162f346e54'))
try:
    m.verify_inputs(True)
    state = m.read(R / 'mutation-state.json')
    if state['phase'] != 'installed-awaiting-one-boot' or state['boot_id'] != '16d836fc-cf62-498a-8153-69162f346e54':
        raise ValueError('already installed candidate boundary changed')
    pre = m.read(R / 'active-preflight.json')
    result = m.accept(m.p.Recorder(R / 'candidate-acceptance-continuation'), 'candidate',
                      pre['boot_id'], (R / pre['folder'] / 'boots.txt').read_text())
    m.write(R / 'mutation-state.json', dict(rollback_required=True,
        phase='accepted-candidate-kept-text', boot_id=result['boot_id']))
    print(json.dumps(result), flush=True)
    print(json.dumps(m.discover()), flush=True)
    m.write(R / 'host-continuation-complete.json', dict(pid=os.getpid(), finished_epoch=time.time(),
                                                      second_candidate=False))
except Exception as exc:
    m.write(R / 'host-continuation-error.json', dict(error=str(exc), second_candidate=False))
    state = m.read(R / 'mutation-state.json')
    if state['rollback_required'] and not (R / 'recovery-required.json').exists():
        try:
            m.restore()
        except Exception as recovery:
            m.write(R / 'recovery-required.json', dict(error=str(recovery), manual_TWRP_required=True))
    raise
