#!/usr/bin/env python3
"""Restore accepted GNOME startup and the ms terminal shortcut; no reboot."""
import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

SCHEMA = 'org.gnome.settings-daemon.plugins.media-keys'
SHORTCUT = '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/gts9-terminal/'

def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--notes-sha256', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('root required for systemd configuration')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != args.boot_id:
        raise ValueError('boot changed')
    digest = lambda value: hashlib.sha256(value).hexdigest()
    if digest(gzip.decompress(Path('/proc/config.gz').read_bytes())) != args.config_sha256 or digest(Path('/sys/kernel/notes').read_bytes()) != args.notes_sha256:
        raise ValueError('kernel identity changed')
    if not Path('/usr/bin/kgx').is_file():
        raise ValueError('GNOME Console not installed')
    # The accepted palm pair includes the pen and its own exact kernel/module gate.
    run('systemctl', 'cat', 'gts9-palm.service')
    masks = {}
    for name in ('gdm.service', 'gdm3.service', 'display-manager.service'):
        for prefix in ('/etc/systemd/system', '/run/systemd/system'):
            path = Path(prefix)/name
            if path.is_symlink():
                masks[str(path)] = os.readlink(path)
                if masks[str(path)] not in ('/dev/null', '/usr/lib/systemd/system/gdm.service', '/lib/systemd/system/gdm.service', 'gdm.service'):
                    raise ValueError('unexpected GDM link: '+str(path))
            elif path.exists():
                raise ValueError('custom GDM unit requires review: '+str(path))
    args.evidence.mkdir(parents=True, exist_ok=False)
    user = ['runuser', '-u', 'ms', '--', 'dbus-run-session', '--', 'gsettings']
    raw = run(*user, 'get', SCHEMA, 'custom-keybindings')
    bindings = ast.literal_eval(raw.removeprefix('@as '))
    if not isinstance(bindings, list) or any(not isinstance(x, str) for x in bindings):
        raise ValueError('invalid shortcut list')
    custom_schema = SCHEMA+'.custom-keybinding:'+SHORTCUT
    previous = {key: run(*user, 'get', custom_schema, key) for key in ('name', 'command', 'binding')}
    before = dict(boot_id=args.boot_id, default_target=run('systemctl', 'get-default'), masks=masks,
                  custom_keybindings=raw, terminal=previous)
    (args.evidence/'before.json').write_text(json.dumps(before, indent=2)+'\n')
    # Never replace an unrelated user shortcut collection.
    if SHORTCUT not in bindings:
        bindings.append(SHORTCUT)
    for key, value in (('name', 'Terminal'), ('command', '/usr/bin/kgx'), ('binding', '<Primary><Alt>t')):
        run(*user, 'set', custom_schema, key, repr(value))
    run(*user, 'set', SCHEMA, 'custom-keybindings', repr(bindings))
    run('systemctl', 'unmask', 'gdm.service', 'gdm3.service', 'display-manager.service')
    link = Path('/etc/systemd/system/display-manager.service')
    if not link.exists():
        link.symlink_to('/usr/lib/systemd/system/gdm.service')
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'gts9-palm.service')
    run('systemctl', 'set-default', 'graphical.target')
    # Gate input before starting the login screen. No restart/automatic reboot.
    run('systemctl', 'start', 'gts9-palm.service')
    run('systemctl', 'start', 'gdm.service')
    after = dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 default_target=run('systemctl', 'get-default'),
                 display_manager=os.readlink(link),
                 services=run('systemctl', 'is-active', 'gdm.service', 'gts9-palm.service', 'ssh.service', 'gts9-adbd.service'),
                 custom_keybindings=run(*user, 'get', SCHEMA, 'custom-keybindings'),
                 binding=run(*user, 'get', custom_schema, 'binding'),
                 command=run(*user, 'get', custom_schema, 'command'))
    if after['boot_id'] != args.boot_id or after['services'].splitlines() != ['active']*4:
        raise ValueError('same-boot desktop/rescue verification failed')
    (args.evidence/'after.json').write_text(json.dumps(after, indent=2)+'\n')
    print(json.dumps(after))

if __name__ == '__main__':
    main()
