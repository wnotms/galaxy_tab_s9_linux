"""Behavioral replay tests: no SSH, device access, power action or sleeps."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wedge_evidence", ROOT / "scripts/wedge-evidence.py")
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)
A, B, C, D = (str(n) * 32 for n in range(1, 5))


def listing(*ids):
    return "\n".join(f"{i + 1 - len(ids)} {value} date date" for i, value in enumerate(ids))


def clean_log(profile="csd-lock"):
    token = {"csd-lock": "csdlock_debug=1", "baseline": "", "cpuidle-off": "cpuidle.off=1"}[profile]
    return f"[ 1.0] kernel: Kernel command line: {token} panic=10 softlockup_panic=1\n[ 2.0] kernel: booted\n"


def capture(**overrides):
    data = dict(log_ok=True, log_boot_id=B, sample_ok=True, profile="csd-lock",
                window_s=150, uptime_s=195, sample_start_boot_id=B, sample_end_boot_id=B)
    data.update(overrides)
    return data


class AttributionTests(unittest.TestCase):
    def test_clean_boot(self):
        selected = evidence.select(A, listing(A), listing(A, B))
        result = evidence.classify(selected, capture(), clean_log())
        self.assertEqual(result["verdict"], "clean")
        self.assertEqual(selected["target_boot_id"], B)

    def test_panic_before_first_ssh_answer_selects_failed_boot(self):
        selected = evidence.select(A, listing(A), listing(A, B, C))
        log = (ROOT / "reference/boot-tests/test-228-csd-ipi-diagnostic/evidence/wedged-boot-klog-full.txt").read_text()
        result = evidence.classify(selected, capture(sample_start_boot_id=C, sample_end_boot_id=C), log)
        self.assertEqual(selected["target_boot_id"], B)
        self.assertEqual(result["verdict"], "wedge")
        self.assertTrue(result["profile_verified"])
        self.assertGreaterEqual(result["wedge_markers"], 4)

    def test_rotation_of_older_history_does_not_change_target(self):
        self.assertEqual(evidence.select(B, listing(A, B), listing(B, C, D))["target_boot_id"], C)

    def test_missing_anchor_is_not_guessed_from_count(self):
        self.assertIsNone(evidence.select(A, listing(A), listing(B, C))["target_boot_id"])

    def test_no_reboot_or_unreadable_counts_are_not_clean(self):
        for text in ("", "permission denied", listing(A), f"0 {B}\n0 {B}", f"-2 {A}\n0 {B}"):
            with self.subTest(text=text):
                selected = evidence.select(A, listing(A), text)
                self.assertEqual(evidence.classify(selected, capture(), clean_log())["verdict"], "unattributed")

    def test_unexpected_reboot_is_not_proof_of_cpu_wedge(self):
        selected = evidence.select(A, listing(A), listing(A, B, C))
        self.assertEqual(evidence.classify(selected, capture(), clean_log())["verdict"], "unattributed")

    def test_missing_failed_or_wrong_boot_capture_never_clean(self):
        selected = evidence.select(A, listing(A), listing(A, B))
        for change in (dict(log_ok=False), dict(log_boot_id=C), dict(sample_ok=False),
                       dict(sample_end_boot_id=C), dict(uptime_s=""), dict(uptime_s=30),
                       dict(window_s=20), dict(profile="baseline")):
            with self.subTest(change=change):
                self.assertEqual(evidence.classify(selected, capture(**change), clean_log())["verdict"], "unattributed")
        self.assertEqual(evidence.classify(selected, capture(), "")["verdict"], "unattributed")

    def test_csd_alone_is_a_positive_signature(self):
        selected = evidence.select(A, listing(A), listing(A, B))
        self.assertEqual(evidence.classify(selected, capture(),
                         "csd: Detected non-responsive CSD lock (#1)")["verdict"], "wedge")

    def test_timeout_alone_is_suspect_and_encoder_noise_is_clean(self):
        selected = evidence.select(A, listing(A), listing(A, B))
        for text, expected in (("mmc1: Timeout", "suspect"),
                               ("[drm] crtc103 event 1 overflow", "clean")):
            with self.subTest(text=text):
                self.assertEqual(evidence.classify(selected, capture(), clean_log() + text)["verdict"], expected)

    def test_conflicting_or_substring_cmdline_is_not_profile_proof(self):
        for token in ("csdlock_debug=10", "xcsdlock_debug=1", "csdlock_debug=1 csdlock_debug=0"):
            self.assertFalse(evidence.profile_matches("csd-lock", clean_log().replace("csdlock_debug=1", token)))

    def test_cli_replay_uses_no_transport_and_recomputes_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            for name, content in {"before-id.txt": A, "boots-before.txt": listing(A),
                                  "boots-after.txt": listing(A, B), "klog.txt": clean_log(),
                                  "capture.json": json.dumps(capture()),
                                  "verdict.json": '{"verdict":"wedge"}'}.items():
                (path / name).write_text(content)
            result = subprocess.run(["bash", str(ROOT / "scripts/wedge-ssh.sh"), "--replay", tmp],
                                    capture_output=True, text=True, timeout=5, check=True)
            parsed = json.loads(result.stdout)
            self.assertEqual(parsed["verdict"], "clean")
            self.assertEqual(len(parsed["evidence_sha256"]), 5)


class CsdPreflightTests(unittest.TestCase):
    def test_gate_uses_runtime_capability_and_consumed_profile(self):
        """All remote reads are fixture responses; even rejected cases request power."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            mock = path / "ssh-mock"
            mock.write_text('''#!/usr/bin/python3
import os, pathlib, sys
root = pathlib.Path(os.environ['MOCK_ROOT'])
mode = os.environ['MOCK_MODE']
cmd = sys.argv[1]
with (root / 'commands').open('a') as stream: stream.write(cmd + '\\n')
line = 'csdlock_debug=1 panic=10 softlockup_panic=1'
if mode == 'missing_token': line = line.replace('csdlock_debug=1', '')
if mode == 'conflict': line += ' csdlock_debug=0'
if mode == 'missing_recovery': line = line.replace('panic=10', '')
if cmd == 'cat /proc/sys/kernel/random/boot_id': print('1' * 32)
elif cmd == 'cat /proc/cmdline': print(line)
elif cmd.startswith('journalctl -b 0'):
    print('Kernel command line: ' + line)
    if mode == 'unconsumed': print('Unknown kernel command line parameters "csdlock_debug=1"')
elif 'for node in watchdog' in cmd:
    print('0\\n0\\n1\\n10' if mode == 'disarmed' else '1\\n1\\n1\\n10')
elif cmd.startswith('ls /sys/module/smp/parameters/'):
    print('panic_on_ipistall' if mode == 'no_timeout' else 'csd_lock_timeout' if mode == 'no_panic' else 'csd_lock_timeout panic_on_ipistall')
elif cmd.startswith('cat /sys/module/smp/parameters/csd_lock_timeout'): print('1' if mode == 'wrong_timeout' else '5000')
elif cmd.startswith('cat /sys/module/smp/parameters/panic_on_ipistall'): print('1' if mode == 'early_panic' else '0')
else: sys.exit('unexpected mock command: ' + cmd)
''')
            mock.chmod(0o755)
            for mode in ("valid", "missing_token", "conflict", "missing_recovery", "unconsumed",
                         "disarmed", "no_timeout", "no_panic", "wrong_timeout", "early_panic"):
                with self.subTest(mode=mode):
                    (path / "commands").write_text("")
                    env = dict(os.environ, GTS9_SSH=str(mock), MOCK_ROOT=tmp, MOCK_MODE=mode,
                               GTS9_ALLOW_POWER="0" if mode == "valid" else "1",
                               GTS9_SSH_RESULTS=str(path / "results"))
                    result = subprocess.run(["bash", str(ROOT / "scripts/wedge-ssh.sh"), "csd-lock", "1"],
                                            env=env, capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0 if mode == "valid" else 1,
                                     result.stdout + result.stderr)
                    commands = (path / "commands").read_text()
                    self.assertNotIn("systemctl reboot", commands)
                    self.assertNotIn("unexpected mock command", result.stderr)
                    if mode == "valid":
                        self.assertIn("/sys/module/smp/parameters/panic_on_ipistall", commands)


