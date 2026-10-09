#!/usr/bin/env python3
"""Bridge verified Type-C cable edges to the existing fixed-peripheral gadget.

Never change descriptors, roles, adbd, PD policy or charger registers. Deployment
requires an independently registered profile; importing this module is passive.
"""
import argparse
import fcntl
import gzip
import hashlib
import json
import select
import signal
import socket
import subprocess
import time
from pathlib import Path


class GuardError(RuntimeError):
    pass


def cable_state(partner, online):
    # A hard reset may temporarily remove VBUS while the partner remains.
    if partner is False and online == 0:
        return 'detached'
    if partner is True and online == 1:
        return 'attached'
    return 'unknown'


class CableEdges:
    def __init__(self, debounce=1.0):
        self.debounce = debounce
        self.pending = None
        self.since = None

    def observe(self, state, now):
        if state == 'unknown':
            self.pending = self.since = None
            return None
        if state != self.pending:
            self.pending, self.since = state, now
            return None
        return state if now - self.since >= self.debounce else None


class Gadget:
    def __init__(self, root, profile):
        self.root = Path(root)
        self.profile = profile
        self.path = self.root / 'sys/kernel/config/usb_gadget/gts9'
        self.udc = self.path / 'UDC'
        self.owned_unbound = False
        self.boot = self.read('proc/sys/kernel/random/boot_id')
        self.identity()
        self.fingerprint = self.describe()
        self.check_layout()
        if self.udc.read_text().strip() != 'a600000.usb':
            raise GuardError('initial binding unknown; do not adopt an empty UDC')

    def read(self, name):
        return (self.root / name).read_text().strip()

    def identity(self):
        config = gzip.decompress((self.root / 'proc/config.gz').read_bytes())
        notes = (self.root / 'sys/kernel/notes').read_bytes()
        if (self.read('etc/machine-id') != self.profile['machine_id'] or
            self.read('proc/sys/kernel/random/boot_id') != self.boot or
            self.read('proc/sys/kernel/osrelease') != self.profile['release'] or
            hashlib.sha256(config).hexdigest() != self.profile['config_sha256'] or
            hashlib.sha256(notes).hexdigest() != self.profile['notes_sha256'] or
            b'# CONFIG_HVC_DCC is not set\n' not in config or
            self.read('sys/module/sm5440_fedora/parameters/direct_charge') not in ('N', '0')):
            raise GuardError('unregistered boot/kernel or direct-charge state')
        if (self.read('sys/class/typec/port0/power_role') != '[sink]' or
            self.read('sys/class/typec/port0/data_role') != '[device]'):
            raise GuardError('not the registered Sink/Device peripheral')

    def describe(self):
        return dict(vendor=(self.path / 'idVendor').read_text().strip(),
                    product=(self.path / 'idProduct').read_text().strip(),
                    functions=sorted(p.name for p in (self.path / 'functions').iterdir()),
                    links=sorted((str(p.relative_to(self.path)), str(p.resolve()))
                                 for p in (self.path / 'configs').rglob('*') if p.is_symlink()))

    def check_layout(self):
        d = self.describe()
        if (d != self.fingerprint or int(d['vendor'], 16) != 0x0525 or
            int(d['product'], 16) != 0xa4a7 or
            d['functions'] != ['ffs.adb', 'ncm.usb0'] or
            len(d['links']) != 2 or
            {x[0] for x in d['links']} != {'configs/c.1/ffs.adb', 'configs/c.1/ncm.usb0'} or
            {x[1] for x in d['links']} != {str(self.path / 'functions/ffs.adb'),
                                        str(self.path / 'functions/ncm.usb0')}):
            raise GuardError('shared gadget layout changed')

    def state(self):
        self.identity()
        online = self.read('sys/class/power_supply/sm5714-usb/online')
        if online not in ('0', '1'):
            raise GuardError('invalid USB online observation')
        return cable_state((self.root / 'sys/class/typec/port0-partner').exists(), int(online))

    def write_binding(self, value):
        # A stop signal between a successful sysfs write and our ownership
        # update must not strand the shared gadget. SIGKILL cannot be handled;
        # service auto-restart is deliberately disabled for that unknown state.
        signals = {signal.SIGTERM, signal.SIGINT}
        old = signal.pthread_sigmask(signal.SIG_BLOCK, signals)
        try:
            self.udc.write_text(value + '\n')
            self.owned_unbound = True
            if self.udc.read_text().strip() != value:
                raise GuardError('binding write/readback mismatch')
            self.owned_unbound = not bool(value)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old)

    def apply(self, stable):
        self.identity()
        self.check_layout()
        bound = self.udc.read_text().strip()
        expected = '' if self.owned_unbound else 'a600000.usb'
        if bound != expected:
            raise GuardError('another actor changed UDC; refuse to overwrite')
        # Recheck cable immediately before the write. No delayed stale action.
        if stable not in ('attached', 'detached') or self.state() != stable:
            return None
        if stable == 'detached' and not self.owned_unbound:
            self.write_binding('')
            return 'unbind'
        if stable == 'attached' and self.owned_unbound:
            self.write_binding('a600000.usb')
            return 'bind'
        return None

    def restore(self):
        if self.owned_unbound:
            self.identity()
            self.check_layout()
            bound = self.udc.read_text().strip()
            if bound == 'a600000.usb':
                self.owned_unbound = False
                return
            if bound:
                raise GuardError('owned empty binding changed; recovery refused')
            self.write_binding('a600000.usb')


