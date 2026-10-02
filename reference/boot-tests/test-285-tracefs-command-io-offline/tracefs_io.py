"""Non-seeking command writes for Linux tracefs; offline qualified adapter.

kprobe_events uses seq_lseek: SEEK_END fails EINVAL. Python append-open seeks
to the end during FileIO construction. O_TRUNC would remove unrelated probes.
Use an existing descriptor with neither flag, one write, no seek/no retry.
The unchanged Test279 Session still owns/cleans its unique probe names.
"""
import errno
import os

from collector import TraceFS as FrozenTraceFS


class TraceFS(FrozenTraceFS):
    def write(self, path, value):
        if path != 'kprobe_events':
            return super().write(path, value)
        if not isinstance(value, str) or not value or any(c in value for c in '\n\r\0'):
            raise ValueError('one nonempty trace command required')
        payload = (value + '\n').encode()
        if len(payload) > 4094:
            raise ValueError('trace command exceeds bounded kernel line size')
        try:
            descriptor = os.open(self.root / path, os.O_WRONLY | os.O_CLOEXEC)
        except OSError as exc:
            raise OSError(exc.errno, 'command open failed before write: ' + str(exc)) from exc
        try:
            try:
                written = os.write(descriptor, payload)
            except OSError as exc:
                raise OSError(exc.errno, 'command write failed; no retry: ' + str(exc)) from exc
            if written != len(payload):
                raise OSError(errno.EIO, f'short command write {written}/{len(payload)}; no retry')
        finally:
            os.close(descriptor)
