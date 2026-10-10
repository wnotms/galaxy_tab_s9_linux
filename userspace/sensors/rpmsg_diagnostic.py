#!/usr/bin/env python3
"""One registered AP-initiated DIAG handshake; no DIAG masks or data writes.

Does not load/unload modules, start ADSP/RPC, change bindings or configure USB.
Run only inside a separately registered early-ADSP test with mandatory rollback.
Kernel endpoint open can wait twice for 5s; the caller must impose a 15s timeout.
"""
import argparse
import base64
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import struct
import time
from uuid import UUID

CREATE_EPT = 0x4028b501
DESTROY_EPT = 0xb502
ADDR_ANY = 0xffffffff
MAX_PACKET = 65536


def endpoint_request(name='DIAG'):
    if name != 'DIAG':
        raise ValueError('only the registered DIAG channel is allowed')
    return struct.pack('<32sII', b'DIAG', ADDR_ANY, ADDR_ANY)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Native:
    def admit(self, plan):
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if UUID(boot) != UUID(plan['boot_id']):
            raise ValueError('boot identity changed')
        if Path('/proc/cmdline').read_text().strip() != plan['cmdline']:
            raise ValueError('registered cmdline changed')
        if digest(gzip.decompress(Path('/proc/config.gz').read_bytes())) != plan['config_sha256']:
            raise ValueError('kernel config identity changed')
        if digest(Path('/sys/kernel/notes').read_bytes()) != plan['notes_sha256']:
            raise ValueError('kernel notes identity changed')
        note = Path('/sys/module/rpmsg_ctrl/notes/.note.gnu.build-id')
        if digest(note.read_bytes()) != plan['module_build_id_note_sha256']:
            raise ValueError('loaded control module identity changed')
        if Path('/sys/class/remoteproc/remoteproc0/state').read_text().strip() != 'running':
            raise ValueError('ADSP is not running')
        parent = Path(plan['rpmsg_parent']).resolve(strict=True)
        prefix = '/sys/devices/platform/soc@0/6800000.remoteproc/'
        if not str(parent).startswith(prefix) or ':glink-edge.rpmsg_ctrl.' not in parent.name:
            raise ValueError('not the registered ADSP control parent')
        entries = list(Path('/sys/class/rpmsg').glob('rpmsg_ctrl*'))
        if (len(entries) != 1 or entries[0].resolve().parent.parent != parent or
                entries[0].resolve() != Path(plan['controller']).resolve(strict=True)):
            raise ValueError('control device is not unique or registered')
        controller = entries[0]
        self.device(controller)
        if self.endpoints(controller):
            raise ValueError('pre-existing endpoint: no adoption')
        return controller

    def device(self, entry):
        if not re.fullmatch(r'rpmsg(?:_ctrl)?[0-9]+', entry.name):
            raise ValueError('unexpected device name')
        node = Path('/dev') / entry.name
        mode = node.lstat()
        major, minor = map(int, (entry / 'dev').read_text().strip().split(':'))
        if not stat.S_ISCHR(mode.st_mode) or mode.st_rdev != os.makedev(major, minor):
            raise ValueError('node is not the matching native character device')
        return node

    def endpoints(self, controller):
        parent = controller.resolve()
        return {p.resolve() for p in Path('/sys/class/rpmsg').glob('rpmsg[0-9]*')
                if parent in p.resolve().parents}

    def open_control(self, controller):
        return os.open(self.device(controller), os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)

    def create(self, fd):
        fcntl.ioctl(fd, CREATE_EPT, endpoint_request())

    def owned_endpoint(self, controller):
        limit = time.monotonic() + 2
        while True:
            entries = self.endpoints(controller)
            if len(entries) == 1:
                entry = next(iter(entries))
                if (entry / 'name').read_text().strip() != 'DIAG':
                    raise ValueError('unexpected created endpoint name')
                self.device(entry)
                return entry
            if len(entries) > 1 or time.monotonic() >= limit:
                raise ValueError('created endpoint missing or not unique')
            time.sleep(0.05)

    def open_endpoint(self, entry):
        # Driver open, not CREATE_EPT, initiates GLINK OPEN and waits for ACK.
        return os.open(self.device(entry), os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)

    def receive(self, fd):
        ready, _, _ = select.select([fd], [], [], 1)
        if not ready:
            return b''
        packet = os.read(fd, MAX_PACKET)
        if not packet:
            raise ConnectionError('endpoint EOF while ready; not an idle channel')
        return packet

    def destroy(self, fd):
        # Destroy through the already open FD. Never reopen a failed endpoint.
        fcntl.ioctl(fd, DESTROY_EPT)

    def close(self, fd):
        os.close(fd)


def probe(plan, native, ledger):
    if plan.get('channel') != 'DIAG' or plan.get('payload_writes') is not False:
        raise ValueError('unregistered channel or data policy')
    controller = native.admit(plan)
    # O_EXCL preserves one attempt and never adopts another boot's ledger.
    with ledger.open('x') as stream:
        json.dump(dict(boot_id=plan['boot_id'], phase='before-create', channel='DIAG'), stream)
    state = dict(boot_id=plan['boot_id'], channel='DIAG', complete=False,
                 payload_writes=0, masks_sent=0, endpoint_opened=False,
                 endpoint_destroyed=False, requires_registered_reboot=False)
    control = endpoint = None
    created = False
    try:
        control = native.open_control(controller)
        native.create(control); created = True
        state.update(phase='endpoint-device-created', requires_registered_reboot=True)
        ledger.write_text(json.dumps(state, indent=2) + '\n')
        entry = native.owned_endpoint(controller)
        endpoint = native.open_endpoint(entry)
        state.update(endpoint_opened=True, phase='endpoint-opened')
        ledger.write_text(json.dumps(state, indent=2) + '\n')
        packet = native.receive(endpoint)
        if len(packet) > MAX_PACKET:
            raise ValueError('packet evidence cap exceeded')
        state.update(packet_bytes=len(packet), packet_base64=base64.b64encode(packet).decode(),
                     packet_sha256=digest(packet), complete=True,
                     verdict='DIAG_OPEN_COMPLETED_NO_PAYLOAD_SENT')
    except Exception as exc:
        state.update(error=str(exc), verdict='STOP_DIAG_HANDSHAKE_OR_EVIDENCE')
    finally:
        if endpoint is not None:
            try:
                native.destroy(endpoint); state['endpoint_destroyed'] = True
            except Exception as exc:
                state.update(complete=False, cleanup_error=str(exc), verdict='STOP_ENDPOINT_CLEANUP')
            finally:
                native.close(endpoint)
        if control is not None:
            native.close(control)
        state['requires_registered_reboot'] = created and not state['endpoint_destroyed']
        # Never unload control driver or retry an endpoint here; rollback owns it.
        ledger.write_text(json.dumps(state, indent=2) + '\n')
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('registered native device operation requires root')
    plan = json.loads(args.plan.read_text())
    if args.ledger.parent != Path('/run/gts9-test384') or not args.ledger.parent.is_dir() or args.ledger.parent.is_symlink():
        raise ValueError('not the registered runner-owned ledger directory')
    result = probe(plan, Native(), args.ledger)
    print(json.dumps(result))
    raise SystemExit(0 if result['complete'] else 1)
