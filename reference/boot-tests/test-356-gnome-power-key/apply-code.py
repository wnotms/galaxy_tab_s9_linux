from pathlib import Path
import gzip, hashlib, json, re, subprocess, time

POLICY_B64='IyBYNzEwOiBndHM5LXBvd2VyLWtleS5zZXJ2aWNlIG93bnMgc2hvcnQgcHJlc3NlcyAoYmFja2xpZ2h0IG9ubHkpLgojIEdOT01FIDQ4IHRyZWF0cyB0aGUgUXVhbGNvbW0gdm0tb3RoZXIgY2hhc3NpcyBhcyBhIFZNOiBldmVyeSBhY3Rpb24gZXhjZXB0CiMgJ25vdGhpbmcnIGlzc3VlcyBQb3dlck9mZiwgZXZlbiBpZiBsb2dpbmQncyBIYW5kbGVQb3dlcktleSBpcyBpZ25vcmUuCiMgS2VlcCBrZXJuZWwvUE1JQyBsb25nLWhvbGQgcmVjb3ZlcnkgYW5kIHRoZSBleGlzdGluZyBiYWNrbGlnaHQgaGVscGVyIGludGFjdC4KW29yZy5nbm9tZS5zZXR0aW5ncy1kYWVtb24ucGx1Z2lucy5wb3dlcl0KcG93ZXItYnV0dG9uLWFjdGlvbj0nbm90aGluZycK'
BOOT = '1adc0f13-a210-4856-bb15-c6e9df17867a'
CONFIG = '51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a'
NOTES = '03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95'
root = Path('/var/log/gts9-test356-power-key')
battery = Path('/sys/class/power_supply/sm5714-battery')
masks = [Path('/etc/systemd/system') / n for n in
         ('gdm.service', 'gdm3.service', 'display-manager.service')]

def run(name, argv, check=True):
    p = subprocess.run(argv, capture_output=True, timeout=15)
    (root / (name + '.stdout')).write_bytes(p.stdout)
    (root / (name + '.stderr')).write_bytes(p.stderr)
    (root / (name + '.command.json')).write_text(json.dumps(
        dict(argv=argv, returncode=p.returncode, monotonic=time.monotonic())))
    if check and p.returncode:
        raise RuntimeError(name + ' failed: ' + str(p.returncode))
    return p

def telemetry():
    return {n: (battery / n).read_text().strip() for n in
            ('capacity', 'temp', 'health', 'status', 'current_now')}

def restore_masks():
    for p in masks:
        if not p.exists() and not p.is_symlink():
            p.symlink_to('/dev/null')
        assert p.is_symlink() and str(p.readlink()) == '/dev/null'
    run('restore-mask-reload', ['systemctl', 'daemon-reload'])

assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT
assert hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest() == CONFIG
assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest() == NOTES
assert all(p.is_symlink() and str(p.readlink()) == '/dev/null' for p in masks)
assert not Path('/dev/hvc0').exists()
assert not Path('/sys/class/tty/hvc0').exists()
entry = telemetry()
assert entry['health'] == 'Good' and int(entry['temp']) < 380 and int(entry['capacity']) >= 20
root.mkdir(exist_ok=False)
state = dict(boot_id=BOOT, config_sha256=CONFIG, notes_sha256=NOTES,
             entry_battery=entry, automatic_stop_seconds=None, verdict='STARTING')
started = False
schema_dir = Path('/usr/share/glib-2.0/schemas')
policy = schema_dir / '99-gts9-power-key.gschema.override'
assert not policy.exists() and not policy.is_symlink()
policy_bytes = __import__('base64').b64decode(POLICY_B64)
user_old_values = {}
policy_written = False

def user_cmd(user, *args):
    return ['runuser', '-u', user, '--', 'env', '-u', 'XDG_RUNTIME_DIR',
            '-u', 'DBUS_SESSION_BUS_ADDRESS', 'dbus-run-session', '--', *args]

