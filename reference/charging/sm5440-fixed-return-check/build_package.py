#!/usr/bin/env python3
"""Reuse frozen boot packaging offline in a new formal namespace, default OFF."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
original = ROOT / 'reference/charging/sm5440-fedora-port/build_package.py'
source = original.read_text().replace('OFFLINE_FEDORA_PORT_PASS', 'OFFLINE_FIXED_RETURN_CHECK_PASS')
source = source.replace('out/boot-bundle-x710-fedora', 'out/boot-bundle-x710-fedora-fixed-check')
source = source.replace('UNREGISTERED_FEDORA_SOURCE_CANDIDATE', 'UNREGISTERED_FIXED_RETURN_CHECK_CANDIDATE')
exec(compile(source, str(original), 'exec'), globals())
