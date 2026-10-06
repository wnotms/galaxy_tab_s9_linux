#!/usr/bin/env python3
"""Bounded host discovery; importing this module never contacts a device.

This locates an enrolled SSH endpoint. The charging runner must still verify
its current packet, boot history, pump state and registered observation gates.
"""
import argparse
import asyncio
from contextlib import suppress
from dataclasses import dataclass
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import time


RFC1918 = tuple(ipaddress.IPv4Network(x) for x in
                ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
IDENTITY_COMMAND = ('set -e; cat /etc/machine-id; '
                    'cat /proc/sys/kernel/random/boot_id; '
                    'zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes')


@dataclass(frozen=True)
class Identity:
    machine_id: str
    config_sha256: str
    notes_sha256: str
    boot_id: str = ''

    def validate(self):
        for value, size in [(self.machine_id, 32), (self.config_sha256, 64),
                            (self.notes_sha256, 64)]:
            if not re.fullmatch('[0-9a-f]{%d}' % size, value):
                raise ValueError('invalid expected identity')
        if self.boot_id and not re.fullmatch('[0-9a-f]{32}', self.boot_id):
            raise ValueError('invalid expected boot ID')


@dataclass(frozen=True)
class Settings:
    previous_ip: str
    key: Path
    known_hosts: Path
    alias: str
    total_seconds: float = 90
    tcp_seconds: float = 3
    ssh_seconds: float = 8
    concurrency: int = 16

    def validate(self):
        address = ipaddress.IPv4Address(self.previous_ip)
        if not any(address in network for network in RFC1918):
            raise ValueError('enrolled address must be RFC1918 IPv4')
        network = ipaddress.IPv4Network(str(address) + '/24', strict=False)
        if address in (network.network_address, network.broadcast_address):
            raise ValueError('enrolled address is not a host')
        if not 0 < self.total_seconds <= 90 or not 0 < self.tcp_seconds <= 3:
            raise ValueError('invalid discovery deadline')
        if not 0 < self.ssh_seconds <= 8 or not 1 <= self.concurrency <= 16:
            raise ValueError('invalid SSH/concurrency bound')
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]*', self.alias):
            raise ValueError('invalid enrolled alias')
        for path in (self.key, self.known_hosts):
            if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
                raise ValueError('key/trust file must be private regular file')
        # Do not create, replace, or opportunistically learn an SSH host key.
        rows = [x.split() for x in self.known_hosts.read_text().splitlines()]
        if not any(len(x) >= 3 and self.alias in x[0].split(',') and
                   x[1] == 'ssh-ed25519' for x in rows):
            raise ValueError('enrolled ed25519 alias missing')
        return network


def parse_identity(stdout, expected):
    lines = stdout.splitlines()
    if len(lines) != 4:
        return None
    boot = lines[1].replace('-', '')
    if not re.fullmatch('[0-9a-f]{32}', boot):
        return None
    if lines[0] != expected.machine_id or lines[2].split() != [expected.config_sha256, '-']:
        return None
    if lines[3].split() != [expected.notes_sha256, '/sys/kernel/notes']:
        return None
    if expected.boot_id and boot != expected.boot_id:
        return None
    return dict(machine_id=lines[0], boot_id=boot, config_sha256=expected.config_sha256,
                notes_sha256=expected.notes_sha256)


async def probe_tcp(address, seconds):
    writer = None
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(address, 22), seconds)
        return True
    except (OSError, asyncio.TimeoutError):
        return False
    finally:
        if writer is not None:
            writer.close()
            # An unauthenticated port probe need not wait for the peer's FIN.
            writer.transport.abort()


async def identify(address, seconds, settings, expected, emit):
    argv = ['ssh', '-i', str(settings.key), '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=3', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=' + str(settings.known_hosts),
            '-o', 'HostKeyAlias=' + settings.alias, 'root@' + address, IDENTITY_COMMAND]
    proc = None
    started = time.monotonic()
    emit('ssh-start', address=address, argv=argv, timeout_seconds=seconds)
    try:
        proc = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), seconds)
        raw = stdout.decode(errors='replace')
        match = parse_identity(raw, expected) if proc.returncode == 0 else None
        emit('ssh', address=address, argv=argv, returncode=proc.returncode,
             stdout=raw, stderr=stderr.decode(errors='replace'), matched=bool(match),
             seconds=time.monotonic() - started)
        return match
    except asyncio.TimeoutError:
        emit('ssh', address=address, status='timeout', seconds=time.monotonic() - started)
        return None
    finally:
        if proc is not None and proc.returncode is None:
            with suppress(ProcessLookupError):
                proc.kill()
            # Cancellation also drains the child before discovery returns.
            with suppress(asyncio.TimeoutError):
                stdout, stderr = await asyncio.wait_for(proc.communicate(), 0.5)
                emit('ssh-drained', address=address, returncode=proc.returncode,
                     stdout=stdout.decode(errors='replace'), stderr=stderr.decode(errors='replace'))