try:
    assert run('state-before', ['systemctl', 'is-active', 'gdm.service'], False).stdout.strip() == b'inactive'
    assert not run('failed-before', ['systemctl', '--failed', '--no-legend', '--plain']).stdout.strip()
    cursor = json.loads(run('cursor', ['journalctl', '-n', '1', '-o', 'json', '--no-pager']).stdout)['__CURSOR']
    state['journal_start_cursor'] = cursor
    assert run('backlight-helper', ['systemctl', 'is-active', 'gts9-power-key.service']).stdout.strip() == b'active'
    run('schema-before-check', ['glib-compile-schemas', '--strict', '--dry-run', str(schema_dir)])
    for user in ('ms', 'Debian-gdm'):
        old = run(user+'-dconf-before', user_cmd(user, 'dconf', 'read', '/org/gnome/settings-daemon/plugins/power/power-button-action')).stdout.decode().strip()
        user_old_values[user] = old
        run(user+'-gsettings-before', user_cmd(user, 'gsettings', 'get', 'org.gnome.settings-daemon.plugins.power', 'power-button-action'))
    policy.write_bytes(policy_bytes)
    policy_written = True
    policy.chmod(0o644)
    run('schema-compile', ['glib-compile-schemas', '--strict', str(schema_dir)])
    for user in ('ms', 'Debian-gdm'):
        run(user+'-set-policy', user_cmd(user, 'gsettings', 'set', 'org.gnome.settings-daemon.plugins.power', 'power-button-action', 'nothing'))
        got = run(user+'-effective-policy', user_cmd(user, 'gsettings', 'get', 'org.gnome.settings-daemon.plugins.power', 'power-button-action')).stdout.strip()
        assert got == b"'nothing'", 'effective GNOME policy did not change'
    state['policy_sha256'] = hashlib.sha256(policy_bytes).hexdigest()
    state['effective_power_button_action'] = {'ms': 'nothing', 'Debian-gdm': 'nothing'}
    state['previous_explicit_dconf_values'] = user_old_values
    for p in masks:
        p.unlink()
    run('unmask-reload', ['systemctl', 'daemon-reload'])
    started = True
    run('start', ['systemctl', 'start', 'gdm.service'])
    restore_masks()  # No --now: keep this active desktop; block automatic future starts.
    begin = time.monotonic()
    time.sleep(10)
    assert run('state-after', ['systemctl', 'is-active', 'gdm.service']).stdout.strip() == b'active'
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT
    final = telemetry()
    assert final['health'] == 'Good' and int(final['temp']) < 420
    assert not run('failed-after', ['systemctl', '--failed', '--no-legend', '--plain']).stdout.strip()
    kernel = run('new-kernel', ['journalctl', '-k', '-b', '--after-cursor', cursor, '-o', 'json', '--no-pager']).stdout
    fault = re.compile(r'soft lockup|rcu.*(?:stall|INFO)|CSD.*(?:stall|non.respon)|Kernel panic|Oops:|BUG:|Internal error|SError|GPU fault|GPU hang|GPU recovery', re.I)
    faults = [json.loads(line)['MESSAGE'] for line in kernel.splitlines() if line and fault.search(str(json.loads(line).get('MESSAGE', '')))]
    state['new_kernel_faults'] = faults
    assert not faults, 'new kernel fault'
    run('shell-journal', ['journalctl', '-b', '--after-cursor', cursor, '_COMM=gnome-shell', '-o', 'json', '--no-pager'])
    run('gdm-journal', ['journalctl', '-b', '-u', 'gdm.service', '-o', 'short-monotonic', '--no-pager'])
    run('sessions', ['loginctl', 'list-sessions', '--no-legend'])
    state.update(verdict='GNOME_POWER_KEY_POLICY_APPLIED_AWAITING_PHYSICAL_CONFIRMATION', initial_observation_seconds=time.monotonic()-begin,
                 final_battery=final, final_gdm='active', persistent_masks_restored=True, touch_loaded=False)
except BaseException as exc:
    state.update(verdict='STOP_ACTIVATION_FAILED', error=repr(exc))
    if started:
        run('stop-on-failure', ['systemctl', 'stop', 'gdm.service'], False)
    restore_masks()
    if policy_written:
        for user, old in user_old_values.items():
            argv = user_cmd(user, 'dconf', 'write', '/org/gnome/settings-daemon/plugins/power/power-button-action', old) if old else user_cmd(user, 'dconf', 'reset', '/org/gnome/settings-daemon/plugins/power/power-button-action')
            run(user+'-restore-policy', argv, False)
        policy.unlink()
        run('restore-schema-compile', ['glib-compile-schemas', '--strict', str(schema_dir)], False)
    raise
finally:
    (root / 'summary.json').write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps(state), flush=True)
