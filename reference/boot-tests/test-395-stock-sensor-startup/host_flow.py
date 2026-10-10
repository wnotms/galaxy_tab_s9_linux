#!/usr/bin/env python3
"""Test395: one read-only stock startup export, no DSP/RPC/reboot/flash."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[3]
R = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load('startup395_base', R.parent/'test-393-standard-pdr-listener/host_flow.py')
GUARD = load('startup395_health', R.parent/'test-371-usb-lifecycle-gmu/host_flow.py')
COLLECT = load('startup395_collect', ROOT/'userspace/sensors/read-vendor-sensor-startup.py')
p = BASE.p
PLAN = json.loads((R/'registration.json').read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def verify(pushed=False):
    for name, digest in json.loads((R/'INPUTS.json').read_text()).items():
        path = ROOT/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('registered input drift: '+name)
    if pushed:
        git = lambda *args: subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
        if (git('branch', '--show-current') != 'test' or
                git('rev-parse', 'HEAD') != git('rev-parse', 'origin/test') or
                git('status', '--porcelain')):
            raise ValueError('clean registration must be pushed to origin/test')


def snapshot(rec, name):
    raw, _ = rec.adb(name, BASE.CAPTURE, timeout=15)
    data = json.loads(raw)
    BASE.identity(data, 'baseline', PLAN['boot_id'])
    if (data['services']['gdm'] != 'active' or len(data['adsp']) != 1 or
            data['adsp'][0]['state'] != 'offline'):
        raise ValueError('accepted desktop/ADSP-offline baseline changed')
    return data


def kernel(rec, name, before):
    raw, _ = rec.adb(name, 'journalctl -k -b -o json --no-pager', timeout=15)
    rows = GUARD.journal(raw, PLAN['boot_id'])
    GUARD.health(rows, before, {})
    return rows


def preflight():
    verify()
    folder = R/'preflight'
    folder.mkdir(exist_ok=False)
    rec = p.Recorder(folder)
    p.SERIAL = 'gts9wifi-0001'
    data = snapshot(rec, 'identity')
    prior = ROOT/PLAN['enrolled_kernel']
    kernel(rec, 'kernel', GUARD.journal(prior.read_text(), PLAN['boot_id']))
    raw, _ = rec.ps('windows-usb', p.PS_USB, timeout=20)
    if p.has_code43(raw):
        raise ValueError('Windows Code43')
    write(folder/'summary.json', dict(verdict='READONLY_PREFLIGHT_PASS', epoch=time.time(), snapshot=data,
        partition_module_identity_reused='Test394 same returned boot, no writes since',
        no_kernel_build=True))


def archive_manifest(path, boot):
    if path.stat().st_size > 70 * 1024 * 1024:
        raise ValueError('archive bound')
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        if (len(names) > COLLECT.MAX_FILES+1 or len(names) != len(set(names)) or
                'MANIFEST.json' not in names or any(not m.isfile() or m.size > COLLECT.MAX_FILE_BYTES for m in members) or
                sum(m.size for m in members) > COLLECT.MAX_TOTAL_BYTES+2*1024*1024):
            raise ValueError('archive member/bounds')
        manifest = json.load(archive.extractfile('MANIFEST.json'))
        if (manifest['boot_id'] != boot or manifest['purpose'] != 'READ_ONLY_X710_SENSOR_STARTUP_INPUTS' or
                not manifest['temporary_mount_and_loop_removed'] or
                any(manifest[key] for key in ('binaries_executed', 'DSP_started', 'partitions_written', 'registry_written'))):
            raise ValueError('collection identity/cleanup evidence')
        if not manifest['files'] or set(names) != set(manifest['files']) | {'MANIFEST.json'}:
            raise ValueError('manifest/archive member disagreement')
        for name, meta in manifest['files'].items():
            rel = Path(name)
            if (rel.parts[0] != 'vendor' or '..' in rel.parts or rel.is_absolute() or
                    not COLLECT.selected(str(rel.parent.relative_to('vendor')), rel.name)):
                raise ValueError('unexpected stock export path')
            data = archive.extractfile(name).read()
            if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
                raise ValueError('stock export hash mismatch')
    return manifest


def run():
    verify(pushed=True)
    if (R/'execution').exists():
        raise ValueError('one export already consumed; no replay')
    initial = json.loads((R/'preflight/summary.json').read_text())
    if initial['verdict'] != 'READONLY_PREFLIGHT_PASS' or time.time()-initial['epoch'] > 600:
        raise ValueError('missing/stale preflight')
    rec = p.Recorder(R/'execution')
    p.SERIAL = 'gts9wifi-0001'
    snapshot(rec, 'boundary')
    output = ROOT/'out/ssc-stock-startup395.tar.gz'
    if output.exists():
        raise ValueError('owned host output already exists')
    # Inline the pinned helper modules without installing scripts in the rootfs.
    source = "import types,sys\nlayout=types.ModuleType('vendor_layout')\n"
    source += 'exec('+repr((ROOT/'userspace/sensors/read-vendor-sensors.py').read_text())+',layout.__dict__)\n'
    source += "collector=types.ModuleType('vendor_startup')\n"
    source += 'exec('+repr((ROOT/'userspace/sensors/read-vendor-sensor-startup.py').read_text())+',collector.__dict__)\n'
    source += 'sys.argv=["collector","--boot-id",'+repr(PLAN['boot_id'])+']\ncollector.main(layout)\n'
    encoded = base64.b64encode(source.encode()).decode()
    program = 'import base64;exec(base64.b64decode('+repr(encoded)+'))'
    # INT allows Python's finally cleanup; host timeout/forced kill is UNKNOWN,
    # never assumed cleanup success and never automatically retried.
    command = 'timeout --signal=INT --kill-after=15 45 python3 -c '+shlex.quote(program)
    argv = [p.ADB, '-s', p.SERIAL, 'exec-out', command]
    started = time.time()
    with output.open('xb') as stream:
        try:
            result = subprocess.run(argv, stdout=stream, stderr=subprocess.PIPE, timeout=75)
            status, stderr = result.returncode, result.stderr
        except subprocess.TimeoutExpired as error:
            status, stderr = 'timeout', error.stderr or b''
    (rec.folder/'export.stderr').write_bytes(stderr)
    write(rec.folder/'export.command.json', dict(argv=argv, status=status, seconds=time.time()-started,
        host_archive=str(output.relative_to(ROOT))))
    if status != 0:
        raise ValueError('export failed; cleanup unknown, no replay: '+str(status))
    manifest = archive_manifest(output, PLAN['boot_id'])
    write(rec.folder/'stock-manifest.json', manifest)
    after = snapshot(rec, 'after')
    prior = GUARD.journal((R/'preflight/kernel.txt').read_text(), PLAN['boot_id'])
    kernel(rec, 'kernel-after', prior)
    raw, _ = rec.adb('cleanup-state', 'cat /proc/mounts; losetup --list --output NAME,BACK-FILE,RO,OFFSET,SIZELIMIT', timeout=10)
    if 'gts9-sensor-startup-' in raw:
        raise ValueError('owned vendor mount still present')
    write(R/'summary.json', dict(verdict='STOCK_STARTUP_EXPORTED_UNCHANGED_DESKTOP', boot_id=after['boot_id'],
        files=len(manifest['files']), archive_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        archive_bytes=output.stat().st_size, temporary_mount_and_loop_removed=True,
        partition_module_identity_reused='Test394; no writes/reboot',
        DSP_started=False, binaries_executed=False, flashed=False, rebooted=False,
        kernel_rebuilt=False, PPS=False, pump_ON=False, sensor_acceptance=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'preflight', 'run'])
    action = parser.parse_args().action
    {'verify': verify, 'preflight': preflight, 'run': run}[action]()
