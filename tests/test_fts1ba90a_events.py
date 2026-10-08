"""Run the imported driver's actual C decoders with input-event capture stubs."""
import ctypes
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'kernel/desktop/fts1ba90a'


def function(source, name):
    start = source.index('static ', source.index(name) - 20)
    body = source.index('{', start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class TouchEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        source = (DRIVER / 'fts1ba90a.c').read_text()
        defines = '\n'.join(re.findall(r'^#define FTS_.*$', source, re.MULTILINE))
        prelude = r'''
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
#define BIT(n) (1U << (n))
#define MT_TOOL_FINGER 0
#define ABS_MT_PRESSURE 6
#define ABS_MT_TOUCH_MAJOR 7
#define ABS_MT_TOUCH_MINOR 8
struct input_dev { int unused; };
struct touchscreen_properties { int unused; };
struct fts1ba90a { struct input_dev *input; struct touchscreen_properties prop; };
static unsigned int events[10];
static void input_mt_slot(struct input_dev *d, unsigned int slot) { events[0]++; events[1]=slot; }
static void input_mt_report_slot_inactive(struct input_dev *d) { events[2]++; }
static void input_mt_report_slot_state(struct input_dev *d, int tool, bool active) { events[3]+=active; }
static void touchscreen_report_pos(struct input_dev *d, struct touchscreen_properties *p,
                                    unsigned int x, unsigned int y, bool mt) {
    events[4]=x; events[5]=y; events[9]++;
}
static void input_report_abs(struct input_dev *d, int code, unsigned int value) { events[code]=value; }
'''
        wrappers = r'''
void decode(const u8 *data, unsigned int *result) {
    struct input_dev input = {0}; struct fts1ba90a ts = { .input=&input };
    memset(events, 0, sizeof(events));
    fts1ba90a_report_touch(&ts, data); memcpy(result, events, sizeof(events));
}
int double_tap(const u8 *data) { return fts1ba90a_is_double_tap(data); }
'''
        unit = folder / 'events.c'
        unit.write_text(prelude + defines + '\n' + function(source, 'fts1ba90a_is_double_tap') +
                        '\n' + function(source, 'fts1ba90a_report_touch') + wrappers)
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', str(unit), '-o', str(folder / 'events.so')],
                       check=True, capture_output=True, text=True)
        cls.lib = ctypes.CDLL(str(folder / 'events.so'))
        cls.lib.decode.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_uint)]
        cls.lib.decode.restype = None
        cls.lib.double_tap.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        cls.lib.double_tap.restype = ctypes.c_int

    def frame(self, slot=0, action=1, ttype=0, x=0, y=0, pressure=0):
        data = bytearray(16)
        data[0] = (action << 6) | (slot << 2)
        data[1:4] = bytes((x >> 4, y >> 4, ((x & 15) << 4) | (y & 15)))
        data[4:8] = bytes((12, 8, ((ttype >> 2) << 6) | pressure, (ttype & 3) << 6))
        return data

    def decode(self, data):
        out = (ctypes.c_uint * 10)()
        self.lib.decode((ctypes.c_ubyte * 16).from_buffer_copy(data), out)
        return list(out)

    def test_import_is_byte_identical_to_pinned_same_model_source(self):
        manifest = json.loads((DRIVER / 'SOURCE.json').read_text())
        for name, row in manifest['files'].items():
            self.assertEqual(hashlib.sha256((DRIVER / name).read_bytes()).hexdigest(), row['sha256'])

    def test_press_and_move_decode_last_slot_and_coordinates(self):
        for action in (1, 2):
            result = self.decode(self.frame(slot=9, action=action, x=1599, y=2559, pressure=63))
            self.assertEqual(result, [1, 9, 0, 1, 1599, 2559, 63, 12, 8, 1])

    def test_zero_pressure_is_reported_as_one(self):
        self.assertEqual(self.decode(self.frame())[6], 1)

    def test_release_reports_inactive_without_coordinates(self):
        self.assertEqual(self.decode(self.frame(slot=2, action=3)), [1, 2, 1, 0, 0, 0, 0, 0, 0, 0])

    def test_invalid_slot_and_non_coordinate_are_ignored(self):
        self.assertEqual(self.decode(self.frame(slot=10)), [0] * 10)
        frame = self.frame(); frame[0] |= 1
        self.assertEqual(self.decode(frame), [0] * 10)

    def test_palm_releases_slot_without_reporting_finger(self):
        self.assertEqual(self.decode(self.frame(slot=4, ttype=5)), [1, 4, 1, 0, 0, 0, 0, 0, 0, 0])

    def test_glove_and_wet_report_but_unsupported_type_does_not(self):
        for ttype in (3, 6):
            self.assertEqual(self.decode(self.frame(ttype=ttype))[3], 1)
        self.assertEqual(self.decode(self.frame(ttype=7)), [0] * 10)

    def test_only_exact_double_tap_wake_gesture_matches(self):
        frame = bytearray(16); frame[0] = (1 << 6) | (1 << 2) | 2; frame[1] = 1
        self.assertEqual(self.lib.double_tap((ctypes.c_ubyte * 16).from_buffer_copy(frame)), 1)
        for index, mask in ((0, 1), (0, 4), (0, 64), (1, 1)):
            changed = frame.copy(); changed[index] ^= mask
            self.assertEqual(self.lib.double_tap((ctypes.c_ubyte * 16).from_buffer_copy(changed)), 0)
