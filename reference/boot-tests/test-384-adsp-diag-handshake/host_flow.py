#!/usr/bin/env python3
"""Test384: one AP-initiated DIAG OPEN; no RPC launch or DIAG protocol writes."""
import argparse
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import time
from uuid import UUID

R = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ssc384_core', R / 'core.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
PLAN = C.PLAN


def stage():
    result = C._stage_kernel()
    sources = {name: R / name for name in ('desktop.py', 'desktop-manifest.json')}
    for row in C.read(R / 'desktop-manifest.json').values():
        sources[row['incoming']] = C.ROOT / row['source']
    sources['rpmsg_ctrl.ko'] = C.ROOT / PLAN['module_path']
    sources['rpmsg_diagnostic.py'] = C.ROOT / 'userspace/sensors/rpmsg_diagnostic.py'
    rows = C.read(R / 'staged-files.json')
    for name, source in sources.items():
        shutil.copyfile(source, C.LOCAL / name)
        rows[name] = dict(bytes=source.stat().st_size, sha256=C.sha(source))
    C.write(R / 'staged-files.json', rows)
    return dict(result, files=len(rows))


def control_parent(inventory, boot):
    if UUID(inventory['boot_id']) != UUID(boot):
        raise ValueError('control inventory boot mismatch')
    parents = [row for row in inventory['rpmsg'] if row['name'] == 'rpmsg_ctrl']
    if len(parents) != 1 or parents[0]['driver'] is not None:
        raise ValueError('control parent not uniquely unbound; no adoption')
    parent = parents[0]['resolved']
    prefix = '/sys/devices/platform/soc@0/6800000.remoteproc/'
    if not parent.startswith(prefix) or ':glink-edge.rpmsg_ctrl.' not in Path(parent).name:
        raise ValueError('not the X710 ADSP control parent')
    return parent


def controller(rec, parent, boot):
    script = '''import json
from pathlib import Path
p=Path('/sys/class/rpmsg')
rows=[dict(path=str(x),resolved=str(x.resolve()),parent=str(x.resolve().parent.parent)) for x in p.glob('rpmsg_ctrl*')]
print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),controllers=rows)))'''
    raw, _ = rec.adb('native-controller', 'python3 -c ' + shlex.quote(script), timeout=5)
    data = json.loads(raw)
    if UUID(data['boot_id']) != UUID(boot) or len(data['controllers']) != 1:
        raise ValueError('loaded control inventory boot/uniqueness')
    row = data['controllers'][0]
    if row['parent'] != parent:
        raise ValueError('loaded controller ancestry mismatch')
    return row['path']


def diagnostic(rec, boot):
    current = C.snapshot(rec, 'diagnostic-boundary', 'candidate', boot)
    C.native_gate(current); C.transport_admit(rec, 'diagnostic-transport', current)
    if current['uptime'] > PLAN['trace_boot_deadline_seconds'] - 25:
        raise ValueError('insufficient registered trace window')
    parent = control_parent(C.trace_inventory(rec, 'glink-before-diag', boot), boot)
    rows = C.verify_stage()
    rec.adb('incoming-dir', 'set -e; test ! -e '+C.TMP+'; mkdir -m700 '+C.TMP, timeout=5)
    for name in ('rpmsg_ctrl.ko', 'rpmsg_diagnostic.py'):
        rec.host_adb('push-'+name, '-s', C.p.SERIAL, 'push', C.STAGE+'/'+name, C.TMP+'/'+name, timeout=8)
    hashes = ''.join(rows[name]['sha256']+'  '+C.TMP+'/'+name+'\n' for name in ('rpmsg_ctrl.ko','rpmsg_diagnostic.py'))
    rec.adb('incoming-hashes', 'printf %s '+shlex.quote(hashes)+' | sha256sum -c -', timeout=5)
    # No driver override/bind mutation, no rmmod, no live RPC activation.
    rec.adb('load-native-control', 'set -e; test ! -e /run/gts9-ssc-test/ready; test ! -e /sys/module/rpmsg_ctrl; test ! -e /sys/bus/rpmsg/drivers/rpmsg_ctrl; test ! -e /run/gts9-test384; mkdir -m700 /run/gts9-test384; insmod '+C.TMP+'/rpmsg_ctrl.ko', timeout=8)
    ctl = controller(rec, parent, boot)
    plan = dict(boot_id=boot, cmdline=PLAN['runtime_cmdline'],
                config_sha256=PLAN['candidate_config_sha256'], notes_sha256=PLAN['candidate_notes_sha256'],
                module_build_id_note_sha256=PLAN['module_build_id_note_sha256'],
                channel='DIAG', payload_writes=False, rpmsg_parent=parent, controller=ctl)
    C.write(rec.folder/'live-diag-plan.json', plan)
    rec.adb('live-diag-plan', 'python3 -c '+shlex.quote('from pathlib import Path; Path('+repr(C.TMP+'/diag-plan.json')+').write_text('+repr(json.dumps(plan))+')'), timeout=5)
    command = ('timeout --signal=TERM --kill-after=2 '+str(PLAN['helper_device_deadline_seconds'])+
               ' python3 '+C.TMP+'/rpmsg_diagnostic.py --plan '+C.TMP+'/diag-plan.json --ledger /run/gts9-test384/probe.json')
    raw, status = rec.adb('diag-probe', command, timeout=PLAN['helper_host_deadline_seconds'], required=False)
    rec.adb('diag-ledger', 'cat /run/gts9-test384/probe.json; cat /proc/sys/kernel/tainted', timeout=5, required=False)
    if status != 0:
        raise ValueError('one DIAG helper failed/status='+str(status)+'; never retry or live-unload')
    result = json.loads(raw)
    if (UUID(result['boot_id']) != UUID(boot) or not result['complete'] or
            not result['endpoint_opened'] or not result['endpoint_destroyed'] or
            result['payload_writes'] != 0 or result['masks_sent'] != 0 or
            result['packet_bytes'] > PLAN['helper_packet_max_bytes']):
        raise ValueError('DIAG result incomplete, wrong boot or out of scope')
    C.write(rec.folder/'diag-result.json', result)
    return result


