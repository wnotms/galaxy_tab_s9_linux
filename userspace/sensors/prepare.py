#!/usr/bin/env python3
"""Verify and patch Fedora X710 SSC sources on the host, without deployment."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile

BASE = Path(__file__).resolve().parent


def verified(path, row):
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing regular input: " + str(path))
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError("input hash mismatch: " + str(path))
    if "bytes" in row and len(data) != row["bytes"]:
        raise ValueError("input size mismatch: " + str(path))
    return data


def relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("invalid relative path: " + value)
    return path


def members(data, expected_root):
    """Validate every member before writing; inputs are small source archives."""
    entries = []
    seen = set()
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            path = relative(member.name)
            if path.parts[0] != expected_root:
                raise ValueError("unexpected archive root: " + member.name)
            if not member.isdir() and not member.isfile():
                raise ValueError("archive links/special files are not supported")
            if path in seen:
                raise ValueError("duplicate archive member: " + member.name)
            seen.add(path)
            total += member.size
            if total > 64 * 1024 * 1024 or len(seen) > 20000:
                raise ValueError("source archive limit exceeded")
            if len(path.parts) == 1:
                if not member.isdir():
                    raise ValueError("archive root must be a directory")
                continue
            if member.isfile():
                entries.append((Path(*path.parts[1:]), archive.extractfile(member).read(),
                                member.mode & 0o777))
    if not entries:
        raise ValueError("empty source archive")
    return entries


def prepare(manifest, cache, output, base=BASE):
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists; preserve the prior source tree")
    inputs = []
    names = set()
    for row in manifest["sources"]:
        name = row["name"]
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or name in names:
            raise ValueError("invalid or duplicate source name")
        names.add(name)
        filename = relative(row["filename"])
        if len(filename.parts) != 1:
            raise ValueError("cache filename must be a basename")
        source = members(verified(cache / filename, row), row["archive_root"])
        patches = [(p["path"], verified(base / relative(p["path"]), p))
                   for p in row["patches"]]
        inputs.append((row, source, patches))
    if not inputs:
        raise ValueError("no sources")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(verdict="HOST_SSC_SOURCES_PREPARED_NOT_BUILT", device_operations=False,
                  build_executed=False, installation_executed=False,
                  fedora_commit=manifest["fedora_commit"], sources=[])
    with tempfile.TemporaryDirectory(prefix=".ssc-prepare-", dir=output.parent) as temporary:
        stage = Path(temporary) / "sources"
        stage.mkdir()
        for row, entries, patches in inputs:
            tree = stage / row["name"]
            tree.mkdir()
            for path, data, mode in entries:
                target = tree / path
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
                target.chmod(mode)
            logs = []
            for name, data in patches:
                result = subprocess.run(["patch", "--batch", "--fuzz=0", "--forward",
                    "--no-backup-if-mismatch", "-p1"],
                    cwd=tree, input=data, capture_output=True, timeout=30)
                logs.append(dict(patch=name, returncode=result.returncode,
                                 stdout=result.stdout.decode(errors="replace"),
                                 stderr=result.stderr.decode(errors="replace")))
                if result.returncode:
                    raise ValueError("patch failed: " + name + "\n" + logs[-1]["stdout"] + logs[-1]["stderr"])
            hashes = {str(p.relative_to(tree)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(tree.rglob("*")) if p.is_file()}
            report["sources"].append(dict(name=row["name"], version=row["version"],
                archive_sha256=row["sha256"], patches=logs, patched_files=hashes))
        (stage / "PREPARED.json").write_text(json.dumps(report, indent=2) + "\n")
        if output.exists() or output.is_symlink():
            raise ValueError("output appeared during preparation")
        os.rename(stage, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=BASE / "sources.json")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(json.loads(args.manifest.read_text()), args.cache, args.output)
    print(json.dumps({k: v for k, v in report.items() if k != "sources"}, indent=2))


if __name__ == "__main__":
    main()
