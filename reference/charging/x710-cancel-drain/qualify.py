#!/usr/bin/env python3
"""Reuse previous exact qualification; add immediately preceding config/metadata."""
from pathlib import Path
p = Path(__file__).resolve().parent.parent / 'x710-pack-current/qualify.py'
code = p.read_text().replace("OUT=ROOT/'out/kernel-x710-pack-current'", "OUT=ROOT/'out/kernel-x710-cancel-drain'")
code = code.replace("('active-session','out/kernel-x710-active-session/config')", "('active-session','out/kernel-x710-active-session/config'),('pack-current','out/kernel-x710-pack-current/config')")
code = code.replace(" 'active-session':{},", " 'active-session':{},\n 'pack-current':{},")
code = code.replace("active_modules=archived(ROOT/'out/kernel-x710-active-session/modules-x710.tar.gz')", "active_modules=archived(ROOT/'out/kernel-x710-pack-current/modules-x710.tar.gz')")
code = code.replace("active-session builtin identity changed:", "pack-current builtin identity changed:")
exec(compile(code, str(p), 'exec'))
