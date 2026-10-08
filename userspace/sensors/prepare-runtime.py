#!/usr/bin/env python3
"""Stage gated SSC unit overrides offline; no service/device operations."""
import argparse
import hashlib
import json
from pathlib import Path

PREFIX = '/usr/share/qcom/sm8550/Samsung/gts9wifi'
GATE = '/run/gts9-ssc-test/ready'
UNITS = ('pd-mapper.service', 'hexagonrpcd-adsp-rootpd.service',
         'hexagonrpcd-adsp-sensorspd.service', 'iio-sensor-proxy.service')


def overrides():
    # The future registered runner owns the volatile gate and explicit starts.
    # No boot target/dependency added here: do not late-start shared ADSP.
    common = ('[Unit]\nConditionPathExists=' + GATE + '\n'
              'StartLimitIntervalSec=infinity\nStartLimitBurst=1\n\n'
              '[Service]\nRestart=no\nTimeoutStopSec=10s\n')
    result = {}
    for unit in UNITS:
        body = common
        if unit.startswith('hexagonrpcd-adsp-'):
            sensor = ' -s' if 'sensorspd' in unit else ''
            body += ('ExecStart=\nExecStart=/usr/bin/hexagonrpcd '
                     '-f /dev/fastrpc-adsp -d adsp' + sensor + ' -R ' + PREFIX + '\n'
                     'ProtectSystem=strict\nProtectHome=yes\n'
                     'ReadWritePaths=' + PREFIX + '/sensors\n')
        result['etc/systemd/system/' + unit + '.d/90-gts9-controlled-test.conf'] = body.encode()
    # X710 has ADSP, not an SDSP. Do not accidentally activate the packaged unit.
    # This is a drop-in condition rather than a filesystem /dev/null mask.
    result['etc/systemd/system/hexagonrpcd-sdsp.service.d/90-gts9-controlled-test.conf'] = (
        '[Unit]\nConditionPathExists=/run/gts9-ssc-test/sdsp-never-enabled\n\n'
        '[Service]\nRestart=no\n').encode()
    return result


def stage(output):
    output.mkdir(exist_ok=False, parents=True)
    files = overrides()
    for name, data in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o644)
    report = dict(verdict='OFFLINE_SSC_OVERRIDES_NOT_DEPLOYED', device_operations=False,
                  services_started=False, remoteproc_started=False, gate_created=False,
                  prefix=PREFIX, gate=GATE, files={name: hashlib.sha256(data).hexdigest()
                                               for name, data in files.items()})
    (output / 'RUNTIME.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(stage(parser.parse_args().output), indent=2))