def probe():
    C.verify_inputs(True)
    state = C.read(R / 'mutation-state.json')
    if state['phase'] != 'accepted-candidate-kept-text' or (R / 'diagnostic').exists():
        raise ValueError('one diagnostic only from accepted candidate')
    C.p.SERIAL = 'gts9wifi-0001'; rec = C.p.Recorder(R / 'diagnostic'); boot = state['boot_id']
    result = None; error = None
    try:
        result = diagnostic(rec, boot)
        C.trace_collect(rec, boot)
        C.trace_inventory(rec, 'glink-after-diag', boot)
        current = C.snapshot(rec, 'final-identity', 'candidate', boot)
        C.native_gate(current); C.transport_admit(rec, 'final-transport', current)
        faults = C.scan(rec, boot, current['uptime'])
        result.update(kernel_fault_counts=faults['fault_counts'], SSC_tested=False,
                      physical_rotation_tested=False, runtime_module_changed=True,
                      live_control_unloaded=False, PPS=False, pump_ON=False)
        C.write(rec.folder/'summary.json', result)
    except Exception as exc:
        error = exc
        C.write(R/'first-diagnostic-failure.json',dict(error=str(exc), stopped=True, no_retry=True))
        for name, collect in (
            ('glink', lambda: C.trace_collect(rec,boot,'failure-glink')),
            ('inventory', lambda: C.trace_inventory(rec,'failure-inventory',boot)),
            ('kernel', lambda: C.scan(rec,boot,0))):
            try: collect()
            except Exception as failed:
                C.write(rec.folder/(name+'-collection-error.json'),dict(error=str(failed)))
    finally:
        # A baseline reboot removes temporary control/endpoint state. No rmmod.
        try:
            rollback = C.restore()
            rec.adb('empty-ledger-dir-cleanup', 'if test -d /var/lib/gts9-test384; then rmdir /var/lib/gts9-test384; fi; test ! -e /sys/module/rpmsg_ctrl; test ! -e /run/gts9-test384', timeout=8)
            C.write(R/'rollback-complete.json', rollback)
        except Exception as failed:
            C.write(R/'recovery-required.json',dict(error=str(failed),manual_TWRP_required=True))
            if error is None:error=failed
    if error is not None:raise error
    return result


def run():
    if (R/'mutation-state.json').exists():
        raise ValueError('no second installation or reboot')
    C.preflight()
    C.install()
    return probe()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('verify','stage','preflight','install','probe','restore','restore-recovery','run'))
    mode=parser.parse_args().mode
    if mode=='verify':result=C.verify_inputs()
    elif mode=='stage':result=stage()
    elif mode=='preflight':result=C.preflight()
    elif mode=='install':result=C.install()
    elif mode=='probe':result=probe()
    elif mode=='run':result=run()
    else:result=C.restore(mode=='restore-recovery')
    print(json.dumps(result,indent=2))
