#!/usr/bin/env python3
"""Reuse frozen boot packaging offline in a new formal namespace, default OFF."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
original = ROOT / 'reference/charging/sm5440-fedora-port/build_package.py'
source = original.read_text().replace('OFFLINE_FEDORA_PORT_PASS', 'OFFLINE_BOUNDED_DIRECT_PASS')
source = source.replace('out/boot-bundle-x710-fedora', 'out/boot-bundle-x710-fedora-pps-off-return')
source = source.replace('UNREGISTERED_FEDORA_SOURCE_CANDIDATE', 'UNREGISTERED_BOUNDED_DIRECT_CANDIDATE')
source = source.replace('reference/boot-tests/test-323-pc-source-budget', 'reference/boot-tests/test-331-pps-fix-default-off')
source = source.replace('accepted Test323 source-authorized ordinary PC charging', 'accepted Test331 default-OFF paired ordinary charging')
source = source.replace('out/boot-bundle-x710-fedora-pps-off-return', 'out/boot-bundle-x710-bounded-direct-on')
source = source.replace("'--cmdline', ''", "'--cmdline', 'sm5440_fedora.direct_charge_once=1'")
source = source.replace('same-model Fedora SM5440/PPS source port; default direct charging off', 'single <=30s 1.8A pump bring-up; one explicit direct_charge_once opt-in, no automatic retry')
exec(compile(source, str(original), 'exec'), globals())
