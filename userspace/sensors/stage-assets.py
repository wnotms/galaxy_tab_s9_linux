#!/usr/bin/env python3
"""Create a private offline sensor asset tar; never install or start an ADSP."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

PREFIX = 'usr/share/qcom/sm8550/Samsung/gts9wifi/'


def load(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('source archive hash mismatch')
    files, times = {}, {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        for m in t:
            p = PurePosixPath(m.name)
            if (not m.isfile() or str(p) != m.name or p.is_absolute() or '..' in p.parts
                    or m.name in files or not 0 <= m.size <= 64*1024*1024):
                raise ValueError('unsafe archive member')
            total += m.size
            if total > 192*1024*1024 or len(files) >= 8193:
                raise ValueError('archive bounds exceeded')
            files[m.name] = t.extractfile(m).read()
            times[m.name] = m.mtime
    manifest = json.loads(files.pop('MANIFEST.json'))
    if set(files) != set(manifest['files']):
        raise ValueError('source file set mismatch')
    for n,b in files.items():
        e = manifest['files'][n]
        if (len(b) != e['bytes'] or hashlib.sha256(b).hexdigest() != e['sha256']
                or times[n] != e['archive_mtime']):
            raise ValueError('source member identity/mtime mismatch')
    return manifest,files


def plan(stock, vendor):
    sm,sf = stock
    vm,vf = vendor
    if (sm['purpose'] != 'READ_ONLY_STOCK_SENSOR_ASSETS' or sm['firmware_installed']
            or sm['remoteproc_started'] or not sm['temporary_mounts_removed']
            or sm['cleanup_errors'] or sm['skipped_links']
            or vm['purpose'] != 'READ_ONLY_VENDOR_SENSOR_CONFIG' or vm['device_deployment']
            or not vm['temporary_mount_and_loop_removed'] or vm['boot_id'] != sm['boot_id']):
        raise ValueError('unqualified source collection')
    cache = json.loads(sf['persist/sensors/registry/registry/sns_reg_config'])['sns_reg_config']
    expected = {n.lstrip('/') for n in cache if n != 'owner'}
    actual = {n for n in vf if n.startswith('vendor/etc/sensors/config/')}
    if expected != actual:
        raise ValueError('registry config input set differs')
    for n in expected:
        if (cache['/'+n]['type'] != 'int'
                or int(cache['/'+n]['data']) != vm['files'][n]['archive_mtime']):
            raise ValueError('registry config timestamp mismatch')
    if sf.get('persist/sensors/registry/registry/sensors_registry') != b'':
        raise ValueError('registry completion marker missing')
    outputs = {}

    def add(target, name, files, manifest):
        if target in outputs:
            raise ValueError('destination collision')
        outputs[target] = dict(source=name,bytes=files[name],
                               mtime=manifest['files'][name]['archive_mtime'])

    for n in sf:
        if n.startswith('apnhlos/image/'):
            tail = n.removeprefix('apnhlos/image/')
            if '/' in tail or not tail.startswith('adsp'):
                raise ValueError('unexpected firmware path')
            add('usr/lib/firmware/qcom/sm8550/'+tail,n,sf,sm)
        elif n.startswith('dsp/adsp/'):
            add(PREFIX+n,n,sf,sm)
        elif n.startswith('persist/sensors/registry/'):
            tail = n.removeprefix('persist/sensors/registry/')
            add(PREFIX+'sensors/'+tail,n,sf,sm)
    for n in expected:
        add(PREFIX+'sensors/config/'+PurePosixPath(n).name,n,vf,vm)
    add(PREFIX+'sensors/sns_reg.conf','vendor/etc/sensors/sns_reg_config',vf,vm)
    for n in ('adsp.mdt','adsp_dtb.mdt'):
        if 'usr/lib/firmware/qcom/sm8550/'+n not in outputs:
            raise ValueError('required ADSP MDT absent')
    for n in ('libsns_dynamic_loader_skel.so','libsns_remote_proc_state_skel.so'):
        if PREFIX+'dsp/adsp/'+n not in outputs:
            raise ValueError('sensor PD library absent')
    return outputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('stock','vendor'):
        p.add_argument('--'+n,type=Path,required=True)
        p.add_argument('--'+n+'-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    # Reuse all existing firmware structural/region/cache checks without policy
    # changes. Hash the bytes again when reading each source for the mapping.
    spec = importlib.util.spec_from_file_location('stock_verifier',Path(__file__).with_name('verify-stock-assets.py'))
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.verify_archive(args.stock,args.stock_sha256)
    outputs = plan(load(args.stock,args.stock_sha256),load(args.vendor,args.vendor_sha256))
    args.output.mkdir(mode=0o700,exist_ok=False)
    archive = args.output/'sensor-assets.tar.gz'
    with archive.open('xb') as f:
        archive.chmod(0o600)
        with tarfile.open(fileobj=f,mode='w:gz') as t:
            for n,e in sorted(outputs.items()):
                info=tarfile.TarInfo(n);info.size=len(e['bytes']);info.mtime=e['mtime']
                info.mode=0o600 if '/sensors/registry/' in n else 0o644
                t.addfile(info,io.BytesIO(e['bytes']))
    # Reopen the output instead of treating successful creation as verification.
    with tarfile.open(archive) as t:
        members=t.getmembers()
        if len(members) != len(outputs) or {m.name for m in members} != set(outputs):
            raise ValueError('staged file set mismatch')
        for m in members:
            e=outputs[m.name]
            if (not m.isfile() or m.uid or m.gid or m.mtime != e['mtime']
                    or t.extractfile(m).read() != e['bytes']):
                raise ValueError('staged content/ownership/mtime mismatch')
    result=dict(verdict='OFFLINE_ASSET_ARCHIVE_VERIFIED_NOT_INSTALLED',
        source_archives={'stock':args.stock_sha256,'vendor':args.vendor_sha256},
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        files={n:dict(source=e['source'],bytes=len(e['bytes']),mtime=e['mtime'],
                       sha256=hashlib.sha256(e['bytes']).hexdigest()) for n,e in sorted(outputs.items())},
        device_deployment_ready=False,
        outstanding=['controlled early-boot activation registration',
                     'socinfo virtual input mapping (stock sysfs path absent)',
                     'runtime one-attempt units and dependency installation'],
        excluded=['CDSP libraries','Android hals.conf','real persist access'])
    (args.output/'STAGED.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(verdict=result['verdict'],files=len(outputs),device_deployment_ready=False)))


if __name__ == '__main__':
    main()
