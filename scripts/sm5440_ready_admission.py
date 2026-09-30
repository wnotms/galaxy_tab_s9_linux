#!/usr/bin/env python3
"""Explicit Test260 transport adapter; unchanged ADB-first hardware admission."""
import os
from pathlib import Path

import gts9_ncm_ready as n
import production_reboot_stability as p


class ReadyRecorder(p.Recorder):
    """Use the new registered readiness budget, never retry authentication."""
    def __init__(self, folder):
        super().__init__(folder)
        self.ready = None

    def ps(self, name, script, timeout=20, required=True):
        if name == 'windows-topology':
            self.ready = n.wait_ready(self, 30)
            source = f"readiness-{self.ready['samples']:02d}-windows.txt"
            p.write_json(self.folder / 'windows-topology-source.json',
                         {'raw_source': source, 'ready': self.ready})
            return (self.folder / source).read_text().replace('\r', ''), 0
        return super().ps(name, script, timeout, required)

    def ssh(self, name, script, timeout=15, required=True):
        if self.ready is None:
            raise p.CaptureError('no verified NCM path; SSH refused')
        argv = ['ssh', '-F', '/dev/null', '-4', '-T', '-b', self.ready['source_ipv4'],
                '-i', os.environ.get('GTS9_SSH_KEY', str(Path.home() / '.ssh/gts9_ed25519')),
                '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                '-o', 'ConnectionAttempts=1', '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'LogLevel=ERROR', 'root@' + n.TARGET, script]
        return self.command(name, argv, timeout, required)
