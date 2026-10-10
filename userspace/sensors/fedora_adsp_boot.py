#!/usr/bin/env python3
"""Build a host-only matched Fedora ADSP vendor ramdisk from exact Test399.

Kernel, DTB, cmdline, bootconfig, trace enrollment and three PD maps stay exact.
Firmware bytes come from the qualified complete 52-file profile. No deployment.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import shlex
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('fedora_boot_transaction',
                                            Path(__file__).with_name('adsp_firmware_transaction.py'))
TX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TX)
BASE_VENDOR_SHA = 'af6531b5eaaf5a86ae35f9362cebd173086320d94154590f2391703d7cae72aa'
BASE_RAMDISK_SHA = '44cf42afa8a7b0c524ae52c1339d63019bedf49b2e675410864fa464808f7874'
TOOLS = {
    'unpack_bootimg.py': 'a9d260978a63bd06a24b6347e7dee8a28ff96639793caea15dff6aa491316308',
    'mkbootimg.py': '37d84b3d162e0bc62e36c1f4e1c63c85ea0caa9f29be023eb2f8efe006ad948c',
    'avbtool.py': 'e5a664a38db623da00f080219bc0ee60a640a9dc4a872803616fae4938ac749b',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_cpio(raw):
    if len(raw) > 128*1024**2:
        raise ValueError('ramdisk size bound')
    rows, names, offset = [], set(), 0
    while offset+110 <= len(raw):
        header = raw[offset:offset+110]
        if header[:6] != b'070701':
            raise ValueError('not newc')
        fields = [int(header[6+i*8:14+i*8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        if not 1 <= namesize <= 512 or size > 64*1024**2 or fields[12] != 0:
            raise ValueError('cpio bounds/check')
        begin = offset+110
        end = begin+namesize
        namebytes = raw[begin:end]
        if len(namebytes) != namesize or namebytes[-1:] != b'\0':
            raise ValueError('cpio name')
        name = namebytes[:-1].decode('ascii')
        start = (end+3)&~3
        data = raw[start:start+size]
        if len(data) != size:
            raise ValueError('short cpio data')
        offset = (start+size+3)&~3
        if name == 'TRAILER!!!':
            if size or any(raw[offset:]):
                raise ValueError('cpio trailer/trailing bytes')
            return rows
        p = PurePosixPath(name)
        if (name in names or len(names) >= 128 or str(p) != name or p.is_absolute()
                or '..' in p.parts or fields[2:4] != [0, 0]
                or not (stat.S_ISREG(fields[1]) or stat.S_ISDIR(fields[1]))
                or (stat.S_ISDIR(fields[1]) and size)):
            raise ValueError('unsafe cpio entry')
        names.add(name)
        rows.append(dict(name=name, fields=fields, data=data))
    raise ValueError('missing cpio trailer')


def pack_cpio(rows):
    raw = bytearray()
    for row in rows + [dict(name='TRAILER!!!', fields=[0]*13, data=b'')]:
        name = row['name'].encode('ascii')+b'\0'
        fields = list(row['fields'])
        fields[6], fields[11] = len(row['data']), len(name)
        raw += b'070701'+b''.join(f'{n:08x}'.encode() for n in fields)+name
        raw += b'\0'*(-len(raw)%4)
        raw += row['data']
        raw += b'\0'*(-len(raw)%4)
    raw += b'\0'*(-len(raw)%512)
    return bytes(raw)


def replace_pair(rows, base, candidate):
    expected_dirs = {'.', 'lib', 'lib/firmware', 'lib/firmware/qcom', 'lib/firmware/qcom/sm8550'}
    directories = {r['name'] for r in rows if stat.S_ISDIR(r['fields'][1])}
    files = {r['name']: r for r in rows if stat.S_ISREG(r['fields'][1])}
    names = {n.removeprefix('usr/') for n in base}
    # Exact Test399 PD maps; do not import Fedora maps with its firmware pair.
    maps = {'lib/firmware/qcom/sm8550/'+n for n in ('adspr.jsn', 'adspua.jsn', 'adsps.jsn')}
    if directories != expected_dirs or set(files) != names|maps or len(base) != 52 or set(base) != set(candidate):
        raise ValueError('unexpected early firmware/map set')
    output, changes = [], []
    for row in rows:
        item = dict(row, fields=list(row['fields']))
        mapped = 'usr/'+row['name']
        if mapped in base:
            if row['data'] != base[mapped]['data'] or row['fields'][1] != stat.S_IFREG|0o644:
                raise ValueError('early original differs from baseline pair')
            item['data'] = candidate[mapped]['data']
            item['fields'][6] = len(item['data'])
            changes.append(dict(path=row['name'], before=TX.digest(row['data']),
                                after=TX.digest(item['data']), changed=row['data'] != item['data']))
        output.append(item)
    return output, changes


def build(base_vendor, base_assets, candidate_assets, output):
    if base_vendor.is_symlink() or sha(base_vendor) != BASE_VENDOR_SHA:
        raise ValueError('exact Test399 vendor required')
    for name, expected in TOOLS.items():
        if sha(ROOT/'.work/tools'/name) != expected:
            raise ValueError('AOSP tool identity')
    base = TX.archive_files(base_assets, TX.BASE_SHA)
    candidate = TX.archive_files(candidate_assets, TX.CANDIDATE_SHA)
    output.mkdir(mode=0o700, exist_ok=False)
    commands = []
    def run(args, name, data=None):
        commands.append(args)
        result = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=120, check=False)
        if name in ('decompress', 'compress', 'verify-ramdisk'):
            (output/(name+'.json')).write_text(json.dumps(dict(
                bytes=len(result.stdout), sha256=TX.digest(result.stdout)))+'\n')
        else:
            (output/(name+'.stdout')).write_bytes(result.stdout)
        (output/(name+'.stderr')).write_bytes(result.stderr)
        if result.returncode:
            raise ValueError('failed '+name)
        return result.stdout
    source = output/'source'
    args = shlex.split(run(['python3', str(ROOT/'.work/tools/unpack_bootimg.py'),
                           '--boot_img', str(base_vendor), '--out', str(source),
                           '--format', 'mkbootimg'], 'unpack').decode())
    original = source/'vendor_ramdisk00'
    if sha(original) != BASE_RAMDISK_SHA:
        raise ValueError('original early ramdisk identity')
    rows = parse_cpio(run(['lz4', '-dc', str(original)], 'decompress'))
    replaced, changes = replace_pair(rows, base, candidate)
    cpio = pack_cpio(replaced)
    if parse_cpio(cpio) != replaced:
        raise ValueError('reopened generated cpio mismatch')
    ramdisk = output/'fedora-adsp.lz4'
    ramdisk.write_bytes(run(['lz4', '-l', '-12', '-c'], 'compress', cpio))
    if parse_cpio(run(['lz4', '-dc', str(ramdisk)], 'verify-ramdisk')) != replaced:
        raise ValueError('compressed ramdisk mismatch')
    before = list(args)
    index = args.index('--vendor_ramdisk_fragment')+1
    if args[index] != str(original):
        raise ValueError('unexpected ramdisk argument')
    args[index] = str(ramdisk)
    vendor = output/'vendor_boot.img'
    run(['python3', str(ROOT/'.work/tools/mkbootimg.py'), *args,
         '--vendor_boot', str(vendor)], 'pack')
    payload = sha(vendor)
    run(['python3', str(ROOT/'.work/tools/avbtool.py'), 'add_hash_footer', '--image', str(vendor),
         '--partition_name', 'vendor_boot', '--partition_size', '100663296', '--salt', payload], 'footer')
    run(['python3', str(ROOT/'.work/tools/avbtool.py'), 'verify_image', '--image', str(vendor)], 'avb-verify')
    verified = shlex.split(run(['python3', str(ROOT/'.work/tools/unpack_bootimg.py'),
                               '--boot_img', str(vendor), '--out', str(output/'verify'),
                               '--format', 'mkbootimg'], 'unpack-verify').decode())
    def normalized(arguments):
        copy = list(arguments)
        for option in ('--dtb', '--vendor_bootconfig', '--vendor_ramdisk_fragment'):
            copy[copy.index(option)+1] = '<component>'
        return copy
    if normalized(before) != normalized(verified):
        raise ValueError('vendor header/arguments changed')
    for component in ('dtb', 'bootconfig'):
        if sha(source/component) != sha(output/'verify'/component):
            raise ValueError('protected component changed')
    if sha(output/'verify/vendor_ramdisk00') != sha(ramdisk) or vendor.stat().st_size != 100663296:
        raise ValueError('vendor readback/size')
    report = dict(verdict='MATCHED_FEDORA_ADSP_BOOT_OFFLINE_ONLY',
                  base_vendor_sha256=BASE_VENDOR_SHA, candidate_vendor_sha256=sha(vendor),
                  candidate_asset_sha256=TX.CANDIDATE_SHA, ramdisk_sha256=sha(ramdisk),
                  firmware_files=52, changed_files=sum(r['changed'] for r in changes),
                  firmware_changes=changes, PD_maps_unchanged=True,
                  DTB_sha256=sha(source/'dtb'), bootconfig_sha256=sha(source/'bootconfig'),
                  command_arguments_before=before, command_arguments_after=verified,
                  commands=commands, tool_hashes=TOOLS, kernel_build_executed=False,
                  device_operations=False, authentication_verified=False, deployment_ready=False)
    (output/'BUILD.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-vendor', type=Path, required=True)
    parser.add_argument('--base-assets', type=Path, required=True)
    parser.add_argument('--candidate-assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = build(args.base_vendor, args.base_assets, args.candidate_assets, args.output)
    print(json.dumps({k: report[k] for k in ('verdict', 'candidate_vendor_sha256',
                                         'firmware_files', 'changed_files', 'deployment_ready')}))
