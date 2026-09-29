# Portable evidence seal supplement

The original SHA256.json is byte-for-byte preserved. Its local-filesystem snapshot
accidentally included tools/__pycache__/control.cpython-314.pyc, a generated ignored
host cache (not device evidence), unavailable in a fresh Git clone. Do not interpret
that cache locator as missing hardware evidence. GIT_EVIDENCE_SHA256.json seals
all archived payloads, including the original seal and this scope note, excluding
Python caches; all raw device/command/results files are included unchanged.
The Test254 physical seal likewise covers Git evidence only. No old result or
raw capture was rewritten, and no bytecode is made an executable repo artifact.
