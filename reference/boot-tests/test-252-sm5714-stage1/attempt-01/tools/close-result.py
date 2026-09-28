"""Reconcile Test252 stopped physical evidence; no device calls."""
from pathlib import Path
import sys, json, hashlib, base64
sys.path.insert(0, str(Path('scripts').resolve()))
import production_reboot_stability as p
p.P = p.TEST250_ROOT / 'attempt-05'
baseline = p.baseline()
parent = Path('reference/boot-tests/test-252-sm5714-stage1')
r = parent / 'attempt-01'
f = r / 'usb-reconnect/post-stop'
art = json.loads((parent / 'ARTIFACTS.json').read_text())
initial = json.loads((r / 'boot/acceptance/summary.json').read_text())
boot = initial['boot_id']
state = json.loads((f / 'production-state.json').read_text())
assert state['identity_ok'] and state['boot_id'] == boot
cfg = (f / 'embedded-config.txt').read_bytes()
assert hashlib.sha256(cfg).hexdigest() == art['kernel_artifacts']['config']
assert b'# CONFIG_HVC_DCC is not set\n' in cfg
# Windows ADB raw output has CRLF; Wi-Fi SSH output has LF. Compare tokens.
assert (f / 'cmdline.txt').read_text().split() == (r / 'boot/acceptance/cmdline.txt').read_text().split()
expectedparts = {n: v['accepted_device_sha256'] for n, v in art['partitions'].items()}
expectedparts['boot'] = art['partitions']['boot']['candidate_sha256']
assert p.parse_hashes((f / 'partitions.txt').read_text(), '/dev/disk/by-partlabel/') == expectedparts
mods = p.parse_hashes((f / 'module-hashes.txt').read_text(), p.MODULE_ROOT + '/')
assert mods == json.loads((parent / 'validation/module-hashes.json').read_text()) and len(mods) == 181
backup = p.parse_hashes((f / 'backup-module-hashes.txt').read_text(), '/usr/lib/modules/.gts9-test252-original/')
assert backup == baseline['modules'] and len(backup) == 181
assert p.evidence.boot_list((f / 'boot-history.txt').read_text())[-2:] == [initial['before_boot_id'], boot]
raw = (f / 'final-state.txt').read_text()
assert p.evidence.canonical_boot_id(raw.split('__boot_end__\n')[1].strip()) == boot
notes = base64.b64decode(''.join(raw.split('__notes__\n')[1].split('__modules__')[0].split()), validate=True)
assert hashlib.sha256(notes).hexdigest() == art['kernel_notes_sha256']
(f / 'kernel-notes.bin').write_bytes(notes)
scan = json.loads((f / 'kernel-scan.json').read_text())
assert not scan['fault_counts'] and not scan['suspects']
assert not (f / 'systemd-failed.txt').read_text().strip()
assert 'offline' in (f / 'adb-state.txt').read_text()
assert p.bound_banner_ok((f / 'windows-ncm-banner.txt').read_text())
assert p.evidence.canonical_boot_id((f / 'ncm-authenticated-ssh.txt').read_text()) == boot
assert json.loads((f / 'ncm-authenticated-ssh.command.json').read_text())['status'] == 0
assert not p.has_code43((f / 'windows-pnp.txt').read_bytes().decode('gb18030', errors='replace'))
report = dict(verdict='candidate identity verified; physical acceptance stopped on USB ADB offline',
              boot_id=boot, config_sha256=art['kernel_artifacts']['config'], notes_sha256=art['kernel_notes_sha256'],
              exact_config_and_notes_verified=True, cmdline_unchanged=True, partition_hashes=expectedparts,
              module_files_verified=181, rollback_module_files_verified=181, dcc_absent=state['dcc_absent'],
              production_cpu_profile_unchanged=state['profile_ok'], failed_units=[], kernel_fault_counts=scan['fault_counts'],
              kernel_suspects=scan['suspects'], kernel_journal_rows=scan['rows'], boot_attribution_unique=True,
              adb_state='offline', ncm_banner_source_bound=True, ncm_authenticated_ssh=True, wifi_ssh=True,
              windows_code43=False, device_state='candidate retained for offline analysis; no recovery/config/service change',
              candidate_physically_accepted=False, rollback_executed=False)
(f / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
host_log = (r / 'validation/physical-host-tests.log').read_bytes()
assert hashlib.sha256(host_log).hexdigest() == json.loads((r / 'validation/physical-host-tests.json').read_text())['log_sha256']
phases = {name: json.loads((r / name / 'raw-evidence-audit.json').read_text()) for name in ('battery-only', 'charging', 'plug-out')}
summary = dict(test=252, attempt=1, purpose='SM5714 Stage1 battery and ordinary switching-charge physical observation',
               final_verdict='stopped_usb_adb_offline_after_reconnect', stage1_full_acceptance=False,
               observation_stages_completed=3, boot_id=boot, kernel_release=art['kernel_release'], linux_pin=art['linux_pin'],
               kernel_config_sha256=report['config_sha256'], kernel_notes_sha256=report['notes_sha256'],
               modules_verified=181, rollback_modules_verified=181, dcc_absent=True, kernel_fault_counts={},
               failed_units=[], unexpected_reboots=0, phases=phases, first_non_clean_phase='usb-reconnect',
               stop_reason='Windows enumerates both interfaces; native USB ADB remains offline after reconnect; NCM/Wi-Fi SSH available',
               final_identity=report, charger=json.loads((r / 'charger.json').read_text()), charging_start_soc=92, charging_end_soc=97,
               actual_pd_contract_measured=False, measured_vbus_ibus_available=False, hardware_damage_guarantee=False,
               stage2_tcpm_started=False, stage3_sm5440_started=False,
               next_scope='Offline USB ADB/FunctionFS reconnect analysis; no new physical experiment or service change in Test252',
               current_device='Test252 candidate boot + all181 matching module files installed; Test249 rollback retained')
(r / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(report, indent=2))
