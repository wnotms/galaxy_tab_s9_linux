# Userspace-only build and local validation

Debian android-platform-tools34.0.5-12 source archives are SHA256-pinned in
`scripts/build-adbd-reconnect.sh`; the base trixie-slim image is digest-pinned
in `userspace/adbd/Dockerfile`. No GPG signature verification is claimed.
Exact source fixtures retain Apache2 attribution and baseline checksums.
Patch SHA256: `4b1ed2bcd3f44e5d268a9d9670551225a94543345230c9571e9d79daefaffd50`.

Successful ARM64 Clang cross-build produced an optional separate daemon,
SHA256 `053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5`.
See build/manifest.json, cross-build.log, elf-dynamic.txt, elf-versions.txt
and build-packages.txt. Compiler/tools/libs are recorded; repository code
never overwrites the packaged daemon or contacts hardware from the build.
Earlier GCC/tool bootstrap attempts failed locally and were not deployed.
Kernel/config/DTS/modules were neither modified nor rebuilt.

Thirteen focused host checks execute actual patched methods with real
threads and owned file descriptors, including glibc's original cleanup hang,
early worker exit, retained control endpoint, duplicate failure and event
ordering. Original full-source fixture hashes are checked before extraction.
Changed selection command `bash scripts/check-stall-offline.sh --changed
--base HEAD~1` passed1080 tests, zero failures/errors/skips (81.301s).
Final `python3 scripts/run-host-tests.py all --fail-on-skip --report
out/host-tests/adbd-reconnect-all.json` passed1080 tests, zero failures/errors/
skips (76.056s); saved report is build/host-tests-all.json. Shell syntax checks
for scripts/*.sh, scripts/lib/*.sh and boot/*.sh passed. No old test was deleted.
Host success does not establish hardware reconnect or device runtime ABI.
