#!/usr/bin/env python3
"""Exercise real proxy handlers over an owned private D-Bus; no tablet access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time
import uuid

IMAGE = 'sha256:1b148977ce4662a9d9a28e44b92d3499934ce08fc11f096e32d0fc911b5b79b0'


def run(build):
    records = []
    plans = [('original', 'during-discovery', 'g_ptr_array_add'),
             ('reference', 'during-discovery', None),
             ('reference', 'release-before-open', 'sensor_device'),
             ('reference', 'vanish-before-open', 'sensor_device')]
    plans += [('final', mode, None) for mode in (
        'no-clients', 'before-discovery', 'during-discovery', 'during-open',
        'release-before-open', 'vanish-before-open', 'after-open', 'open-failure')]
    with tempfile.TemporaryDirectory(prefix='bus-', dir=build) as directory:
        bus = Path(directory)
        with (build / 'private-bus.stderr').open('wb') as errors:
            daemon = subprocess.Popen(['dbus-daemon', '--session', '--nofork',
                '--print-address=1', '--address=unix:path=' + str(bus / 'socket')],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors,
                start_new_session=True)
            try:
                if not select.select([daemon.stdout], [], [], 5)[0]:
                    raise RuntimeError('private bus did not publish address')
                address = daemon.stdout.readline().decode().strip()
                if daemon.poll() is not None or not address.startswith('unix:path='):
                    raise RuntimeError('private bus failed')
                for profile, mode, expected_fault in plans:
                    assert daemon.poll() is None, 'owned bus unexpectedly exited'
                    container = 'proxy-claim-' + uuid.uuid4().hex
                    command = ['docker', 'run', '--rm', '--name', container, '--network=none',
                        '--security-opt=no-new-privileges',
                        '--user', str(os.getuid()) + ':' + str(os.getgid()),
                        '-e', 'G_DEBUG=fatal-criticals',
                        '-v', str(build) + ':/output:ro', '-v', str(bus) + ':/bus:ro',
                        IMAGE, 'sh', '-c',
                        'ulimit -c 0\nexec timeout --signal=KILL 6s qemu-aarch64 -L /usr/aarch64-linux-gnu "$@"',
                        'claim-test', '/output/claim-' + profile, 'unix:path=/bus/socket', mode]
                    start = time.monotonic()
                    try:
                        result = subprocess.run(command, capture_output=True, text=True, timeout=12)
                    except subprocess.TimeoutExpired as failure:
                        row = dict(profile=profile, case=mode, timed_out=True,
                                   stdout=(failure.stdout or b'').decode(errors='replace'),
                                   stderr=(failure.stderr or b'').decode(errors='replace'))
                        records.append(row)
                        (build / 'CLAIM_TESTS.partial.json').write_text(json.dumps(records, indent=2) + '\n')
                        raise RuntimeError('owned case timed out: ' + profile + '/' + mode) from None
                    finally:
                        subprocess.run(['docker', 'rm', '-f', container], capture_output=True, timeout=5)
                    row = dict(profile=profile, case=mode, expected_fault=expected_fault,
                               returncode=result.returncode, stdout=result.stdout,
                               stderr=result.stderr, seconds=time.monotonic() - start)
                    records.append(row)
                    (build / 'CLAIM_TESTS.partial.json').write_text(json.dumps(records, indent=2) + '\n')
                    if expected_fault:
                        assert result.returncode in (133, 134) and expected_fault in result.stderr, (profile, mode, 'expected fatal critical absent; see partial report')
                    else:
                        assert result.returncode == 0, (profile, mode, 'case failed; see partial report')
                        row['observation'] = json.loads(result.stdout)
            finally:
                daemon.terminate()
                daemon.wait(timeout=5)
                daemon.stdout.close()
                if (bus / 'socket').exists(): (bus / 'socket').unlink()
    report = dict(successful=True, cases=records, device_operations=False,
                  hardware_tested=False, private_bus_stopped=True,
                  authorization_mocked=True, sensor_IO_mocked=True,
                  GUdev_identity_mocked=True,
                  binary_sha256={profile: hashlib.sha256((build / ('claim-' + profile)).read_bytes()).hexdigest()
                                 for profile in ('original', 'reference', 'final')},
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (build / 'CLAIM_TESTS.json').write_text(json.dumps(report, indent=2) + '\n')
    print('12 real D-Bus/ARM64 cases qualified; private bus stopped')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    run(args.build.resolve())
