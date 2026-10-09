#!/usr/bin/env python3
"""One boot-bound read-only native identity/health snapshot; no activation."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess


def text(name):
    return Path(name).read_text().strip()


def command(argv, required=True):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=8)
    if required and p.returncode:
        raise ValueError(str(argv)+': '+p.stderr)
    return p.stdout.strip()


def capture():
    boot = text('/proc/sys/kernel/random/boot_id')
    config = gzip.decompress(Path('/proc/config.gz').read_bytes())
    battery = dict(line.split('=', 1) for line in text('/sys/class/power_supply/sm5714-battery/uevent').splitlines())
    native = {}
    socs = list(Path('/sys/devices').glob('soc*'))
    socs = [p for p in socs if (p/'soc_id').is_file()]
    if len(socs) == 1:
        native = dict(boot_id=boot, **{n:text(socs[0]/n) for n in ('family', 'machine', 'soc_id')})
        debug = Path('/sys/kernel/debug/qcom_socinfo')
        for n in ('info_fmt', 'hardware_platform', 'hardware_platform_subtype', 'platform_version'):
            native[n] = text(debug/n)
    adsp = [dict(path=str(p), name=text(p/'name'), state=text(p/'state'), firmware=text(p/'firmware'))
            for p in Path('/sys/class/remoteproc').glob('remoteproc*') if text(p/'name') == 'adsp']
    gpu_power = {}
    for device in ('3d00000.gpu', '3d6a000.gmu'):
        directory = Path('/sys/bus/platform/devices') / device / 'power'
        gpu_power[device] = {name:text(directory/name) for name in
            ('runtime_status', 'control', 'runtime_active_time', 'runtime_suspended_time')}
    result = dict(boot_id=boot, machine_id=text('/etc/machine-id'),
        uname=command(['uname', '-a']), cmdline=text('/proc/cmdline'), uptime=float(text('/proc/uptime').split()[0]),
        config_sha256=hashlib.sha256(config).hexdigest(), notes_sha256=hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest(),
        dcc_absent=b'# CONFIG_HVC_DCC is not set\n' in config and not Path('/dev/hvc0').exists() and not Path('/sys/class/tty/hvc0').exists() and command(['systemctl', 'is-active', 'serial-getty@hvc0.service'], False) != 'active',
        battery=battery, network=command(['ip', '-4', '-o', 'addr']),
        services={n:command(['systemctl', 'is-active', n], False) for n in ('ssh', 'gts9-adbd', 'gts9-usb-acm', 'gdm', 'gts9-pen', 'gts9-palm')},
        roles={n:text('/sys/class/typec/port0/'+n) for n in ('power_role', 'data_role')},
        failed_units=command(['systemctl', '--failed', '--no-legend', '--plain', '--no-pager']),
        host_key=text('/etc/ssh/ssh_host_ed25519_key.pub'), direct_default=text('/sys/module/sm5440_fedora/parameters/direct_charge'),
        adsp=adsp, native_socinfo=native, fastrpc=[str(p) for p in Path('/dev').glob('fastrpc*')],
        gpu_power=gpu_power)
    if text('/proc/sys/kernel/random/boot_id') != boot:
        raise ValueError('mixed snapshot boot')
    return result


if __name__ == '__main__':
    print(json.dumps(capture(), indent=2))
