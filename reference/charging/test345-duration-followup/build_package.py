#!/usr/bin/env python3
"""Prepare a default-OFF boot only; no device command or armed opt-in."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
original = ROOT / 'reference/charging/sm5440-fedora-port/build_package.py'
source = original.read_text().replace('OFFLINE_FEDORA_PORT_PASS', 'OFFLINE_BOUNDED_DURATION_PASS')
source = source.replace('out/boot-bundle-x710-fedora', 'out/boot-bundle-x710-bounded-duration-off')
source = source.replace('UNREGISTERED_FEDORA_SOURCE_CANDIDATE', 'UNREGISTERED_BOUNDED_DURATION_OFF_CANDIDATE')
source = source.replace('reference/boot-tests/test-323-pc-source-budget', 'reference/boot-tests/test-331-pps-fix-default-off')
source = source.replace('accepted Test323 source-authorized ordinary PC charging', 'accepted Test331 default-OFF paired ordinary charging')
source = source.replace('same-model Fedora SM5440/PPS source port; default direct charging off', 'explicit bounded30s/300s duration with unchanged hardware1.7A/PPS+raw1.8A; direct charging default OFF')
exec(compile(source, str(original), 'exec'), globals())
