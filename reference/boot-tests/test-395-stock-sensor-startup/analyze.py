#!/usr/bin/env python3
"""Offline ELF metadata; never execute stock binaries or contact the tablet."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

R = Path(__file__).resolve().parent
ROOT = R.parents[2]
spec = importlib.util.spec_from_file_location('startup395', R/'host_flow.py')
flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow)


def main():
    archive = ROOT/'out/ssc-stock-startup395.tar.gz'
    result = json.loads((R/'summary.json').read_text())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != result['archive_sha256']:
        raise ValueError('physical archive changed')
    manifest = flow.archive_manifest(archive, result['boot_id'])
    output = R/'offline-analysis'
    output.mkdir(exist_ok=False)
    report = dict(archive_sha256=result['archive_sha256'], binaries_executed=False,
        device_contacted=False, llvm_version=subprocess.check_output(['llvm-readelf', '--version'], text=True),
        symbol_policy='summary: sns_/remote_handle/adsp_default_listener prefixes; complete dynsym retained in compressed readelf',
        files={}, sensor_acceptance=False)
    with tarfile.open(archive) as source, tempfile.TemporaryDirectory(prefix='ssc-startup395-', dir=ROOT/'out') as folder:
        for name, meta in manifest['files'].items():
            raw = source.extractfile(name).read()
            if meta['elf_machine'] is None:
                if name.endswith('.rc') or name.endswith('init.qcom.sensors.sh'):
                    # Derived non-comment startup lines, original hash in manifest.
                    report['files'][name] = dict(source_sha256=meta['sha256'],
                        active_lines=[x for x in raw.decode().splitlines() if x.strip() and not x.lstrip().startswith('#')])
                continue
            path = Path(folder)/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            elf = subprocess.run(['llvm-readelf', '--dynamic', '--dyn-syms', '--wide', str(path)],
                capture_output=True, timeout=10, check=True)
            label = name.replace('/', '__')
            (output/(label+'.elf.txt.gz')).write_bytes(gzip.compress(elf.stdout, mtime=0))
            text = elf.stdout.decode()
            symbols = []
            for line in text.splitlines():
                fields = line.split()
                if (len(fields) == 8 and fields[0].rstrip(':').isdigit() and fields[4] in ('GLOBAL', 'WEAK') and
                        fields[7].startswith(('sns_', 'remote_handle', 'adsp_default_listener'))):
                    symbols.append(dict(name=fields[7], defined=fields[6] != 'UND', type=fields[3]))
            strings = subprocess.run(['strings', '-t', 'x', str(path)], capture_output=True, timeout=10, check=True)
            (output/(label+'.strings.txt.gz')).write_bytes(gzip.compress(strings.stdout, mtime=0))
            report['files'][name] = dict(source_sha256=meta['sha256'], elf_machine=meta['elf_machine'],
                needed=re.findall(r'\(NEEDED\).*?\[(.*?)\]', text), symbols=symbols,
                sns_related_strings=[x for x in strings.stdout.decode(errors='replace').splitlines()
                    if re.search('sns_dynamic_loader|sns_remote_proc_state|createstaticpd|attachguestos|default_listener|boot_slpi', x)])
            if name in ('vendor/bin/sscrpcd', 'vendor/lib64/libadsp_default_listener.so',
                        'vendor/lib64/libssc_default_listener.so'):
                assembly = subprocess.run(['llvm-objdump', '-d', '--no-show-raw-insn', str(path)],
                    capture_output=True, timeout=10, check=True)
                (output/(label+'.disassembly.txt.gz')).write_bytes(gzip.compress(assembly.stdout, mtime=0))
    (output/'analysis.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
