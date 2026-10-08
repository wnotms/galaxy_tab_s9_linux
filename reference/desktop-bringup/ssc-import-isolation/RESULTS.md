# SSC source-helper import isolation

Combined discovery loaded GNOME `prepare.py` into Python's generic `prepare`
module cache. SSC build-source validation subsequently imported that unrelated
module and could not find its path validator. Six source-verification tests
failed in the exhaustive run; this was a real host-helper import defect.

Load the sibling SSC preparation module by its exact filesystem location under
a unique name. No sys.path/cache mutation, permissive path fallback or validation
removal. A regression caches an unrelated module with no relative() helper and
still requires SSC source validation to work.

125 affected GNOME/SSC preparation, cross-build, Debian packaging, overrides,
asset, stock, layout and SoCinfo tests PASS, 0 skip. All four/205 prepared source
files and 68 staged files/8 ARM64 ELF objects revalidated; runtime binaries and
packages unchanged, so no runtime/kernel recompile. The first targeted command
misspelled a test module; its import error is retained separately, then corrected.

The previous full3032 result remains NOTPASS; this scoped125 pass fixes the six
SSC import errors and does not imply the remaining historical prerequisites or
fixture failures are fixed. No device operations, installation, firmware/PPS/
ADSP start. The native-SoCinfo build remains offline; sensor hardware acceptance
and controlled early boot are still pending.
