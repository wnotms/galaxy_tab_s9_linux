#!/usr/bin/env python3
"""Reuse existing passive cache; save an ordinary-config candidate, never deploy."""
from pathlib import Path
p=Path(__file__).resolve().parent.parent/'x710-pack-current/build.py'
code=p.read_text().replace("'sm5440-native-control'", "'sm5440-passive'").replace('linux-out-x710-303-policy','linux-out-x710-308-passive').replace('out/kernel-x710-pack-current','out/kernel-x710-pc-ordinary')
exec(compile(code,str(p),'exec'))
