#!/usr/bin/env python3
"""Reuse qualified native-profile builder; save distinct formal PC-budget candidate."""
from pathlib import Path
p=Path(__file__).resolve().parent.parent/'x710-pack-current/build.py'
code=p.read_text().replace('out/kernel-x710-pack-current','out/kernel-x710-pc-current')
exec(compile(code,str(p),'exec'))