def relevant_uevent(data, sender):
    if sender[0] != 0 or len(data) >= 65536:
        return False
    fields = {}
    for part in data.split(b'\0')[1:]:
        if b'=' in part:
            key, value = part.split(b'=', 1)
            if key in fields:
                return False
            fields[key] = value
    return (fields.get(b'SUBSYSTEM') == b'typec' or
            (fields.get(b'SUBSYSTEM') == b'power_supply' and
             fields.get(b'DEVPATH', b'').endswith(b'/sm5714-usb')))


def serve(gadget, sock, clock=time.monotonic):
    edges = CableEdges()
    pending_check = clock()  # Initial detached stale state is also repaired.
    try:
        while True:
            now = clock()
            timeout = None if pending_check is None else max(0, pending_check - now)
            if select.select([sock], [], [], timeout)[0]:
                data, sender = sock.recvfrom(65536)
                if relevant_uevent(data, sender) and pending_check is None:
                    pending_check = clock() + 0.1
            if pending_check is not None and clock() >= pending_check:
                state = gadget.state()
                stable = edges.observe(state, clock())
                if stable is not None:
                    action = gadget.apply(stable)
                    if action:
                        print(json.dumps(dict(boot_id=gadget.boot, event=action,
                                              cable=stable, monotonic=clock())), flush=True)
                    pending_check = None
                elif state == 'unknown':
                    # Await a real new Type-C/USB event. Do not poll the I2C
                    # supply or reset a live link through a PD transient.
                    pending_check = None
                else:
                    pending_check = clock() + edges.debounce
    finally:
        gadget.restore()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', type=Path, required=True)
    args = ap.parse_args()
    profile = json.loads(args.profile.read_text())
    with Path('/run/gts9-usb-typec-lifecycle.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        gadget = Gadget('/', profile)
        if subprocess.run(['systemctl', 'is-active', '--quiet', 'gts9-adbd'], timeout=5).returncode:
            raise GuardError('adbd not ready; no UDC action')
        def stop(signum, frame):
            raise InterruptedError('lifecycle service stopped')
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        with socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, 15) as sock:
            sock.bind((0, 1))
            serve(gadget, sock)


if __name__ == '__main__':
    try:
        main()
    except InterruptedError:
        pass
