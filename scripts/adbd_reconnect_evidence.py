"""Pure Test253 classifier for the owner-adopted existing UPower launch failure."""

UPOWER_UNIT_SHA256 = 'c6d300b60a7dd2e9186152b8bc4fd1557ec2977027d0a24b06304d31f6e4124c'
FAILED_UNIT = 'upower.service loaded failed failed Daemon for power management'


def classify_failed_units(failed, properties, unit_sha256, config):
    if unit_sha256 != UPOWER_UNIT_SHA256:
        raise ValueError('UPower unit identity changed')
    values = dict(line.split('=', 1) for line in properties.splitlines() if '=' in line)
    if values.get('PrivateUsers') != 'yes' or '# CONFIG_USER_NS is not set' not in config.splitlines():
        raise ValueError('UPower namespace prerequisites changed')
    units = [' '.join(line.split()) for line in failed.splitlines() if line.strip()]
    if not units:
        return {'classification': 'no-failed-units', 'failed_units': []}
    if units != [FAILED_UNIT] or values.get('Result') != 'exit-code' or values.get('ExecMainStatus') != '217':
        raise ValueError('new or changed systemd failure')
    return {'classification': 'known-upower-user-namespace-prerequisite', 'failed_units': units,
            'upower_unresolved': True, 'daemon_executed': False}


def same_cmdline(left, right):
    """Normalize only ADB shell CRLF framing; preserve every cmdline byte."""
    return left.replace(b'\r\n', b'\n') == right.replace(b'\r\n', b'\n')
