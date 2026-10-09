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