async def discover(settings, expected, emit, probe=probe_tcp, authenticate=identify):
    network = settings.validate()
    expected.validate()
    trust_digest = hashlib.sha256(settings.known_hosts.read_bytes()).hexdigest()
    start = time.monotonic()
    deadline = start + settings.total_seconds
    tasks = []
    winner = asyncio.get_running_loop().create_future()
    ssh_slots = asyncio.Semaphore(2)
    emit('start', network=str(network), previous_ip=settings.previous_ip,
         concurrency=settings.concurrency, tcp_seconds=settings.tcp_seconds,
         ssh_seconds=settings.ssh_seconds, total_seconds=settings.total_seconds)

    def remaining(cap):
        return max(0, min(cap, deadline - time.monotonic()))

    async def check(address):
        async with ssh_slots:
            seconds = remaining(settings.ssh_seconds)
            if seconds <= 0 or winner.done():
                return
            match = await asyncio.wait_for(
                authenticate(address, seconds, settings, expected, emit), seconds)
            if hashlib.sha256(settings.known_hosts.read_bytes()).hexdigest() != trust_digest:
                raise ValueError('enrolled host key file changed during discovery')
            if match and time.monotonic() < deadline and not winner.done():
                winner.set_result(dict(address=address, **match))

    async def sweep(pass_number):
        queue = asyncio.Queue()
        for address in network.hosts():
            if str(address) != settings.previous_ip:
                queue.put_nowait(str(address))

        async def worker():
            while not queue.empty() and not winner.done():
                address = queue.get_nowait()
                seconds = remaining(settings.tcp_seconds)
                if seconds <= 0:
                    return
                began = time.monotonic()
                emit('tcp-start', address=address, port=22, pass_number=pass_number,
                     timeout_seconds=seconds)
                try:
                    opened = await asyncio.wait_for(probe(address, seconds), seconds)
                    emit('tcp', address=address, port=22, pass_number=pass_number,
                         opened=opened, seconds=time.monotonic() - began)
                    if opened:
                        await check(address)
                except asyncio.TimeoutError:
                    emit('tcp-or-ssh-timeout', address=address, pass_number=pass_number)
                except asyncio.CancelledError:
                    emit('tcp-cancelled', address=address, pass_number=pass_number)
                    raise

        group = [asyncio.create_task(worker()) for _ in range(settings.concurrency)]
        tasks.extend(group)
        await asyncio.wait([winner, *group], return_when=asyncio.FIRST_COMPLETED)
        # A worker can finish early on an empty queue; still await the others.
        while not winner.done() and any(not x.done() for x in group):
            pending = [x for x in group if not x.done()]
            await asyncio.wait([winner, *pending], return_when=asyncio.FIRST_COMPLETED)
        for task in group:
            if task.done() and not task.cancelled() and task.exception():
                raise task.exception()

    async def search():
        for pass_number in (1, 2):
            # Never make a short raw TCP prefilter veto the enrolled recent IP.
            emit('preferred', address=settings.previous_ip, pass_number=pass_number)
            try:
                await check(settings.previous_ip)
            except asyncio.TimeoutError:
                emit('preferred-timeout', address=settings.previous_ip, pass_number=pass_number)
            if not winner.done():
                await sweep(pass_number)
            if winner.done():
                return winner.result()
        raise TimeoutError('no enrolled endpoint in bounded two-pass discovery')

    try:
        result = await asyncio.wait_for(search(), settings.total_seconds)
        emit('matched', **result, seconds=time.monotonic() - start)
        return result
    except BaseException as error:
        emit('stop', error=type(error).__name__, detail=str(error), seconds=time.monotonic() - start)
        raise
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        emit('drained', seconds=time.monotonic() - start)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous-ip', 'key', 'known-hosts', 'alias', 'machine-id',
                 'config-sha256', 'notes-sha256', 'report'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--boot-id', default='')
    args = parser.parse_args()
    settings = Settings(args.previous_ip, Path(args.key), Path(args.known_hosts), args.alias)
    expected = Identity(args.machine_id, args.config_sha256, args.notes_sha256, args.boot_id)
    settings.validate()
    expected.validate()
    folder = Path(args.report)
    folder.mkdir(parents=True, exist_ok=False)  # never overwrite an earlier attempt
    summary = dict(verdict='STOP', read_only=True, reboot=False, partition_write=False)
    with (folder / 'events.jsonl').open('w') as events:
        def emit(kind, **values):
            events.write(json.dumps(dict(kind=kind, **values)) + '\n')
            events.flush()
        try:
            match = asyncio.run(discover(settings, expected, emit))
            summary.update(verdict='ENROLLED_ENDPOINT_FOUND', **match)
        except Exception as error:
            summary['error'] = repr(error)
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    return 0 if summary['verdict'] == 'ENROLLED_ENDPOINT_FOUND' else 1


if __name__ == '__main__':
    raise SystemExit(main())
