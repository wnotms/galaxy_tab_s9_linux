#!/usr/bin/env python3
"""Reuse the previous same-profile builder, with a distinct formal output."""
from pathlib import Path
p = Path(__file__).resolve().parent.parent / 'x710-pack-current/build.py'
code = p.read_text().replace("out/kernel-x710-pack-current", "out/kernel-x710-cancel-drain")
exec(compile(code, str(p), 'exec'))
