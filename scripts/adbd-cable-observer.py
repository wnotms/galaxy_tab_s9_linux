#!/usr/bin/env python3
"""Host-only Test253 cable capture. No deployment, restart, reset or reboot.

Requires an adopted registration and passing full preflight. Each process
records one owner-operated cycle and stops on its first failed gate.
"""
import argparse
import dataclasses
import json
from pathlib import Path
import re
import subprocess
import time

import production_reboot_stability as p
from adbd_cable_evidence import CableCycle, boot_id, review_adbd

SNAPSHOT = r'''set -eu
cat /proc/sys/kernel/random/boot_id
cat /proc/uptime
cat /sys/class/udc/a600000.usb/state
systemctl show -p MainPID --value gts9-adbd.service
pid=$(systemctl show -p MainPID --value gts9-adbd.service)
sha256sum /proc/$pid/exe
cat /sys/kernel/config/usb_gadget/gts9/UDC
cat /sys/class/power_supply/sm5714-usb/online
'''


def load_registration(path):
    policy = json.loads(path.read_text())
    if not policy.get('owner_adopted') or not policy.get('owner_reply'):
        raise ValueError('registration is proposed, not owner-adopted')
    if (policy.get('physical_cycles') != 3 or policy.get('offline_seconds') != 10 or
            policy.get('recovery_seconds') != 60 or policy.get('observation_seconds') != 150 or
            policy.get('maximum_pre_enable_disable_warnings_per_cycle') != 1 or
            policy.get('disable_to_enable_seconds') != 5 or policy.get('enable_to_worker_seconds') != 1 or
            policy.get('device_changes') is not False or policy.get('host_server_restarts') != 0):
        raise ValueError('unreviewed registration gate')
    preflight = json.loads((path.parent/'preflight/summary.json').read_text())
    if preflight.get('verdict') != 'passed' or preflight.get('full_identity') is not True:
        raise ValueError('passing full preflight missing')
    if boot_id(preflight['boot_id']) != boot_id(policy['boot_id']):
        raise ValueError('preflight/registration boot mismatch')
    return policy


def parse_snapshot(raw):
    lines = raw.splitlines()
    if len(lines) != 7 or lines[6] not in ('0', '1'):
        raise ValueError('incomplete cable state')
    return dict(boot=lines[0], uptime=float(lines[1].split()[0]), udc_state=lines[2],
                pid=int(lines[3]), sha256=lines[4].split()[0], udc_binding=lines[5], online=lines[6]=='1')


def native_identity(raw):
    lines = raw.splitlines()
    if len(lines) != 3:
        raise ValueError('incomplete native shell identity')
    return lines[0], int(lines[1]), lines[2].split()[0]


def stream_review(path, boot, base, uptime, floor, *, review_daemon, warning_source_range=None):
    raw = path.read_bytes()
    complete = raw[:raw.rfind(b'\n')+1].decode()
    rows = [json.loads(line) for line in complete.splitlines()]
    kernel = '\n'.join(json.dumps(row) for row in rows if row.get('_TRANSPORT') == 'kernel')
    scan = p.inspect(kernel, boot, base, uptime)
    if scan['fault_counts'] or scan['suspects']:
        raise ValueError('new kernel fault/suspect: ' + str(scan))
    daemon = None
    if review_daemon:
        units = [row for row in rows if row.get('_SYSTEMD_UNIT') == 'gts9-adbd.service' or
                 row.get('UNIT') == 'gts9-adbd.service']
        daemon = review_adbd('\n'.join(json.dumps(row) for row in units), expected_boot=boot,
                             expected_pid=834, source_floor=floor, allow_pre_enable_disable=True,
                             warning_source_range=warning_source_range)
    return dict(kernel=scan, adbd=daemon)


