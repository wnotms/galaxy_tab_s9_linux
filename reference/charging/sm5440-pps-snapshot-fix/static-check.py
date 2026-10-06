#!/usr/bin/env python3
"""Changed object W=1/sparse; restore the exact standard built object afterward."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
original = ROOT / 'reference/charging/sm5440-fedora-port/static-check.py'
exec(compile(original.read_text(), str(original), 'exec'), globals())
