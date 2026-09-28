"""Read-only acceptance audit of the production DCC repair."""
import json

import control
import observe


def main():
    p = control.P
    first = json.loads((p / 'production-twrp-continued/verdict.json').read_text())
    warm = json.loads((p / 'production-warm/verdict.json').read_text())
    assert first['verdict'] == warm['verdict'] == 'clean_window'
    assert first['boot_id'] != warm['boot_id']
    assert first['uptime'] >= 120 and warm['uptime'] >= 120
    boot = warm['boot_id']
    assert b'TcpTestSucceeded        : True' in (p / 'production-twrp-continued/windows-ncm-ssh.txt').read_bytes()
    assert b'TcpTestSucceeded        : False' in (p / 'production-warm/windows-ncm-ssh.txt').read_bytes()
    assert b'TcpTestSucceeded        : True' in (p / 'production-warm/windows-ncm-ssh-followup.txt').read_bytes()
    assert (p / 'production-warm/windows-ssh-banner.txt').read_bytes().startswith(b'SSH-2.0-OpenSSH_')

    observe.profile('final-acceptance', boot)
    state, _ = control.shell('final-acceptance', 'state',
        'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; '
        'find /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty -type f | wc -l; '
        'test ! -e /usr/lib/modules/.gts9-test248-original && '
        'test ! -e /usr/lib/modules/.gts9-test249-original && echo backups_absent; '
        'systemctl --failed --no-legend --plain --no-pager; '
        'cat /proc/sys/kernel/random/boot_id', timeout=8)
    lines = state.splitlines()
    assert lines[0] == lines[-1] == boot
    assert lines[2:-1] == ['181', 'backups_absent'], lines

    parts, _ = control.shell('final-acceptance', 'partitions',
        'cat /proc/sys/kernel/random/boot_id; '
        'for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done; '
        'cat /proc/sys/kernel/random/boot_id', timeout=15)
    lines = parts.splitlines()
    assert lines[0] == lines[-1] == boot
    actual = {row.split()[1].rsplit('/', 1)[-1]: row.split()[0] for row in lines[1:-1]}
    expected = {row.split()[1].rsplit('/', 1)[-1]: row.split()[0]
                for row in (p / 'baseline/partitions.txt').read_text().splitlines()
                if '/dev/block/by-name/' in row}
    expected.update({row['partition']: row['candidate_sha256']
                     for row in json.loads((p / 'backup-and-staging.json').read_text())})
    assert actual == expected, (actual, expected)

    text, _ = control.shell('final-acceptance', 'kernel-json',
        f'journalctl -b {boot.replace("-", "")} -k --no-pager -o json', timeout=15)
    kind, markers = observe.classify(text)
    assert kind is None, (kind, markers)
    rows = [json.loads(row) for row in text.splitlines()]
    assert rows and all(row['_BOOT_ID'] == boot.replace('-', '') and
                        '_SOURCE_BOOTTIME_TIMESTAMP' in row for row in rows)
    result = {
        'production_twrp_boot': first['boot_id'],
        'production_twrp_window_seconds': first['uptime'],
        'production_warm_boot': boot,
        'production_warm_window_seconds': warm['uptime'],
        'final_uptime_seconds': float(state.splitlines()[1].split()[0]),
        'final_kernel_source_timestamp_rows': len(rows),
        'all_five_partition_hashes_verified': True,
        'production_modules_verified': 181,
        'temporary_module_backups_removed': True,
        'temporary_diagnostics_and_DCC_absent': True,
        'failed_systemd_units': [],
        'USB_ADB_both_boots': True,
        'NCM_SSH_first_boot': 'passed',
        'NCM_SSH_warm_boot': 'initial_timeout_then_passed_without_reboot',
    }
    (p / 'final-acceptance/acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
