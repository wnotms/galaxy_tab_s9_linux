#!/usr/bin/env python3
"""Offline full-journal replays and adversarial fixtures, no hardware access."""
import ast
import copy
import json
from pathlib import Path
import unittest

import gate
import host_flow

A = Path(__file__).resolve().parent
SOURCE = A.parent / 'test-282-passive-fresh-trace'


class Classification(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((SOURCE / 'registration.json').read_text())
        self.current = gate.baseline.sections((SOURCE / 'candidate-admission/current-state.txt').read_text())
        self.boot = gate.evidence.canonical_boot_id(self.current['boot'])
        self.rows = list(map(json.loads, (SOURCE / 'candidate-admission/kernel-json.txt').read_text().splitlines()))
        self.known = {r['MESSAGE'] for r in map(json.loads, (A.parent /
            'test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt').read_text().splitlines())
            if int(r.get('PRIORITY', 7)) <= 3}

    def fault(self):
        return next(r for r in self.rows if 'passive fault bitmap=' in r['MESSAGE'])

    def event(self, substring):
        return next(r for r in self.rows if substring in r['MESSAGE'])

    def scan(self, full=True):
        raw = '\n'.join(json.dumps(r) for r in self.rows)
        return gate.journal(raw, self.boot, self.known, float(self.current['uptime'].split()[0]),
                            self.current, self.plan, self.plan['candidate_notes_sha256'], full)

    def reject_message(self, old, new):
        self.fault()['MESSAGE'] = self.fault()['MESSAGE'].replace(old, new)
        with self.assertRaises(ValueError):
            self.scan()

    def test_real282_classified_without_rewriting_original_stop(self):
        out = self.scan()
        event = out['retained_startup_confirmation']
        self.assertTrue(event['int4_adc_updated'] and event['event_retained'])
        self.assertEqual(event['confirmation_seconds'], 2.300114)
        self.assertFalse(event['charging_authorized'] or out['stability_clean_claim'])
        self.assertEqual(out['unresolved_counts'], {'context': 0, 'syndrome': 0})
        self.assertTrue(out['current_health_verified'])
        summary = json.loads((SOURCE / 'summary.json').read_text())
        self.assertIn('STOP_UNCLASSIFIED', summary['final_verdict'])
        with self.assertRaisesRegex(ValueError, 'unclassified passive fault'):
            gate.frozen.journal('\n'.join(json.dumps(r) for r in self.rows), self.boot,
                                self.known, float(self.current['uptime'].split()[0]))

    def test_all256_int4_values_only_completion_bit_allowed(self):
        original = self.fault()['MESSAGE']
        for byte in range(256):
            with self.subTest(int4=byte):
                self.fault()['MESSAGE'] = original.replace('INT=00 00 62 01', f'INT=00 00 62 {byte:02x}')
                if byte in (0, 1):
                    self.assertEqual(gate._retained_startup(self.rows, True)['int4_adc_updated'], bool(byte))
                else:
                    with self.assertRaisesRegex(ValueError, 'INT4 watchdog/timer/unknown'):
                        gate._retained_startup(self.rows, True)

    def test_all_other_literal_safety_fields_remain_exact(self):
        original = self.fault()['MESSAGE']
        changes = [('bitmap=0x80', 'bitmap=0x88'), ('INT=00 00 62', 'INT=08 00 62'),
                   ('INT=00 00 62', 'INT=00 01 62'), ('INT=00 00 62', 'INT=00 00 e2'),
                   ('STATUS=00 00 20 00', 'STATUS=00 00 22 00'), ('INT4-disable=00', 'INT4-disable=01'),
                   ('INT4-wait=01', 'INT4-wait=03'), ('mode=01/01', 'mode=05/05'),
                   ('CNTL2=f2', 'CNTL2=f3'), ('VBUSCNTL=e7', 'VBUSCNTL=e6'),
                   ('VBATCNTL=37', 'VBATCNTL=38'), ('PRTNCNTL=fe', 'PRTNCNTL=ff'), ('IBUS=0uA', 'IBUS=625uA')]
        for old, new in changes:
            with self.subTest(field=old):
                self.fault()['MESSAGE'] = original
                self.reject_message(old, new)

    def test_raw_adc_decoding_disagreement_rejected(self):
        self.reject_message('VBUS=4789000', 'VBUS=4790000')

    def test_unsafe_raw_vbus_rejected_even_when_decoding_matches(self):
        self.reject_message('ADC=15 a8', 'ADC=37 28')  # raw13=1765 ->5.861V
        # Above mismatch itself fails; now require a self-consistent unsafe pair.
        self.fault()['MESSAGE'] = self.fault()['MESSAGE'].replace('VBUS=4789000', 'VBUS=5861000')
        with self.assertRaisesRegex(ValueError, 'unsafe ADC'): self.scan()

    def test_late_or_bad_startup_chronology(self):
        fault = self.fault()
        for stamp in ['0', '269729', '1000001', '-1']:
            with self.subTest(timestamp=stamp):
                fault['_SOURCE_BOOTTIME_TIMESTAMP'] = stamp
                with self.assertRaises(ValueError): self.scan()

    def test_confirmation_deadlines(self):
        done = self.event('confirmed inactive')
        for stamp in ['269739', '5269740', '269738']:
            with self.subTest(timestamp=stamp):
                done['_SOURCE_BOOTTIME_TIMESTAMP'] = stamp
                with self.assertRaises(ValueError): self.scan()

    def test_waiting_to_fault_over100ms_rejected(self):
        self.event('awaiting two')['_SOURCE_BOOTTIME_TIMESTAMP'] = '100000'
        with self.assertRaises(ValueError): self.scan()

    def test_missing_and_duplicate_confirmations(self):
        original = copy.deepcopy(self.rows)
        for phrase in ['awaiting two', 'confirmed inactive']:
            for duplicate in [False, True]:
                with self.subTest(phrase=phrase, duplicate=duplicate):
                    self.rows = copy.deepcopy(original)
                    event = self.event(phrase)
                    if duplicate: self.rows.append(copy.deepcopy(event))
                    else: self.rows.remove(event)
                    with self.assertRaises(ValueError): self.scan()

    def test_priorities_remain_exact(self):
        original = copy.deepcopy(self.rows)
        for phrase in ['fault bitmap=', 'awaiting two', 'confirmed inactive']:
            with self.subTest(phrase=phrase):
                self.rows = copy.deepcopy(original)
                self.event(phrase)['PRIORITY'] = '5'
                with self.assertRaises(ValueError): self.scan()

    def test_repeated_or_later_fault_rejected(self):
        self.rows.append(copy.deepcopy(self.fault()))
        with self.assertRaises(ValueError): self.scan()

    def test_adc_and_confirmation_failure_not_exempted(self):
        fault = self.fault()
        for phrase in ['ADC fault', 'confirmation failed']:
            with self.subTest(phrase=phrase):
                fault['MESSAGE'] = gate.PASSIVE_PREFIX + phrase
                with self.assertRaises(ValueError): self.scan()

    def test_incremental_fault_never_gets_startup_exemption(self):
        with self.assertRaisesRegex(ValueError, 'new/repeated'): self.scan(full=False)

    def test_cpu_and_severe_kernel_faults_still_stop(self):
        original = copy.deepcopy(self.rows)
        for message in ['watchdog: BUG: soft lockup - CPU#5 stuck', 'rcu: INFO: rcu_preempt detected stalls',
                        'CSD lock timeout on CPU 4', 'Kernel panic - not syncing: test',
                        'Internal error: Oops: 00000000', 'unclassified serious kernel message']:
            with self.subTest(message=message):
                self.rows = copy.deepcopy(original)
                row = copy.deepcopy(self.rows[-1]); row['MESSAGE'] = message; row['PRIORITY'] = '3'
                self.rows.append(row)
                with self.assertRaises(ValueError): self.scan()

    def test_healthy_current_snapshot_is_mandatory(self):
        original = copy.deepcopy(self.current)
        for old, new in [('fault=0\n', 'fault=128\n'), ('sample_fresh=1', 'sample_fresh=0'),
                         ('sample_mode_after=0x01', 'sample_mode_after=0x05'),
                         ('sample_prtncntl=0xfe', 'sample_prtncntl=0xff')]:
            with self.subTest(field=old):
                self.current = copy.deepcopy(original)
                self.current['snapshot'] = self.current['snapshot'].replace(old, new)
                with self.assertRaises(ValueError): self.scan()

    def test_identity_services_dcc_and_battery_still_stop(self):
        original = copy.deepcopy(self.current)
        mutations = [('boot', '0'*32), ('cmdline', 'changed'), ('identity', 'changed'),
                     ('services', 'active\nfailed\nactive'), ('dcc', 'present'),
                     ('network', ''), ('roles', '[sink]\n[host]'), ('failed', 'test.service failed')]
        for section, value in mutations:
            with self.subTest(section=section):
                self.current = copy.deepcopy(original); self.current[section] = value
                with self.assertRaises((ValueError, KeyError, IndexError)): self.scan()
        self.current = copy.deepcopy(original)
        # Use the fixture's actual value, not a guessed temperature.
        self.current['battery'] = '\n'.join('POWER_SUPPLY_TEMP=450' if x.startswith('POWER_SUPPLY_TEMP=') else x
                                           for x in original['battery'].splitlines())
        with self.assertRaises(ValueError): self.scan()

    def test_empty_missing_and_wrong_boot_journal(self):
        for raw in ['', 'not JSON', json.dumps(dict(self.rows[0], _BOOT_ID='0'*32))]:
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(ValueError):
                    gate.journal(raw, self.boot, self.known, 100, self.current, self.plan,
                                 self.plan['candidate_notes_sha256'])

    def test_final_baseline_int4_zero_keeps_original_behavior(self):
        current = gate.baseline.sections((SOURCE / 'final-acceptance/current-state.txt').read_text())
        raw = (SOURCE / 'final-acceptance/kernel-json.txt').read_text()
        boot = gate.evidence.canonical_boot_id(current['boot']); uptime = float(current['uptime'].split()[0])
        new = gate.journal(raw, boot, self.known, uptime, current, self.plan, self.plan['baseline_notes_sha256'])
        old = gate.frozen.journal(raw, boot, self.known, uptime)
        self.assertFalse(new['retained_startup_confirmation'].pop('int4_adc_updated'))
        for key in old: self.assertEqual(new[key], old[key])

    def test_no_startup_fault_requires_no_exemption(self):
        self.rows = [r for r in self.rows if not any(s in r['MESSAGE']
                     for s in ['passive fault bitmap=', 'awaiting two', 'confirmed inactive'])]
        self.assertIsNone(self.scan()['retained_startup_confirmation'])

    def test_existing_journal_cpu_smmu_rules_ast_unchanged(self):
        old = next(n for n in ast.parse(gate._path.read_text()).body
                   if isinstance(n, ast.FunctionDef) and n.name == 'journal')
        new = next(n for n in ast.parse((A / 'gate.py').read_text()).body
                   if isinstance(n, ast.FunctionDef) and n.name == 'journal')
        self.assertEqual(ast.unparse(new.body[1]), 'identity(current, plan, notes, boot)')
        new.body = new.body[2:]  # only added docstring/current admission check
        new.args = old.args
        class NormalizeAdditions(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id == '_retained_startup': node.id = 'retained_startup'
                return node
            def visit_Call(self, node):
                self.generic_visit(node)
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'update':
                    node.keywords = [k for k in node.keywords if k.arg not in
                                     ('current_health_verified', 'classification_profile')]
                return node
        new = NormalizeAdditions().visit(new)
        self.assertEqual(ast.dump(old), ast.dump(new))


class RecoveryFlow(unittest.TestCase):
    def test_native_recovery_and_device_states(self):
        for state in ['recovery', 'device']:
            with self.subTest(state=state):
                self.assertTrue(host_flow.recovery_ready('List of devices attached\r\nR52X10045LT\t'+state+'\r\n'))

    def test_debian_and_offline_are_not_recovery(self):
        self.assertFalse(host_flow.recovery_ready('gts9wifi-0001\tdevice'))
        self.assertFalse(host_flow.recovery_ready('R52X10045LT\toffline'))
        self.assertFalse(host_flow.recovery_ready('List of devices attached\n'))

    def test_ambiguous_or_unauthorized_state_stops(self):
        for raw in ['R52X10045LT device\nR52X10045LT recovery', 'R52X10045LT unauthorized',
                    'R52X10045LT', 'R52X10045LT unexpected']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError): host_flow.recovery_ready(raw)

    def exercise(self, replies, timeout=9):
        self.clock = 0
        self.calls = []
        outer = self
        class Recorder:
            def host_adb(self, name, *args, **kwargs):
                outer.calls.append((name, args, kwargs))
                return replies.pop(0) if replies else ('', 0)
        def pause(seconds): outer.clock += seconds
        return host_flow.wait_recovery(Recorder(), timeout, lambda: self.clock, pause)

    def test_returns_immediately_on_first_recovery_no_fixed_wait(self):
        result = self.exercise([('R52X10045LT recovery', 0)])
        self.assertEqual(result['polls'], 1)
        self.assertEqual(result['elapsed_seconds'], 0)
        self.assertIn('IDENTITY_STILL_REQUIRED', result['verdict'])
        self.assertEqual(self.calls[0][1], ('devices',))

    def test_transitional_absence_does_not_trigger_another_reboot(self):
        result = self.exercise([('', 0), ('gts9wifi-0001 device', 0), ('R52X10045LT recovery', 0)])
        self.assertEqual(result['polls'], 3)
        self.assertEqual(result['elapsed_seconds'], 6)
        self.assertTrue(all(call[1] == ('devices',) for call in self.calls))

    def test_transport_error_is_not_ready(self):
        result = self.exercise([('R52X10045LT recovery', 1), ('R52X10045LT recovery', 0)])
        self.assertEqual(result['polls'], 2)

    def test_deadline_no_reboot_flash_or_infinite_retry(self):
        with self.assertRaises(TimeoutError): self.exercise([], timeout=9)
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(all(call[1] == ('devices',) for call in self.calls))

    def test_invalid_deadline(self):
        with self.assertRaises(ValueError): self.exercise([], timeout=0)


if __name__ == '__main__': unittest.main(verbosity=2)
