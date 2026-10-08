#!/usr/bin/env python3
"""Select the accepted interim or native Escape mapping on an exact X710 kernel."""
import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess

OPTION = 'gts9:swap_escape_grave'
SCHEMA = 'org.gnome.desktop.input-sources'
IDENTITIES = {
    'native': ('599ca47ab41a29469c3d5830e475049fca9f33bd2ab0923ad014e5ba3fa6ec6c',
               '3fe9191a85ec0eaecbe8c24dd2e58b7281050876adbc60d8f21c73f5b917c5bd'),
    'interim': ('51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a',
                '03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95'),
}


def options(raw):
    value = ast.literal_eval(raw.removeprefix('@as '))
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError('invalid XKB option array')
    return value


def select(raw, mode):
    current = options(raw)
    if mode == 'native':
        return [x for x in current if x != OPTION]
    if mode == 'interim':
        return current if OPTION in current else current + [OPTION]
    raise ValueError('unknown mapping')


def apply(mode, settings, check, record=lambda before, sources: None):
    """Save before setting, preserve input sources/other options, verify readback."""
    check()
    before = settings('get', SCHEMA, 'xkb-options')
    sources = settings('get', SCHEMA, 'sources')
    after = select(before, mode)
    record(before, sources)
    check()
    if after != options(before):
        try:
            settings('set', SCHEMA, 'xkb-options', repr(after))
            check()
            if options(settings('get', SCHEMA, 'xkb-options')) != after:
                raise ValueError('XKB settings readback mismatch')
            if settings('get', SCHEMA, 'sources') != sources:
                raise ValueError('input sources changed during transition')
        except Exception:
            # Never blindly apply the old mapping after an unexplained reboot.
            check()
            settings('set', SCHEMA, 'xkb-options', before)
            raise
    return dict(mode=mode, before=before, after=after, sources=sources,
                changed=after != options(before))


def settings_command(uid, home, active_bus):
    command = ['runuser', '-u', 'ms', '--', 'env', '-u', 'DBUS_SESSION_BUS_ADDRESS',
               '-u', 'XDG_RUNTIME_DIR', 'HOME=' + home,
               'XDG_CONFIG_HOME=' + home + '/.config']
    if active_bus:
        command += ['DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/' + str(uid) + '/bus',
                    'gsettings']
    else:
        command += ['dbus-run-session', '--', 'gsettings']
    return command


def identity(mode, boot, root=Path('/'), machine=None, release=None):
    def read(name):
        return (root / name).read_bytes()
    if read('proc/sys/kernel/random/boot_id').decode().strip() != boot:
        raise ValueError('boot changed')
    if read('etc/machine-id').decode().strip() != '3c2a1b8f2d624db4b5ffdc836050fcf6':
        raise ValueError('unqualified machine')
    if (machine or os.uname().machine) != 'aarch64' or (release or os.uname().release) != '7.2.0-rc3-gts9wifi-dirty':
        raise ValueError('unqualified kernel release')
    if b'samsung,gts9wifi' not in read('sys/firmware/devicetree/base/compatible').split(b'\0'):
        raise ValueError('unqualified DT model')
    config = gzip.decompress(read('proc/config.gz'))
    notes = read('sys/kernel/notes')
    if tuple(hashlib.sha256(x).hexdigest() for x in (config, notes)) != IDENTITIES[mode]:
        raise ValueError('kernel config/notes do not match mapping')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=tuple(IDENTITIES))
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('root required')
    check = lambda: identity(args.mode, args.boot_id)
    check()
    ms = pwd.getpwnam('ms')
    if ms.pw_uid == 0 or ms.pw_dir != '/home/ms':
        raise ValueError('unexpected GNOME account')
    bus = Path('/run/user') / str(ms.pw_uid) / 'bus'
    # A controlled text boot can use a private short-lived bus to write ms's
    # dconf before first GNOME login. Never inherit root's session bus.
    command = settings_command(ms.pw_uid, ms.pw_dir, bus.exists())
    def settings(*argv):
        return subprocess.check_output(command + list(argv), text=True,
                                       timeout=10).strip()
    if args.mode == 'interim':
        here = Path(__file__).resolve().parent
        for target, source in (('rules/evdev', 'evdev'), ('symbols/gts9', 'gts9')):
            if (Path(ms.pw_dir) / '.config/xkb' / target).read_bytes() != (here / source).read_bytes():
                raise ValueError('accepted interim XKB files missing/altered')
    args.evidence.mkdir(parents=True, exist_ok=False)
    def record(before, sources):
        # Persist exactly the settings used by apply before its first mutation.
        (args.evidence / 'before.json').write_text(json.dumps(dict(
            mode=args.mode, boot_id=args.boot_id, xkb_options=before,
            sources=sources), indent=2) + '\n')
    result = apply(args.mode, settings, check, record)
    result.update(boot_id=args.boot_id, physical_confirmation_pending=True)
    (args.evidence / 'after.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
