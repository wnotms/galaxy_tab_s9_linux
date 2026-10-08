# Test351 result

Verified-prefix resume completed in56.15s; full166492160-byte archive matches
SHA83d7db40c190d68522cfce4d9d552149f6759a4a7d7d6f265feba4eee0d46458,
381members extracted. Sole installer stopped at APT simulation exit100 before
mask/firmware/package/GDM mutation. Raw transaction archive/hash retained.

`--no-download` prevented acquisition of command-line local archives outside
APT's own cache. A subsequent read-only simulation with invocation-local
repository sources disabled and that flag removed returned0, exact368new
packages/no upgrade/removal. Two warnings from nonexistent placeholder source
paths are retained; corrected implementation uses actual empty paths in owned
evidence. No package install, firmware, GUI, GPU load, reboot or charging attempt.
Fresh normal sameboot at90%/32.0C/Good. Next is a corrected installer using the
already complete cache; preserve this original STOP and job identity.

[Debian APT manual](https://manpages.debian.org/trixie/apt/apt-get.8.en.html)
defines --no-download in terms of already acquired archives; actual device
simulation/raw evidence establishes this specific failure. Tests/build for this
results-only record executed:false; corrected installer tests recorded separately.
