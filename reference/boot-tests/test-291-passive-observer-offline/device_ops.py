#!/usr/bin/env python3
"""Recorded one-call passive observation; no trace/deployment/charging."""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import subprocess

import time

def boot_id(raw):
    import uuid
    return str(uuid.UUID(raw.strip()))

from coordinator import run_once, OBSERVER_SHA256, PROVIDER_NOTES_SHA256
import health_gate


RESULT = Path('/sys/kernel/debug/sm5440-passive-observer/result')
LOADED = Path('/sys/module/sm5440_passive_observer')


class DeviceOps:
    def __init__(self, folder, module, packet):
        self.folder, self.module, self.packet = Path(folder), Path(module), packet
        self.folder.mkdir()
        self.index = 0

    def command(self, name, argv, timeout):
        prefix = self.folder / (f'{self.index:03}-' + name)
        self.index += 1
        try:
            proc = subprocess.run(argv, capture_output=True, timeout=timeout)
            stdout, stderr, status = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, status = exc.stdout or b'', exc.stderr or b'', 'timeout'
        prefix.with_suffix('.txt').write_bytes(stdout)
        prefix.with_suffix('.stderr').write_bytes(stderr)
        prefix.with_suffix('.json').write_text(json.dumps({'argv':argv,'timeout_seconds':timeout,'status':status},indent=2)+'\n')
        if status != 0:
            raise RuntimeError(name + ': ' + str(status))
        return stdout.decode()

    def verified_identity(self):
        packet = self.packet
        if packet['test'] != 'Test292' or packet['verdict'] != 'READY_FOR_REGISTERED_PASSIVE_OBSERVATION':
            raise ValueError('unaccepted registration')
        if packet['paired_install_verified'] is not True or packet['health_rescue_verified'] is not True:
            raise ValueError('paired readback/health unverified')
        if packet['candidate_notes_sha256'] != PROVIDER_NOTES_SHA256:
            raise ValueError('provider identity')
        if packet['observer_sha256'] != OBSERVER_SHA256 or hashlib.sha256(self.module.read_bytes()).hexdigest() != OBSERVER_SHA256:
            raise ValueError('observer identity')
        if LOADED.exists() or RESULT.exists():
            raise ValueError('observer already present; cannot adopt')
        raw=self.command('live-preflight',['/bin/sh','-c',packet['current_command']],10)
        sec=health_gate.sections(raw)
        boot,_=health_gate.identity(sec,packet,packet['candidate_notes_sha256'],packet['boot_id'])
        if self.boot().replace('-','') != boot:
            raise ValueError('preflight boot changed')
        return dict(packet,boot_id=self.boot(),normal_cmdline_verified=True,observer_absent=True)

    def boot(self):
        return boot_id(Path('/proc/sys/kernel/random/boot_id').read_text())

    def boottime_ms(self):
        return time.clock_gettime_ns(time.CLOCK_BOOTTIME) // 1000000

    def load(self, timeout):
        self.command('insmod-once',['/sbin/insmod',str(self.module)],timeout)

    def cached_result(self):
        return RESULT.read_text()

    def unload(self, timeout):
        # Called only after one attempted load and initial absence established.
        if LOADED.exists():
            self.command('rmmod-once',['/sbin/rmmod','sm5440_passive_observer'],timeout)
        if LOADED.exists() or RESULT.exists():
            raise ValueError('observer/debugfs remain after unload')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--packet-sha256',required=True)
    parser.add_argument('--module',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.packet.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.packet_sha256:
        parser.error('packet identity')
    packet=json.loads(raw)
    if packet.get('verdict')!='READY_FOR_REGISTERED_PASSIVE_OBSERVATION':
        parser.error('preflight not accepted')
    args.output.mkdir(parents=True,exist_ok=False)
    ops=DeviceOps(args.output/'commands',args.module,packet)
    def interrupted(signum,frame):raise InterruptedError('signal '+str(signum))
    handlers={s:signal.signal(s,interrupted) for s in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT)}
    try:
        result=run_once(args.output/'observation',ops)
    finally:
        for sig,handler in handlers.items():signal.signal(sig,handler)
    print(result['verdict'],flush=True)
    raise SystemExit(0 if result['verdict'] in ('PASSIVE_OBSERVATION_REFUSED','PASSIVE_OBSERVATION_VALID') else 1)


if __name__=='__main__':main()
