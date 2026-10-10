# Offline reproduction

Use the private qualified archive at `out/ssc-assets/sensor-assets.tar.gz` and
its unchanged `out/ssc-assets/STAGED.json`. `AUDIT.json` pins both identities,
all inspected sources, LLVM version and bounded disassembly commands. No device
is required. Never substitute a different firmware archive to reproduce this
analysis. Firmware and generated ELF bytes stay outside Git.

The exact segment18 wrapper was constructed as follows, from the repository
root. The section is synthetic; no function names or symbols are reconstructed.

```python
import hashlib, json, struct, tarfile
from pathlib import Path

record = json.loads(Path("reference/desktop-bringup/ssc-smp2p-initialization/AUDIT.json").read_text())
manifest_file = Path("out/ssc-assets/STAGED.json")
assert hashlib.sha256(manifest_file.read_bytes()).hexdigest() == record["sources_sha256"][str(manifest_file)]
manifest = json.loads(manifest_file.read_text())
archive = Path("out/ssc-assets/sensor-assets.tar.gz")
assert hashlib.sha256(archive.read_bytes()).hexdigest() == record["firmware_archive_sha256"]
with tarfile.open(archive) as source:
    def read(name):
        key = "usr/lib/firmware/qcom/sm8550/" + name
        data = source.extractfile(key).read()
        assert hashlib.sha256(data).hexdigest() == manifest["files"][key]["sha256"]
        return data
    mdt, raw = read("adsp.mdt"), read("adsp.b18")
    phoff = struct.unpack_from("<I", mdt, 28)[0]
    phsize = struct.unpack_from("<H", mdt, 42)[0]
    va = struct.unpack_from("<I", mdt, phoff + 18 * phsize + 8)[0]
    flags = struct.unpack_from("<I", mdt, 36)[0]
names = b"\0.text\0.shstrtab\0"
stroff = 52 + len(raw)
shoff = (stroff + len(names) + 3) & ~3
header = struct.pack("<16sHHIIIIIHHHHHH", b"\x7fELF\x01\x01\x01" + bytes(9),
                     2, 164, 1, va, 0, shoff, flags, 52, 0, 0, 40, 3, 2)
section = lambda *fields: struct.pack("<10I", *fields)
wrapped = (header + raw + names + bytes(shoff - stroff - len(names)) + bytes(40)
           + section(1, 1, 6, va, 52, len(raw), 0, 0, 4, 0)
           + section(7, 3, 0, 0, stroff, len(names), 0, 0, 1, 0))
assert hashlib.sha256(wrapped).hexdigest() == record["derived_elf_sha256"]
target = Path("out/ssc-smp2p-audit/segment-18.elf")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(wrapped)
```

Run the three exact `commands` from `AUDIT.json` and compare their stdout bytes
to the corresponding `cm-create`, `cm-qmi`, `remote-state` disassembly files.
Use the same wrapper path because objdump prints its input filename. Remove
the generated wrapper after comparison; it is an analysis intermediate, not
a deployable firmware or candidate image.

Initial exploration used a default wrapper flag0x60. Before qualification it
was replaced with the original MDT flag0x73; all three selected disassembly
outputs were byte-identical. Only the final original-flag wrapper hash is the
qualified input. No inference relies on decoding data/string regions as code.
