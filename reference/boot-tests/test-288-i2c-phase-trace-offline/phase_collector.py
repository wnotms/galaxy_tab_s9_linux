"""Private-instance I2C observation only; no transfer/charger operations.

Pinned include/trace/events/i2c.h and i2c-core-base.c supply all fields.
Observe bus0 (the qualified 0-0063 device), including other addresses: result
has no address field, so address-only filtering would break transaction pairs.
The parser assigns only same-PID transfers wholly inside a matched worker.
"""
import re

from collector import Session as FrozenSession

I2C_EVENTS = ('i2c_write', 'i2c_read', 'i2c_reply', 'i2c_result')
FILTER = 'adapter_nr == 0'
PROFILE = 'Test288 passive bus0 transaction phases'
FIELDS = {
    'i2c_write': {'adapter_nr': (4, 1), 'msg_nr': (2, 0), 'addr': (2, 0),
                  'flags': (2, 0), 'len': (2, 0), 'buf': (4, 0)},
    'i2c_read': {'adapter_nr': (4, 1), 'msg_nr': (2, 0), 'addr': (2, 0),
                 'flags': (2, 0), 'len': (2, 0)},
    'i2c_reply': {'adapter_nr': (4, 1), 'msg_nr': (2, 0), 'addr': (2, 0),
                  'flags': (2, 0), 'len': (2, 0), 'buf': (4, 0)},
    'i2c_result': {'adapter_nr': (4, 1), 'nr_msgs': (2, 0), 'ret': (2, 1)},
}


def check_format(event, raw):
    for field, (size, signed) in FIELDS[event].items():
        declarations = re.findall(r'field:[^;]*\b' + field +
            r';\s*offset:\d+;\s*size:(\d+);\s*signed:(\d+);', raw)
        if len(declarations) != 1 or tuple(map(int, declarations[0])) != (size, signed):
            raise ValueError('unexpected I2C field: ' + event + '/' + field)


class Session(FrozenSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.i2c_owned = []
        self.meta.update(i2c_profile=PROFILE, i2c_adapter=0, i2c_address=0x63,
                         i2c_events=list(I2C_EVENTS), new_register_access=False)

    def setup(self, kallsyms, before_boot):
        super().setup(kallsyms, before_boot)
        # Parent has recording OFF, zero-hit probes and an empty private buffer.
        for event in I2C_EVENTS:
            base = self.instance + '/events/i2c/' + event
            check_format(event, self.read_save(event + '.format', base + '/format'))
            self.fs.write(base + '/filter', FILTER)
            if self.read_save(event + '.filter', base + '/filter').strip() != FILTER:
                raise ValueError('I2C adapter filter did not take effect')
            self.i2c_owned.append(event)  # Include an ambiguous failed enable.
            self.fs.write(base + '/enable', '1')
        enabled = self.read_save('enabled-events-i2c.txt', self.instance + '/set_event')
        expected = set((self.output / 'enabled-events.txt').read_text().split()) | {
            'i2c:' + event for event in I2C_EVENTS}
        if set(enabled.split()) != expected:
            raise ValueError('I2C enabled events mismatch')

    def disable_i2c(self):
        errors = []
        if self.created:
            for event in self.i2c_owned:
                try:
                    self.fs.write(self.instance + '/events/i2c/' + event + '/enable', '0')
                except Exception as exc:
                    errors.append(str(exc))
        return errors

    def snapshot(self, after_boot):
        errors = []
        try:
            self.fs.write(self.instance + '/tracing_on', '0')
        except Exception as exc:
            errors.append(str(exc))
        errors.extend(self.disable_i2c())
        # Preserve parent's raw capture even after an additional disable error.
        try:
            super().snapshot(after_boot)
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            raise ValueError('I2C snapshot incomplete: ' + '; '.join(errors))

    def cleanup(self):
        errors = self.disable_i2c() + super().cleanup()
        self.meta['cleanup_errors'] = errors
        return errors
