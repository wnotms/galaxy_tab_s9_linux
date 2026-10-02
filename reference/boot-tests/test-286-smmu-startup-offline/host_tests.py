#!/usr/bin/env python3
"""Real archived journals plus hostile variations; no device operations."""
import copy
import json
from pathlib import Path
import unittest

import gate

A = Path(__file__).resolve().parent
SOURCE = A.parent / 'test-284-passive-fresh-trace'


class Classification(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((SOURCE / 'registration.json').read_text())
        self.load('final-acceptance')
        self.known = {r['MESSAGE'] for r in map(json.loads, (A.parent /
            'test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt')
            .read_text().splitlines()) if int(r.get('PRIORITY', 7)) <= 3}

    def load(self, scope):
        self.current = gate.baseline.sections((SOURCE / scope / 'current-state.txt').read_text())
        self.boot = gate.evidence.canonical_boot_id(self.current['boot'])
        self.rows = list(map(json.loads, (SOURCE / scope / 'kernel-json.txt').read_text().splitlines()))
        self.notes = self.plan['baseline_notes_sha256' if scope == 'final-acceptance' else
                               'candidate_notes_sha256']

    def event(self, substring):
        return next(row for row in self.rows if substring in row['MESSAGE'])

    def scan(self, full=True):
        return gate.journal('\n'.join(map(json.dumps, self.rows)), self.boot, self.known,
            float(self.current['uptime'].split()[0]), self.current, self.plan, self.notes, full)

    def test_real284_restored263_context103_retained_without_rewriting_stop(self):
        out = self.scan()
        self.assertEqual(len(out['smmu_triplets']), 10)
        self.assertEqual({t['s1cbndx'] for t in out['smmu_triplets']}, {103})
        self.assertEqual(len(out['unresolved_startup_smmu']), 20)
        self.assertFalse(out['charging_authorized'] or out['stability_clean_claim'])
        self.assertTrue(out['current_health_verified'])
        old = json.loads((SOURCE / 'final-acceptance/summary.json').read_text())
        self.assertIn('JOURNAL_SUSPECT_RETAINED', old['verdict'])
        with self.assertRaisesRegex(ValueError, 'new/unclassified'):
            gate.frozen.journal('\n'.join(map(json.dumps, self.rows)), self.boot, self.known,
                float(self.current['uptime'].split()[0]), self.current, self.plan, self.notes)

    def test_real284_candidate_context99_keeps_old_profile_admission(self):
        self.load('candidate-admission')
        out = self.scan()
        self.assertEqual({t['s1cbndx'] for t in out['smmu_triplets']}, {99})
        self.assertEqual(len(out['smmu_triplets']), 10)

    def replace_tag(self, tag):
        for row in self.rows:
            row['MESSAGE'] = row['MESSAGE'].replace('0x670021', f'0x{tag:02x}0021')
            row['MESSAGE'] = row['MESSAGE'].replace('00670021', f'00{tag:02x}0021')
            row['MESSAGE'] = row['MESSAGE'].replace('S1CBNDX=103', f'S1CBNDX={tag}')

    def test_existing98_and102_tags_match_complete_triplets(self):
        original = copy.deepcopy(self.rows)
        for tag in (98, 102):
            with self.subTest(tag=tag):
                self.rows = copy.deepcopy(original); self.replace_tag(tag)
                self.assertEqual(self.scan()['smmu_triplets'][0]['s1cbndx'], tag)

    def test_unknown_tags_rejected(self):
        original = copy.deepcopy(self.rows)
        for tag in (0, 9, 70, 100, 101, 104, 255):
            with self.subTest(tag=tag):
                self.rows = copy.deepcopy(original); self.replace_tag(tag)
                with self.assertRaises(ValueError): self.scan()

    def test_mixed_observed_tags_rejected(self):
        self.event('Unhandled context')['MESSAGE'] = self.event('Unhandled context')['MESSAGE'].replace('670021', '660021')
        row = self.event('FSYNR0 ='); row['MESSAGE'] = row['MESSAGE'].replace('670021', '660021').replace('103', '102')
        with self.assertRaisesRegex(ValueError, 'mixed tags'): self.scan()

    def test_context_fields_and_flags_rejected(self):
        original = self.event('Unhandled context')['MESSAGE']
        for old, new in [('fsr=0x402', 'fsr=0x403'), ('cbfrsynra=0x1c00', 'cbfrsynra=0x1c01'),
                         ('cb=9', 'cb=10'), ('670021', '670031'), ('670021', '1670021'),
                         ('15000000.iommu', 'other.iommu')]:
            with self.subTest(field=old):
                self.event('Unhandled context')['MESSAGE'] = original.replace(old, new)
                with self.assertRaises(ValueError): self.scan()

    def test_splash_bounds(self):
        original = self.event('Unhandled context')['MESSAGE']
        for value in ('0xb7ffffff', '0xbab00000', '0xffffffff'):
            with self.subTest(iova=value):
                self.event('Unhandled context')['MESSAGE'] = original.replace('0xb8001500', value)
                with self.assertRaises(ValueError): self.scan()

    def test_syndrome_mismatch_and_fsr_rejected(self):
        original = copy.deepcopy(self.rows)
        for phrase, old, new in [('FSYNR0 =', '670021', '660021'),
                                 ('FSYNR0 =', '103', '102'), ('FSYNR0 =', 'PNU', 'WNR'),
                                 ('FSR    =', 'SID=0x1c00', 'SID=0x1c01'),
                                 ('FSR    =', '00000402', '00000403')]:
            with self.subTest(field=old):
                self.rows = copy.deepcopy(original)
                row = self.event(phrase); row['MESSAGE'] = row['MESSAGE'].replace(old, new)
                with self.assertRaises(ValueError): self.scan()

    def test_each_missing_component_rejected_even_fsr_not_a_suspect(self):
        original = copy.deepcopy(self.rows)
        for phrase in ('Unhandled context', 'FSR    =', 'FSYNR0 ='):
            with self.subTest(component=phrase):
                self.rows = copy.deepcopy(original); self.rows.remove(self.event(phrase))
                with self.assertRaises(ValueError): self.scan()

    def test_reordered_components(self):
        a, b = self.event('Unhandled context'), self.event('FSR    =')
        a['MESSAGE'], b['MESSAGE'] = b['MESSAGE'], a['MESSAGE']
        with self.assertRaises(ValueError): self.scan()

    def test_eleventh_complete_triplet_rejected(self):
        self.rows.extend(copy.deepcopy([self.event(s) for s in ('Unhandled context', 'FSR    =', 'FSYNR0 =')]))
        with self.assertRaises(ValueError): self.scan()

    def test_late_negative_missing_or_nonmonotonic_source_times(self):
        original = copy.deepcopy(self.rows)
        for value in ('200001', '-1', 'bad', '0'):
            with self.subTest(time=value):
                self.rows = copy.deepcopy(original)
                self.event('FSYNR0 =')['_SOURCE_BOOTTIME_TIMESTAMP'] = value
                with self.assertRaises(ValueError): self.scan()
        self.rows = copy.deepcopy(original)
        del self.event('FSYNR0 =')['_SOURCE_BOOTTIME_TIMESTAMP']
        with self.assertRaises(ValueError): self.scan()

    def test_triplet_completion_over1ms_rejected(self):
        self.event('FSYNR0 =')['_SOURCE_BOOTTIME_TIMESTAMP'] = '140045'
        with self.assertRaises(ValueError): self.scan()

    def test_priority_change_even_fsr_known_rejected(self):
        original = copy.deepcopy(self.rows)
        for phrase in ('Unhandled context', 'FSR    =', 'FSYNR0 ='):
            with self.subTest(phrase=phrase):
                self.rows = copy.deepcopy(original); self.event(phrase)['PRIORITY'] = '4'
                with self.assertRaises(ValueError): self.scan()

    def test_incremental_cannot_exempt_startup(self):
        with self.assertRaises(ValueError): self.scan(full=False)

    def test_current_health_identity_transport_still_required(self):
        original = copy.deepcopy(self.current)
        for key, value in [('boot', '0'*32), ('identity', 'bad'), ('cmdline', 'changed'),
                           ('dcc', 'present'), ('failed', 'new.service'), ('roles', '[sink]\n[host]'),
                           ('services', 'inactive'), ('network', '')]:
            with self.subTest(section=key):
                self.current = copy.deepcopy(original); self.current[key] = value
                with self.assertRaises((ValueError, KeyError)): self.scan()
        self.current = copy.deepcopy(original)
        self.current['snapshot'] = self.current['snapshot'].replace('fault=0\n', 'fault=128\n')
        with self.assertRaises(ValueError): self.scan()

    def test_cpu_kernel_unknown_faults_never_exempted(self):
        original = copy.deepcopy(self.rows)
        for message in ('watchdog: BUG: soft lockup - CPU#5 stuck', 'rcu: INFO: rcu_preempt detected stalls',
                        'CSD lock timeout on CPU 4', 'Kernel panic - not syncing: test',
                        'Internal error: Oops: test', 'unclassified severe kernel message'):
            with self.subTest(message=message):
                self.rows = copy.deepcopy(original)
                self.rows.append(dict(self.rows[-1], MESSAGE=message, PRIORITY='3'))
                with self.assertRaises(ValueError): self.scan()

    def test_missing_empty_bad_wrong_boot_journal(self):
        for raw in ('', 'bad', json.dumps(dict(self.rows[0], _BOOT_ID='0'*32))):
            with self.subTest(raw=raw[:20]):
                with self.assertRaises(ValueError):
                    gate.journal(raw, self.boot, self.known, 100, self.current, self.plan, self.notes)

    def test_no_smmu_needs_no_exemption(self):
        self.rows = [r for r in self.rows if not ('arm-smmu' in r['MESSAGE'] and
                     any(s in r['MESSAGE'] for s in ('Unhandled context', 'FSR    =', 'FSYNR0 =')))]
        self.assertEqual(self.scan()['smmu_triplets'], [])


if __name__ == '__main__': unittest.main(verbosity=2)
