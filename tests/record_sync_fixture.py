"""Real syncfs for host boot-record fixtures, without flushing unrelated mounts.

Only subprocesses given this environment see the wrapper. Device scripts still
use their original global sync, and both record persistence barriers execute.
"""
import os
from pathlib import Path
import shlex
import shutil


def record_sync_env(directory, env=None):
    directory = Path(directory).resolve(strict=True)
    real_sync = shutil.which('sync', path=os.defpath)
    if not real_sync:
        raise RuntimeError('real host sync is required')
    bin_dir = directory / '.host-record-sync'
    bin_dir.mkdir(exist_ok=True)
    wrapper = bin_dir / 'sync'
    wrapper.write_text(
        '#!/bin/sh\n'
        '# Fixture calls must remain the original argument-free barriers.\n'
        '[ "$#" -eq 0 ] || exit 2\n'
        f'exec {shlex.quote(real_sync)} -f {shlex.quote(str(directory))}\n')
    wrapper.chmod(0o755)
    result = dict(os.environ if env is None else env)
    result['PATH'] = str(bin_dir) + os.pathsep + result.get('PATH', os.defpath)
    return result
