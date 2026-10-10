# Separate RPC stat diagnostic

This profile is deliberately outside the frozen Fedora source manifest. It
applies after all three accepted hexagonrpc patches, to a separately verified
copy; no preparation/build command connects to a device or authorizes deployment.
The exact patch/base/result hashes are in rpc-stat.json.

```sh
python3 userspace/sensors/rpc_stat_profile.py \
  --sources out/ssc-sources/prepared-clean --output out/ssc-rpc-stat/sources
```

The output must be absent. The prepared tree's SOURCE.json records all component
files before and after the one permitted change. For ARM64 compilation, run
compile-rpc-stat.sh in the existing Debian builder with `/inputs` mounted
read-only to that tree, `/recipe` read-only to userspace/sensors, and a separate
empty `/output`; set HOST_UID/HOST_GID to the invoking user's IDs. Use
`--network=none` and `--security-opt=no-new-privileges`. The qualified invocation,
builder ID, package versions, compiler, complete log, source and ELF identity are
recorded under reference/desktop-bringup/ssc-rpc-stat/.

The profile retains successful RPC wire values, including Qualcomm's ctime
encoding. Extra size/mtime output appears only in the verbose diagnostic. It
does not change registry content/timestamps or implement a firmware substitute.
Its error-path repair is host-proven, but not proved to explain Test378's missing
SSC service. A future physical test needs its own registration before any
runtime replacement or reboot.

## Independent RPC wire correction (2026-10-10)

`rpc-wire.json`/`rpc-wire.patch` define a separate candidate based on the frozen
Fedora0.4 sources, not the historical stat diagnostic. The only changed file
is `hexagonrpcd/iobuffer.c`: consume empty buffers, count their four-byte headers
without payload alignment, and copy possibly unaligned size headers safely.
The frozen `sources.json`, stat profile and previous physical results stay intact.

```sh
python3 userspace/sensors/rpc_wire_profile.py \
  --sources out/ssc-sources/prepared-clean --output out/ssc-rpc-wire/sources
```

Compile with the same networkless `compile-rpc-stat.sh` recipe; that script
consumes the verified `SOURCE.json` and does not apply the stat patch itself.
The profile alone never deploys anything. Proven original-code failures,
independent Qualcomm protocol vectors, native UBSan, ARM64/QEMU, all55 source
hashes and artifact hashes are recorded in
`reference/desktop-bringup/ssc-rpc-wire/`. No real DSP zero-length invocation has
yet been identified; this fixes demonstrated codec defects, not a proven SSC
initialization rootcause. A new physical registration is required before use.

For a comparison against the accepted stat-observer runtime, add `--with-stat`.
Both profiles admit the same frozen Fedora source tree independently. The
composed output preserves the stat observer byte-for-byte and changes only
iobuffer.c relative to it; SOURCE.json records both patch identities and the
complete55-file result. This does not rewrite either old build or its manifest.