def run_cycle(folder, policy, *, recorder=None, clock=time.monotonic, sleep=time.sleep):
    """A folder is single-use. Raw capture survives every failure path."""
    if folder.exists():
        raise ValueError('refusing to reuse physical cycle directory')
    folder.mkdir(parents=True)
    r = recorder or p.Recorder(folder)
    previous_policy = p.P
    try:
        p.P = p.TEST250_ROOT/'attempt-05'
        base = p.baseline()
    finally:
        p.P = previous_policy
    cycle = CableCycle(policy['boot_id'], policy['daemon_pid'], policy['daemon_sha256'])
    wifi = ['env', 'GTS9_DEVICE='+policy['wifi_address'], p.SSH]
    proc = None
    stream = folder/'kernel-adbd-follow.jsonl'
    started = clock()
    samples = []
    try:
        initial, _ = r.command('initial-wifi-state', wifi+[SNAPSHOT], timeout=12)
        init = parse_snapshot(initial)
        cycle.identity(init['boot'], init['pid'], init['sha256'])
        if not init['online'] or init['udc_binding'] != 'a600000.usb':
            raise ValueError('cycle must start connected to computer')
        floor = init['uptime']
        cycle.last_connected_uptime = floor
        native, _ = r.adb('initial-native-shell', 'cat /proc/sys/kernel/random/boot_id')
        if boot_id(native) != boot_id(policy['boot_id']):
            raise ValueError('initial native boot mismatch')
        pnp, _ = r.ps('initial-pnp', p.PS_USB, timeout=30)
        if p.has_code43(pnp):
            raise ValueError('Code43 before action')
        argv = wifi+['journalctl -b -f -n all --no-pager -o json _TRANSPORT=kernel + _SYSTEMD_UNIT=gts9-adbd.service + UNIT=gts9-adbd.service']
        with stream.open('wb') as output, (folder/'kernel-adbd-follow.stderr').open('wb') as error:
            proc = subprocess.Popen(argv, stdout=output, stderr=error)
            p.write_json(folder/'follow-start.json', dict(argv=argv, started_utc=p.now(), host_pid=proc.pid))
            sleep(2)
            print('READY: perform one unplug>=20s/replug; Wi-Fi stays on, no charger/reboot', flush=True)
            for poll in range(1,1000):
                if proc.poll() is not None:
                    raise ValueError('Wi-Fi journal stream ended')
                begin = clock()
                raw,_ = r.command(f'poll-{poll:03}-wifi', wifi+[SNAPSHOT], timeout=12)
                sample = parse_snapshot(raw)
                table,_ = r.host_adb(f'poll-{poll:03}-adb', 'devices', '-l', timeout=5)
                present = re.search(r'^gts9wifi-0001\s+device\b', table, re.M) is not None
                # command START/END bracket includes both snapshots, making
                # offline duration and recovery deadlines conservative.
                returned = cycle.sample(**sample, native_seen=present, started=begin, ended=clock())
                samples.append(dict(poll=poll, **sample, native_seen=present, elapsed_seconds=clock()-started))
                p.write_json(folder/'progress.json', dict(state=dataclasses.asdict(cycle), samples=samples))
                scan = stream_review(stream, policy['boot_id'], base, sample['uptime'], floor, review_daemon=False)
                if returned:
                    break
                if clock()-started > 900:
                    raise ValueError('owner-action/physical return deadline expired')
                sleep(1)
            else:
                raise ValueError('physical transition missing')

            identity_command = 'cat /proc/sys/kernel/random/boot_id; systemctl show -p MainPID --value gts9-adbd.service; pid=$(systemctl show -p MainPID --value gts9-adbd.service); sha256sum /proc/$pid/exe'
            for attempt in range(1,30):
                native, rc = r.adb(f'recovery-{attempt:02}-native', identity_command, timeout=5, required=False)
                if rc == 0:
                    nb, npid, sha = native_identity(native)
                    cycle.identity(nb, npid, sha)
                    ncm, nrc = r.ssh(f'recovery-{attempt:02}-ncm-shell', 'cat /proc/sys/kernel/random/boot_id', timeout=8, required=False)
                    if nrc == 0:
                        banner,_ = r.ps('recovery-ncm-banner', p.PS_NCM_BOUND_BANNER, timeout=30)
                        if not p.bound_banner_ok(banner):
                            raise ValueError('NCM bound banner failed')
                        bound = cycle.recovered(native_boot=nb, native_pid=npid, native_sha256=sha,
                                                ncm_boot=ncm, now=clock())
                        break
                if clock()-cycle.last_off_start >= 60:
                    raise ValueError('native shell/NCM not recovered within60s')
                sleep(1)
            else:
                raise ValueError('native shell/NCM recovery not established')
            pnp,_ = r.ps('recovery-pnp', p.PS_USB, timeout=30)
            if p.has_code43(pnp):
                raise ValueError('Code43 after reattach')
            p.write_json(folder/'recovery.json', dict(native_ncm_recovery_upper_bound_seconds=bound,
                         clock_origin='last confirmed offline command start', state=dataclasses.asdict(cycle)))
            for n in range(1,100):
                raw,_ = r.command(f'health-{n:02}-wifi', wifi+[SNAPSHOT], timeout=12)
                state = parse_snapshot(raw)
                cycle.identity(state['boot'], state['pid'], state['sha256'])
                if not state['online'] or state['udc_binding'] != 'a600000.usb':
                    raise ValueError('unexpected extra cable change during observation')
                native,_ = r.adb(f'health-{n:02}-native', identity_command, timeout=8)
                cycle.identity(*native_identity(native))
                ncm,_ = r.ssh(f'health-{n:02}-ncm', 'cat /proc/sys/kernel/random/boot_id', timeout=8)
                if boot_id(ncm) != boot_id(policy['boot_id']):
                    raise ValueError('health NCM boot changed')
                warning_range = (cycle.off_source_earliest, cycle.return_uptime+5)
                scan = stream_review(stream, policy['boot_id'], base, state['uptime'], floor,
                                     review_daemon=True, warning_source_range=warning_range)
                p.write_json(folder/'health-progress.json', dict(elapsed_seconds=clock()-cycle.recovered_at,
                             poll=n, scan=scan))
                if cycle.observed(clock()):
                    observed_elapsed = clock()-cycle.recovered_at
                    break
                if proc.poll() is not None:
                    raise ValueError('journal evidence stream ended')
                sleep(5)
            else:
                raise ValueError('150s responsive window not completed')
        # Complete final journal snapshots are captured before the post-cycle
        # exact config/notes/settings/failed-units checker, run by the owner agent.
        r.command('kernel-journal-json', wifi+['journalctl -k -b --no-pager -o json'], timeout=30)
        r.command('kernel-journal', wifi+['journalctl -k -b --no-pager -o short-monotonic'], timeout=30)
        raw,_ = r.command('adbd-journal-json', wifi+['journalctl -b -u gts9-adbd.service --no-pager -o json'], timeout=30)
        daemon = review_adbd(raw, expected_boot=policy['boot_id'], expected_pid=834,
                             source_floor=floor, allow_pre_enable_disable=True,
                             warning_source_range=warning_range)
        report = dict(verdict='window-passed-awaiting-post-cycle-identity-gate', boot_id=policy['boot_id'],
                      daemon_pid=policy['daemon_pid'], native_ncm_recovery_upper_bound_seconds=bound,
                      responsive_observation_seconds=observed_elapsed,
                      offline_duration_lower_bound_seconds=cycle.last_off_start-cycle.first_off_end,
                      cycle_state=dataclasses.asdict(cycle), kernel_scan=scan['kernel'], adbd_review=daemon,
                      host_server_restarts=0, device_changes=False)
        p.write_json(folder/'summary.json', report)
        return report
    except Exception as exc:
        p.write_json(folder/'failure.json', dict(verdict='stopped', error=repr(exc),
                     cycle_state=dataclasses.asdict(cycle), samples=samples))
        if proc is not None:
            r.ps('post-stop-pnp', p.PS_USB, timeout=30, required=False)
            r.ps('post-stop-pnp-events', p.PS_PNP_EVENTS, timeout=30, required=False)
            r.command('post-stop-kernel-journal-json', wifi+['journalctl -k -b --no-pager -o json'], timeout=30, required=False)
            r.command('post-stop-adbd-journal-json', wifi+['journalctl -b -u gts9-adbd.service --no-pager -o json'], timeout=30, required=False)
        raise
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=5)
            p.write_json(folder/'follow-end.json', dict(ended_utc=p.now(), host_pid=proc.pid,
                         returncode=proc.returncode, host_reader_terminated=True, device_service_restarted=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', type=Path, required=True)
    parser.add_argument('--cycle-dir', type=Path, required=True)
    args = parser.parse_args()
    policy = load_registration(args.registration)
    root = args.registration.parent.resolve()
    folder = args.cycle_dir.resolve()
    if folder.parent != root or folder.name not in ('cycle-01', 'cycle-02', 'cycle-03'):
        raise ValueError('cycle directory must be a registered direct child')
    if any(root.glob('cycle-*/failure.json')):
        raise ValueError('series already stopped on a non-clean cycle')
    index = int(folder.name.rsplit('-', 1)[1])
    for previous in range(1, index):
        prior = root / f'cycle-{previous:02}'
        summary = json.loads((prior/'summary.json').read_text())
        gate = json.loads((prior/'post-cycle/summary.json').read_text())
        if (summary['verdict'] != 'window-passed-awaiting-post-cycle-identity-gate' or
                gate['verdict'] != 'passed' or boot_id(gate['boot_id']) != boot_id(policy['boot_id'])):
            raise ValueError('previous cycle is not clean')
    print(json.dumps(run_cycle(args.cycle_dir, policy), indent=2))


if __name__ == '__main__':
    main()