class RunnerIntegrationTests(unittest.TestCase):
    def test_mock_transport_archives_then_replays_without_device(self):
        """Exercise shell orchestration, transport failures and run isolation."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            mock = path / "ssh-mock"
            mock.write_text('''#!/usr/bin/python3
import os, pathlib, sys
root = pathlib.Path(os.environ['MOCK_ROOT'])
state = root / 'rebooted'
cmd = sys.argv[1]
with (root / 'commands').open('a') as stream:
    stream.write(cmd + '\\n')
a, b, c = (str(i) * 32 for i in (1, 2, 3))
mode = os.environ['MOCK_MODE']
now = (c if mode == 'wedge' else b) if state.exists() else a
line = 'Kernel command line: panic=10 softlockup_panic=1'
if cmd == 'systemctl reboot':
    state.touch()
    sys.exit(255)
elif cmd == 'cat /proc/sys/kernel/random/boot_id': print(now)
elif cmd == 'cat /proc/cmdline': print('panic=10 softlockup_panic=1')
elif 'current_driver' in cmd: print('psci_idle')
elif '--list-boots' in cmd:
    ids = ([a,b,c] if mode == 'wedge' else [a,b]) if state.exists() else [a]
    for i, value in enumerate(ids): print(i+1-len(ids), value, 'dates')
    if state.exists() and mode == 'failed_list': sys.exit(255)
elif cmd.startswith('journalctl -b ' + b):
    print(line)
    if mode == 'wedge': print('csd: Detected non-responsive CSD lock (#1)')
    if mode == 'failed_log': sys.exit(255)
elif cmd.startswith('journalctl -b 0'): print(line)
elif 'for node in watchdog' in cmd:
    print('0\\n0\\n1\\n10' if mode == 'disarmed' else '1\\n1\\n1\\n10')
elif cmd.startswith('set -e;'): print(now + '\\n195.0\\n' + now)
elif cmd.startswith('uname'): print('mock-kernel\\n' + line)
elif 'pstore' in cmd: sys.exit(1)
elif '/proc/interrupts' in cmd: print(now + '\\nmock recovery observation\\n' + now)
else: sys.exit('unexpected mock command: ' + cmd)
''')
            mock.chmod(0o755)
            sleeper = path / "sleep"
            sleeper.write_text("#!/bin/sh\nexit 0\n")
            sleeper.chmod(0o755)
            env = dict(os.environ, GTS9_SSH=str(mock), MOCK_ROOT=tmp,
                       GTS9_ALLOW_POWER="1", GTS9_WINDOW="150", GTS9_SSH_RESULTS=str(path / "results"),
                       PATH=tmp + os.pathsep + os.environ["PATH"])
            for mode, expected in (("clean", "clean"), ("wedge", "wedge"),
                                   ("failed_log", "unattributed"), ("failed_list", "unattributed")):
                with self.subTest(mode=mode):
                    (path / "rebooted").unlink(missing_ok=True)
                    env["MOCK_MODE"] = mode
                    existing = set((path / "results").glob("baseline/*/round-1"))
                    rounds = "1" if mode == "clean" else "3"
                    completed = subprocess.run(["bash", str(ROOT / "scripts/wedge-ssh.sh"), "baseline", rounds],
                                               env=env, capture_output=True, text=True, timeout=15)
                    self.assertEqual(completed.returncode, {"clean": 0, "wedge": 10,
                                     "unattributed": 12}[expected], completed.stdout + completed.stderr)
                    created = set((path / "results").glob("baseline/*/round-1")) - existing
                    self.assertEqual(len(created), 1)
                    round_dir = created.pop()
                    self.assertFalse((round_dir.parent / "round-2").exists())
                    result = json.loads((round_dir / "verdict.json").read_text())
                    self.assertEqual(result["verdict"], expected)
                    self.assertEqual(result, evidence.replay(round_dir))
                    self.assertEqual((round_dir / "reboot-request.txt.status").read_text().strip(), "255")
            self.assertEqual(len(list((path / "results").glob("baseline/*/round-1"))), 4)
            (path / "rebooted").unlink(missing_ok=True)
            (path / "commands").write_text("")
            env["MOCK_MODE"] = "disarmed"
            rejected = subprocess.run(["bash", str(ROOT / "scripts/wedge-ssh.sh"), "baseline", "1"],
                                      env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("runtime watchdog/recovery gate failed", rejected.stderr)
            self.assertNotIn("systemctl reboot", (path / "commands").read_text())


if __name__ == "__main__":
    unittest.main()
