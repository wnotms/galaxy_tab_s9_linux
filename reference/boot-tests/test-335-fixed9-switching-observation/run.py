#!/usr/bin/env python3
"""Append-only host transport for Test335; never flash, reboot or program charging."""
import argparse
import asyncio
import hashlib
import json
import queue
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

R = Path(__file__).resolve().parent
ROOT = R.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from charging_wifi_discovery import Settings, Identity, discover


def verify_registration():
    hashes = json.loads((R / 'REGISTRATION_SHA256.json').read_text())
    for name, digest in hashes.items():
        if hashlib.sha256((R / name).read_bytes()).hexdigest() != digest:
            raise ValueError('registration drift: ' + name)
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', str(R)], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', 'merge-base', '--is-ancestor', 'HEAD', 'origin/test'], cwd=ROOT, check=True)
    return json.loads((R / 'registration.json').read_text())


def accepted(raw, returncode, phase):
    rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
    verdicts = [x for x in rows if x.get('kind') == 'verdict']
    if returncode != 0 or len(verdicts) != 1 or verdicts[0].get('verdict') != 'PASS' or verdicts[0].get('phase') != phase:
        raise ValueError('non-clean observer result')
    if not all(any(x.get('kind') == k for x in rows) for k in ('armed', 'sample', 'journal-before', 'journal-after', 'systemd-failed')):
        raise ValueError('missing observer evidence')
    return verdicts[0]


def main(phase):
    plan = verify_registration()
    folder = R / phase
    if phase == 'discharge':
        prior = json.loads((R / 'charge/summary.json').read_text())
        if prior['verdict'] != 'PASS':
            raise ValueError('charge first non-clean: no next stage')
    folder.mkdir(exist_ok=False)
    result = dict(verdict='STOP', phase=phase, PPS=False, pump_ON=False, reboot=False, flash=False)
    proc = None
    try:
        settings = Settings(plan['previous_ip'], Path(plan['key']), Path(plan['known_hosts']), plan['alias'])
        expected = Identity(plan['machine_id'], plan['config_sha256'], plan['notes_sha256'], plan['boot_id'])
        with (folder / 'discovery.jsonl').open('x') as f:
            def emit(kind, **data):
                f.write(json.dumps(dict(kind=kind, **data)) + '\n')
                f.flush()
            endpoint = asyncio.run(discover(settings, expected, emit))
        if not endpoint:
            raise ValueError('enrolled WiFi unavailable')
        (folder / 'endpoint.json').write_text(json.dumps(endpoint, indent=2) + '\n')
        argv = ['ssh', '-i', plan['key'], '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=3',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + plan['known_hosts'],
                '-o', 'HostKeyAlias=' + plan['alias'], 'root@' + endpoint['address'],
                'python3 - ' + shlex.quote(json.dumps(plan)) + ' ' + shlex.quote(phase)]
        (folder / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
        with (R / 'observe.py').open() as source, (folder / 'stderr.txt').open('x') as err, (folder / 'events.jsonl').open('x') as raw:
            proc = subprocess.Popen(argv, stdin=source, stdout=subprocess.PIPE, stderr=err, text=True)
            lines = queue.Queue()
            def feed():
                for line in proc.stdout:
                    lines.put(line)
                lines.put(None)
            threading.Thread(target=feed, daemon=True).start()
            started = time.monotonic()
            while True:
                if time.monotonic() - started > plan['wait_seconds'] + plan[phase + '_seconds'] + 35:
                    raise TimeoutError('outer collection deadline')
                line = lines.get(timeout=12)
                if line is None:
                    break
                raw.write(line)
                raw.flush()
                row = json.loads(line)
                if row['kind'] in ('armed', 'verdict'):
                    print(json.dumps(row), flush=True)
                elif row['kind'] == 'sample':
                    b, p = row['battery'], row['tcpm']
                    print(json.dumps(dict(kind='progress', uptime=row['uptime'], soc=b['POWER_SUPPLY_CAPACITY'], temp=b['POWER_SUPPLY_TEMP'], current_ua=b['POWER_SUPPLY_CURRENT_NOW'], status=b['POWER_SUPPLY_STATUS'], source=p.get('POWER_SUPPLY_VOLTAGE_NOW'), online=p.get('POWER_SUPPLY_ONLINE'))), flush=True)
            rc = proc.wait(timeout=3)
        result.update(accepted((folder / 'events.jsonl').read_text(), rc, phase))
    except Exception as e:
        result.update(verdict='STOP', host_error=repr(e))
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
        (folder / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    return 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('charge', 'discharge'))
    sys.exit(main(parser.parse_args().phase))
