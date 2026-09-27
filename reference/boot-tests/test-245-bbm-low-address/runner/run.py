import control
import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

def classify(text):
    bad = [x for x in ("CPUS still haven't responded", 'BUG: workqueue lockup',
        'soft lockup - CPU', 'detected stalls', 'self-detected stall', 'CSD lock',
        'Kernel panic - not syncing', 'Oops:') if x in text]
    if bad: return 'failure_observed', bad
    suspect = [x for x in ('vblank wait timed out', 'CTL_START timeout',
        'Timeout waiting for hardware cmd interrupt', 'rpmh_rsc_send_data: Error') if x in text]
    if re.search(r'mmc\d.*(?:timed out|timeout)', text, re.I): suspect.append('MMC timeout')
    return ('suspect', suspect) if suspect else (None, [])

def run(production=False):
    phase = 'production' if production else 'target-run'
    p = control.P / phase
    p.mkdir(exist_ok=False)
    verdict = {'cpu_stall_repair_established': False, 'budget_uptime_seconds': 120}
    for i in range(16):
        s, status = control.shell(phase, f'poll-{i}',
            'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id',
            timeout=4, check=False)
        lines = s.splitlines()
        if status == 0 and len(lines) == 3 and lines[0] == lines[-1]: break
        time.sleep(3)
    else: raise RuntimeError('No attributed boot; stop for recovery review')
    boot = lines[0]
    verdict['boot_id'] = boot
    verdict['first_connection_uptime'] = float(lines[1].split()[0])
    cmd = [control.ADB, '-s', control.LIVE, 'shell',
           f'journalctl -b {boot.replace("-", "")} -k -f -n all --no-pager -o json']
    stream = p / 'kernel-follow.jsonl'
    procmeta = {'command': cmd, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    started = time.monotonic()
    with stream.open('wb') as out, (p / 'kernel-follow.stderr').open('wb') as err:
        proc = subprocess.Popen(cmd, stdout=out, stderr=err)
        try:
            if not production:
                subprocess.run([sys.executable, 'out/test245/target_preflight.py'], check=True, timeout=25)
                identity = json.loads((control.P / 'target/identity.json').read_text())
                assert identity['boot_id'] == boot
            else:
                s, _ = control.shell(phase, 'profile',
                    'cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /sys/module/ramoops/parameters/ecc; test ! -e /sys/module/gts9_pnmi_test/parameters/enable; echo helper_absent=$?', timeout=6)
                assert s.splitlines() == ['0','0','0','0','0','helper_absent=0']
            workload_end = None
            for i in range(30):
                s, status = control.shell(phase, f'identity-{i}',
                    'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id', timeout=5, check=False)
                kind, markers = classify(stream.read_text(errors='replace'))
                if kind:
                    verdict.update(verdict=kind, markers=markers)
                    if kind == 'failure_observed': time.sleep(20)
                    break
                assert status == 0 and len(s.splitlines()) == 3, 'identity response lost'
                lines = s.splitlines()
                assert lines[0] == lines[-1] == boot, 'boot changed'
                uptime = float(lines[1].split()[0]); verdict['uptime'] = uptime
                assert proc.poll() is None and stream.stat().st_size, 'stream stopped/empty'
                print(phase, boot, uptime, flush=True)
                if not production and workload_end is None and uptime >= 60:
                    assert uptime <= 90, 'readiness exceeded startup budget'
                    text = stream.read_text(errors='replace')
                    assert '2645198' in text and 'GTS9_LA_READY' in text
                    s, _ = control.shell('workload', 'preflight',
                        'cat /proc/sys/kernel/random/boot_id; timeout 5 systemctl --failed --no-pager; cat /sys/kernel/tracing/kprobe_events; cat /proc/sys/kernel/random/boot_id', timeout=8)
                    assert s.splitlines()[0] == s.splitlines()[-1] == boot
                    assert '0 loaded units listed.' in s and 'gts9_bbm_low_245' not in s
                    helper = control.ROOT / 'reference/offline-reviews/20260928-bbm-low-address/low_address.py'
                    digest = hashlib.sha256(helper.read_bytes()).hexdigest()
                    control.capture('workload', 'push', ['push', 'D:\\android\\gts9-test245\\low_address.py', '/tmp/gts9-bbm-low245.py'], timeout=8)
                    s, _ = control.shell('workload', 'hash', 'sha256sum /tmp/gts9-bbm-low245.py', timeout=5)
                    assert s.split()[0] == digest
                    notes = hashlib.sha256(Path('out/test240/kernel-notes.bin').read_bytes()).hexdigest()
                    command = f'timeout -k 2 18 python3 /tmp/gts9-bbm-low245.py --run --expected-boot {shlex.quote(boot)} --expected-notes-sha256 {notes}'
                    s, rc = control.shell('workload', 'run', command, timeout=20, check=False)
                    print(s, flush=True)
                    assert rc == 0, 'workload failed: no retry without evidence review'
                    report = json.loads(s)
                    assert report['coverage']['result'] == 'low_address_path_covered' and not report['cleanup_errors'] and 'error' not in report
                    s, _ = control.shell('workload', 'after',
                        'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/kernel/tracing/kprobe_events; test ! -d /sys/kernel/tracing/instances/gts9_bbm_low_245; echo instance_absent=$?; cat /proc/sys/kernel/random/boot_id', timeout=6)
                    assert s.splitlines()[0] == s.splitlines()[-1] == boot
                    assert 'gts9_bbm_low_245' not in s and 'instance_absent=0' in s
                    workload_end = float(s.splitlines()[1].split()[0])
                    assert workload_end <= 90, 'workload exceeded fixed timing gate'
                    verdict['workload_end_uptime'] = workload_end
                if uptime >= 120:
                    assert production or workload_end is not None and uptime - workload_end >= 30
                    verdict['verdict'] = 'clean_window'
                    break
                time.sleep(min(5, max(0, 120-uptime)))
            else: raise RuntimeError('startup budget exhausted')
            j, status = control.shell(phase, 'final-json', f'journalctl -b {boot.replace("-", "")} -k --no-pager -o json', timeout=10, check=False)
            kind, markers = classify(j + stream.read_text(errors='replace'))
            if kind: verdict.update(verdict=kind, markers=markers)
            assert status == 0 and j, 'final journal unavailable'
            rows = [json.loads(line) for line in j.splitlines()]
            assert rows and all(row['_BOOT_ID'] == boot.replace('-', '') for row in rows)
            verdict['final_json_rows'] = len(rows)
            verdict['source_timestamp_rows'] = sum('_SOURCE_BOOTTIME_TIMESTAMP' in row for row in rows)
            s, _ = control.shell(phase, 'final-health',
                'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; timeout 5 systemctl --failed --no-pager; cat /proc/sys/kernel/random/boot_id', timeout=8)
            assert s.splitlines()[0] == s.splitlines()[-1] == boot and '0 loaded units listed.' in s
            history, _ = control.shell(phase, 'boot-list', 'journalctl --list-boots --no-pager', timeout=8)
            ids = [line.split()[1] for line in history.splitlines() if re.match(r'^\s*-?\d+\s+[0-9a-f]{32}\s', line)]
            assert ids[-1] == boot.replace('-', ''), 'unexpected successor'
        except Exception as error:
            verdict.setdefault('verdict', 'inconclusive')
            if verdict['verdict'] == 'clean_window': verdict['verdict'] = 'inconclusive'
            verdict['error'] = repr(error)
        finally:
            was_running = proc.poll() is None
            if was_running: proc.terminate()
            try: status = proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill(); status = proc.wait(timeout=3)
            procmeta.update(status=status, host_stopped_at_observation_end=was_running,
                            elapsed_host_seconds=time.monotonic()-started)
            (p / 'kernel-follow.json').write_text(json.dumps(procmeta, indent=2)+'\n')
            (p / 'verdict.json').write_text(json.dumps(verdict, indent=2)+'\n')
    print(verdict, flush=True)
    assert verdict.get('verdict') == 'clean_window', 'stop for evidence/recovery review'
    if not production:
        control.shell('workload', 'remove-temp', 'rm /tmp/gts9-bbm-low245.py', timeout=5)

if __name__ == '__main__':
    run(production='--production' in sys.argv)
