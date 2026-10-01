#!/usr/bin/env python3
"""Future device-side tracing ONLY; Test279 exercises this exclusively on mocks.

No observer/module/charger/ADB operations. Physical integration and baseline
checks belong to a separately registered test, not this utility.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import signal
import time
import uuid

WORK = ('workqueue_queue_work', 'workqueue_execute_start', 'workqueue_execute_end')
PROBES = {'request_enter': ('p', 'sm5440_passive_request_fresh'),
          'request_return': ('r16', 'sm5440_passive_request_fresh'),
          'poll_enter': ('p', 'sm5440_poll'), 'poll_return': ('r16', 'sm5440_poll')}


def boot_id(value):
    value = value.strip()
    if not re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
        raise ValueError('invalid boot ID')
    return value


def symbols(text):
    result = {}
    for name in {v[1] for v in PROBES.values()}:
        rows = re.findall(r'^([0-9a-f]+) [tT] ' + name + r'$', text, re.M)
        if len(rows) != 1 or int(rows[0], 16) == 0:
            raise ValueError('runtime symbol unavailable/ambiguous: ' + name)
        result[name] = rows[0]
    return result


def stats(raw):
    result = {}
    for line in raw.splitlines():
        key, value = line.split(':', 1)
        if key in result:
            raise ValueError('duplicate stats field')
        result[key] = value.strip()
    for key in ('entries', 'overrun', 'commit overrun', 'dropped events', 'read events'):
        if key not in result or not re.fullmatch(r'\d+', result[key]):
            raise ValueError('missing/invalid stats')
        result[key] = int(result[key])
    if any(result[k] for k in ('overrun', 'commit overrun', 'dropped events', 'read events')):
        raise ValueError('lost/consumed events')
    return result


def profile(raw, names):
    result = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 3 or not all(re.fullmatch(r'\d+', v) for v in fields[1:]):
            raise ValueError('malformed probe profile')
        if fields[0] in names.values():
            if fields[0] in result:
                raise ValueError('ambiguous probe profile')
            result[fields[0]] = (int(fields[1]), int(fields[2]))
    if set(result) != set(names.values()):
        raise ValueError('missing owned probe profile')
    if any(missed for _, missed in result.values()):
        raise ValueError('probe miss')
    return result


class TraceFS:
    """Narrow filesystem adapter; tests replace it with a kernel-like model."""
    def __init__(self, root):
        self.root = Path(root)

    def read(self, path):
        return (self.root / path).read_bytes()

    def write(self, path, value):
        # kprobe_events is a command interface; never truncate it to clear probes.
        mode = 'ab' if path == 'kprobe_events' else 'wb'
        with (self.root / path).open(mode) as stream:
            stream.write((value + '\n').encode())

    def mkdir(self, path):
        (self.root / path).mkdir()  # exclusive; never adopt an existing instance

    def rmdir(self, path):
        (self.root / path).rmdir()

    def list(self, path):
        return sorted(p.name for p in (self.root / path).iterdir())


class Session:
    def __init__(self, fs, output, token=None):
        self.fs, self.output = fs, Path(output)
        token = token or uuid.uuid4().hex[:12]
        if not re.fullmatch(r'[a-f0-9]{12}', token):
            raise ValueError('invalid ownership token')
        self.group = 'gts9t279_' + token
        self.instance = 'instances/' + self.group
        self.names = {kind: self.group + '_' + kind for kind in PROBES}
        self.created = False
        self.output_owned = False
        self.owned = []
        self.files = {}
        self.meta = {'group': self.group, 'probes': self.names, 'events': list(WORK),
                     'clock': 'boot', 'physical_acceptance': False}

    def save(self, name, raw):
        with (self.output / name).open('xb') as stream:
            stream.write(raw)
        self.files[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        return raw.decode()

    def read_save(self, name, path):
        return self.save(name, self.fs.read(path))

    def setup(self, kallsyms, before_boot):
        self.output.mkdir(parents=True, exist_ok=False)
        self.output_owned = True
        self.meta['boot_before'] = boot_id(before_boot)
        self.save('kallsyms.txt', kallsyms.encode())
        self.meta['symbols'] = symbols(kallsyms)
        self.save('ownership.json', (json.dumps({'instance': self.instance,
                  'group': self.group, 'probes': self.names}, sort_keys=True) + '\n').encode())
        self.read_save('global-probes-before.txt', 'kprobe_events')
        # Reject existing names even in another group: profile prints event only.
        current = self.fs.read('kprobe_events').decode()
        if self.group in current or any(n in current for n in self.names.values()):
            raise ValueError('probe ownership collision')
        self.fs.mkdir(self.instance)
        self.created = True
        def write(path, value):
            self.fs.write(self.instance + '/' + path, value)
        # New instances may default to recording on. Disable our owned buffer
        # immediately, before any event is enabled; never alter global state.
        self.read_save('initial-tracing-on.txt', self.instance + '/tracing_on')
        write('tracing_on', '0')
        clock = self.read_save('available-clocks.txt', self.instance + '/trace_clock')
        if 'boot' not in clock.replace('[', '').replace(']', '').split():
            raise ValueError('boot trace clock unavailable')
        write('trace_clock', 'boot')
        write('buffer_size_kb', '256')
        write('options/overwrite', '0')
        write('options/context-info', '1')
        write('options/latency-format', '0')
        write('options/record-tgid', '0')
        write('options/sym-offset', '0')
        write('options/sym-addr', '0')
        for option in ('raw', 'hex', 'bin', 'verbose', 'annotate'):
            write('options/' + option, '0')
        if self.fs.read(self.instance + '/set_event').strip():
            raise ValueError('new instance has inherited enabled events')
        for event in WORK:
            base = self.instance + '/events/workqueue/' + event
            fmt = self.read_save(event + '.format', base + '/format')
            if not re.search(r'field:[^;]*\bfunction;', fmt) or not re.search(r'field:[^;]*\bwork;', fmt):
                raise ValueError('unexpected workqueue format')
            self.fs.write(base + '/filter', 'function == 0x' + self.meta['symbols']['sm5440_poll'])
            filtered = self.read_save(event + '.filter', base + '/filter')
            match = re.fullmatch(r'\s*function == (0x[0-9a-f]+|\d+)\s*', filtered)
            if not match or int(match[1], 0) != int(self.meta['symbols']['sm5440_poll'], 16):
                raise ValueError('workqueue filter did not take effect')
            self.fs.write(base + '/enable', '1')
        for kind, (probe_type, symbol) in PROBES.items():
            name = self.names[kind]
            command = probe_type + ':' + self.group + '/' + name + ' ' + symbol
            if kind == 'request_return':
                command += ' ret=$retval:s32'
            # A failed command may have taken effect; cleanup must include it.
            self.owned.append(name)
            self.fs.write('kprobe_events', command)
            base = self.instance + '/events/' + self.group + '/' + name
            fmt = self.read_save(kind + '.format', base + '/format')
            if kind == 'request_return' and not re.search(r'field:s32 ret;[^\n]*signed:1;', fmt):
                raise ValueError('wrong signed return format')
            self.fs.write(base + '/enable', '1')
        self.read_save('clock.txt', self.instance + '/trace_clock')
        if '[boot]' not in (self.output / 'clock.txt').read_text():
            raise ValueError('boot clock selection failed')
        enabled = self.read_save('enabled-events.txt', self.instance + '/set_event')
        expected = {'workqueue:' + e for e in WORK} | {self.group + ':' + n for n in self.names.values()}
        if set(enabled.split()) != expected:
            raise ValueError('enabled events mismatch')
        self.read_save('options.txt', self.instance + '/trace_options')
        before = profile(self.read_save('profile-before.txt', 'kprobe_profile'), self.names)
        if any(hits for hits, _ in before.values()):
            raise ValueError('preexisting probe hits')
        self.stats('before')

    def stats(self, phase):
        cpus = self.fs.list(self.instance + '/per_cpu')
        if not cpus or any(not re.fullmatch(r'cpu\d+', c) for c in cpus):
            raise ValueError('invalid per-CPU trace inventory')
        prior = self.meta.setdefault('cpus', cpus)
        if cpus != prior:
            raise ValueError('CPU inventory changed')
        for cpu in cpus:
            raw = self.read_save(cpu + '-' + phase + '.stats', self.instance + '/per_cpu/' + cpu + '/stats')
            if phase == 'before' and stats(raw)['entries'] != 0:
                raise ValueError('new instance has preexisting entries')

    def start(self):
        self.fs.write(self.instance + '/tracing_on', '1')
        self.save('ready.txt', b'trace enabled; collector does not load the observer\n')

    def snapshot(self, after_boot):
        errors = []
        def attempt(func, *args):
            try:
                return func(*args)
            except Exception as exc:
                errors.append(str(exc))
        attempt(self.fs.write, self.instance + '/tracing_on', '0')
        # Stop probe hit accounting too; otherwise callbacks after recording is
        # stopped could inflate profile counts while evidence is copied.
        for name in self.owned:
            attempt(self.fs.write, self.instance + '/events/' + self.group + '/' + name + '/enable', '0')
        for event in WORK:
            attempt(self.fs.write, self.instance + '/events/workqueue/' + event + '/enable', '0')
        self.meta['boot_after'] = attempt(boot_id, after_boot)
        # Read counters before non-consuming static trace. Never use trace_pipe.
        attempt(self.stats, 'after')
        attempt(self.read_save, 'profile-after.txt', 'kprobe_profile')
        # A counter/profile failure must not discard the raw trace.
        attempt(self.read_save, 'trace.txt', self.instance + '/trace')
        attempt(self.read_save, 'global-probes-at-stop.txt', 'kprobe_events')
        if errors:
            raise ValueError('snapshot incomplete: ' + '; '.join(errors))

    def cleanup(self):
        errors = []
        def attempt(func, *args):
            try:
                func(*args)
            except Exception as exc:
                errors.append(str(exc))
        if self.created:
            attempt(self.fs.write, self.instance + '/tracing_on', '0')
            for name in self.owned:
                attempt(self.fs.write, self.instance + '/events/' + self.group + '/' + name + '/enable', '0')
            for event in WORK:
                attempt(self.fs.write, self.instance + '/events/workqueue/' + event + '/enable', '0')
            attempt(self.fs.rmdir, self.instance)
        for name in reversed(self.owned):
            attempt(self.fs.write, 'kprobe_events', '-:' + self.group + '/' + name)
        if self.output_owned:
            try:
                remaining = self.read_save('global-probes-after.txt', 'kprobe_events')
                if any('/' + n in remaining for n in self.owned):
                    errors.append('owned probes remain')
            except Exception as exc:
                errors.append(str(exc))
        self.meta['cleanup_errors'] = errors
        return errors

    def finish(self, error=None):
        if not self.output_owned:
            raise ValueError('output not owned')
        cleanup = self.cleanup()
        self.meta.update(files=self.files, collection_error=error,
                         collection_complete=error is None and not cleanup)
        with (self.output / 'manifest.json').open('x') as stream:
            json.dump(self.meta, stream, indent=2, sort_keys=True)
            stream.write('\n')


def record(session, kallsyms, read_boot, maximum_seconds=35,
           elapsed=time.monotonic, pause=time.sleep):
    """Injectable orchestration; no observer action, even after timeout/error."""
    if not 1 <= maximum_seconds <= 35:
        raise ValueError('collection deadline must be 1..35s')
    error = None
    try:
        session.setup(kallsyms, read_boot())
        session.start()
        deadline = elapsed() + maximum_seconds
        while not (session.output / 'STOP').exists():
            if elapsed() >= deadline:
                raise TimeoutError('collector deadline expired; observer state unknown')
            pause(.05)
        if (session.output / 'STOP').read_text().strip() != 'observer-terminal':
            raise ValueError('invalid stop marker')
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    finally:
        try:
            if session.created:
                session.snapshot(read_boot())
        except Exception as exc:
            error = (error or '') + '; snapshot: ' + str(exc)
        if session.output_owned:
            session.finish(error)
    return error is None and not session.meta.get('cleanup_errors')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-tracefs', action='store_true', required=True)
    parser.add_argument('--tracefs', type=Path, default=Path('/sys/kernel/tracing'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=float, default=35)
    args = parser.parse_args()
    if not 1 <= args.maximum_seconds <= 35:
        parser.error('collection deadline must be 1..35s')
    if args.output.exists():
        parser.error('output already exists; never retry in this namespace')
    session = Session(TraceFS(args.tracefs), args.output)
    def interrupted(signum, frame):
        raise InterruptedError('signal ' + str(signum))
    handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
    try:
        ok = record(session, Path('/proc/kallsyms').read_text(),
                    lambda: Path('/proc/sys/kernel/random/boot_id').read_text(), args.maximum_seconds)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
