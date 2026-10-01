#!/usr/bin/env python3
"""Read-only completion in a fresh evidence directory; no deployment or retry."""
from pathlib import Path

import production_reboot_stability as p
import production_stability_evidence as e
from sm5440_passive_admission import admit
from sm5440_ready_admission import ReadyRecorder


def capture_completion(folder, boot, config_sha256, notes_sha256,
                       known_messages=(), *, recorder_factory=ReadyRecorder):
    """Keep preceding Wi-Fi evidence separate from ADB admission filenames.

    The caller selects a new child directory, e.g. endpoint/device-completion.
    Never reuse the endpoint recorder: admit owns kernel-json/kernel-scan names.
    A host error records incomplete acceptance, not a hardware rollback decision.
    """
    folder = Path(folder)
    if folder.exists():
        raise p.CaptureError(f"completion directory already exists: {folder}")
    rec = recorder_factory(folder)
    try:
        boot = e.canonical_boot_id(boot)
        identity = admit(rec, boot, config_sha256, notes_sha256, known_messages)
        services = rec.adb(
            'dcc-services',
            'set -e; test ! -e /dev/hvc0; test ! -e /sys/class/tty/hvc0; '
            '! systemctl is-active --quiet serial-getty@hvc0.service; '
            'systemctl is-active ssh gts9-adbd; '
            'cat /proc/sys/kernel/random/boot_id', 15)[0].splitlines()
        if services[:2] != ['active', 'active'] or len(services) != 3:
            raise p.CaptureError('ADB/DCC/services incomplete')
        if e.canonical_boot_id(services[2]) != boot:
            raise p.CaptureError('services capture crossed reboot')
        result = {'verdict': 'DEVICE_ACCEPTANCE_COMPLETED', 'boot_id': boot,
                  'identity': identity, 'readiness': rec.ready,
                  'ADB': 'available', 'NCM_SSH': 'authenticated same boot',
                  'DCC': 'absent', 'device_configuration_changed': False,
                  'physical_recovery_time_measured': False}
    except Exception as exc:
        p.write_json(folder / 'summary.json', {
            'verdict': 'DEVICE_CHECK_INCOMPLETE', 'error': str(exc),
            'boot_id': boot, 'device_configuration_changed': False})
        raise
    p.write_json(folder / 'summary.json', result)
    return result
