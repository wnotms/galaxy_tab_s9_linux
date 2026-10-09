#!/usr/bin/env python3
"""Complete already required Test382 rollback; never install/retry a candidate.

The original boots-after/before10s failures stay STOP. Device-verified systemd
257 journalctl -n5 limits boot listing; attribution still requires oldboot and
exactly one following newboot. A missing oldboot or extra boot is never passed.
All partition/module/owned-file safety checks are the frozen registered runner.
"""
import importlib.util
import json
from pathlib import Path


def bounded_script(script):
    if script == 'journalctl --list-boots --no-pager':
        return 'timeout 8 journalctl --list-boots -n 5 --no-pager'
    return script


def main():
    folder = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('recovery382', folder/'host_flow.py')
    h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
    state = h.read(folder/'mutation-state.json')
    if not state['rollback_required'] or not (folder/'first-failure.json').is_file():
        raise ValueError('only existing stopped candidate rollback')
    base = h.p.Recorder
    class Recorder(base):
        def adb(self, name, script, timeout=20, required=True):
            changed=bounded_script(script)
            if changed != script: name += '-bounded-recovery'
            return super().adb(name, changed, timeout=timeout, required=required)
    h.p.Recorder = Recorder
    result = h.restore()
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
