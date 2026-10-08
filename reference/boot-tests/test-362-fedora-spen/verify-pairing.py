"""Read-only replay: exact331 Image exports against the optional Wacom module.

The runtime symbol addresses locate PREL32 exports in the hash-bound ARM64
Image. Linux 7.2 export-internal.h defines 12-byte entries and u32 CRCs in the
same sorted order. No force-load/version bypass is permitted. This establishes
export-ABI compatibility, not physical acceptance or identical build provenance.
"""
from pathlib import Path
import gzip, hashlib, json, re, struct, subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
image = ROOT / 'out/kernel-x710-fedora-snapshot-fix/Image.gz'
module = ROOT / 'out/gnome-trixie-arm64/pen-module/wacom-wez01.ko'
assert hashlib.sha256(image.read_bytes()).hexdigest() == 'efb2a1aaf68962270816d99ed54ebc94013f08ea82a95bf9b8c465618595d6cb'
assert hashlib.sha256(module.read_bytes()).hexdigest() == 'bc3816a8f37c0f45bdaca3ac9548793df1784541364da9017d08d5c4841e1412'
evidence = HERE / 'preflight.stdout'
text = evidence.read_text()
identity = json.loads(text.splitlines()[0])
assert identity['boot_id'] == '25ff0ad0-cf2f-4cc6-971d-2b38365da2db'
assert identity['config'] == '51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a'
assert identity['notes'] == '03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95'
syms = {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [A-Za-z] (\S+)$', text, re.M)}
raw = gzip.decompress(image.read_bytes())
assert raw[56:60] == b'ARM\x64'
base = syms['_text']
lo, hi, clo, chi = [syms[n] - base for n in ('__start___ksymtab', '__stop___ksymtab', '__start___kcrctab', '__stop___kcrctab')]
assert 0 < lo < hi <= clo < chi <= len(raw)
assert (hi-lo) % 12 == (chi-clo) % 4 == 0
count = (hi-lo)//12
assert count == (chi-clo)//4 and count > 0
exports = {}
for i, off in enumerate(range(lo, hi, 12)):
    p = off + 4 + struct.unpack_from('<i', raw, off+4)[0]
    assert 0 <= p < len(raw)
    end = raw.index(b'\x00', p, min(len(raw), p+512))
    name = raw[p:end].decode('ascii')
    assert re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name) and name not in exports
    exports[name] = struct.unpack_from('<I', raw, clo+i*4)[0]
assert list(exports) == sorted(exports)
versions = subprocess.check_output(['modprobe', '--show-modversions', str(module)], text=True)
(HERE/'module-versions.txt').write_text(versions)
rows = []
for line in versions.splitlines():
    crc, name = line.split()
    rows.append(dict(symbol=name, imported_crc=crc, kernel_crc=f'0x{exports[name]:08x}', match=int(crc,16)==exports[name]))
assert len(rows) > 0 and any(x['symbol']=='module_layout' for x in rows)
assert len({x['symbol'] for x in rows}) == len(rows) and all(x['match'] for x in rows)
result = dict(verdict='TEST331_ALL_CONSUMED_EXPORT_CRCS_MATCH', export_count=count,
              imports=rows, image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
              module_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),
              runtime_symbols_evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
              source='Fedora X710 ab123e7d with local timer/devres/probe-error fixes', module_original_build_provider='Test348',
              caveat='Cross-build export ABI checked directly against exact331; kernel loader must still check version/BTF/signature with no force flags',
              BTF_base='Module has distilled .BTF.base; Linux7.2 kernel/bpf/btf.c relocates against current vmlinux BTF',
              device_load_executed=False)
(HERE/'pairing.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['verdict'], count, 'exports,',len(rows),'matching imported CRCs')
