"""Compile the pinned real codec, compare to independent Qualcomm wire vectors."""
import ctypes as C
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ssc-rpc-wire'
PROFILE = ROOT / 'userspace/sensors/diagnostics/rpc-wire.json'
PATCH = ROOT / 'userspace/sensors/diagnostics/rpc-wire.patch'


class Buffer(C.Structure):
    _fields_ = [('s', C.c_uint32), ('p', C.c_void_p)]


def wire(payloads):
    # Qualcomm pack_in_bufs/pack_out_bufs: align only non-empty payloads.
    result = bytearray()
    for data in payloads:
        result += struct.pack('<I', len(data))
        if data:
            result += bytes((-len(result)) % 8)
            result += data
    return bytes(result)


class WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        profile = json.loads(PROFILE.read_text())
        for name, sha in profile['fixtures'].items():
            if hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() != sha:
                raise ValueError('pinned fixture mismatch: ' + name)
        import shutil
        shutil.copytree(FIXTURE, cls.root / 'src')
        if hashlib.sha256(PATCH.read_bytes()).hexdigest() != profile['patch_sha256']:
            raise ValueError('wire patch mismatch')
        cls.old = cls.compile(FIXTURE, cls.root / 'old.so')
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PATCH)],
                       cwd=cls.root / 'src', check=True, capture_output=True)
        changed = [name for name in profile['fixtures'] if
                   (cls.root / 'src' / name).read_bytes() != (FIXTURE / name).read_bytes()]
        if changed != profile['changed_files']:
            raise ValueError('unexpected source changes')
        if hashlib.sha256((cls.root / 'src/hexagonrpcd/iobuffer.c').read_bytes()).hexdigest() != profile['patched_file_sha256']:
            raise ValueError('patched codec mismatch')
        cls.new = cls.compile(cls.root / 'src', cls.root / 'new.so')

    @staticmethod
    def compile(tree, output):
        subprocess.run(['cc', '-shared', '-fPIC', '-std=gnu11', '-Wall', '-Wextra',
                        '-Werror', '-I', str(tree / 'include'),
                        str(tree / 'hexagonrpcd/iobuffer.c'), '-o', str(output)],
                       check=True, capture_output=True)
        lib = C.CDLL(str(output))
        lib.outbufs_calculate_size.argtypes = [C.c_size_t, C.POINTER(Buffer)]
        lib.outbufs_calculate_size.restype = C.c_size_t
        lib.outbufs_encode.argtypes = [C.c_size_t, C.POINTER(Buffer), C.c_void_p]
        lib.inbuf_decode_start.argtypes = [C.c_uint32]
        lib.inbuf_decode_start.restype = C.c_void_p
        lib.inbuf_decode.argtypes = [C.c_void_p, C.c_size_t, C.c_void_p]
        lib.inbuf_decode_is_complete.argtypes = [C.c_void_p]
        lib.inbuf_decode_finish.argtypes = [C.c_void_p]
        lib.inbuf_decode_finish.restype = C.POINTER(Buffer)
        lib.iobuf_free.argtypes = [C.c_size_t, C.POINTER(Buffer)]
        return lib

    def check_round(self, payloads, fragmented=False):
        blocks = [C.create_string_buffer(data) for data in payloads]
        bufs = (Buffer * len(blocks))(*(Buffer(len(data), C.cast(block, C.c_void_p))
                                      for block, data in zip(blocks, payloads)))
        expected = wire(payloads)
        size = self.new.outbufs_calculate_size(len(bufs), bufs)
        self.assertEqual(size, len(expected))
        output = C.create_string_buffer(size)
        self.new.outbufs_encode(len(bufs), bufs, output)
        self.assertEqual(output.raw, expected)
        ctx = self.new.inbuf_decode_start(len(payloads) << 16)
        self.assertTrue(ctx)
        pieces = [expected[i:i+1] for i in range(len(expected))] if fragmented else [expected]
        for piece in pieces:
            self.assertEqual(self.new.inbuf_decode(ctx, len(piece), piece), 0)
        complete = self.new.inbuf_decode_is_complete(ctx)
        decoded = self.new.inbuf_decode_finish(ctx)
        self.assertTrue(complete)
        try:
            self.assertEqual([C.string_at(decoded[i].p, decoded[i].s) for i in range(len(payloads))], payloads)
            for i, data in enumerate(payloads):
                if not data:
                    self.assertIsNone(decoded[i].p)
        finally:
            self.new.iobuf_free(len(payloads), decoded)

    def test_zero_only(self):
        self.check_round([b''])

    def test_consecutive_zero(self):
        self.check_round([b'', b'', b''])

    def test_leading_zero(self):
        self.check_round([b'', b'abc'])

    def test_trailing_zero(self):
        self.check_round([b'abc', b''])

    def test_middle_zero_and_unaligned_header(self):
        self.check_round([b'a', b'', b'xyz', b''])

    def test_fragmented_headers(self):
        self.check_round([b'', b'abc', b'', b'defgh', b''], fragmented=True)

    def test_existing_nonempty_format(self):
        self.check_round([bytes(range(i)) for i in range(1, 10)], fragmented=True)

    def test_registry_read_sized_payload(self):
        self.check_round([struct.pack('<II', 512, 0), bytes(range(256))*2])

    def test_zero_buffer_count(self):
        self.check_round([])

    def test_original_length_bug_reproduced(self):
        bufs = (Buffer * 1)(Buffer(0, None))
        self.assertEqual(self.old.outbufs_calculate_size(1, bufs), 8)
        self.assertEqual(len(wire([b''])), 4)

    def test_original_decoder_bug_reproduced(self):
        ctx = self.old.inbuf_decode_start(1 << 16)
        self.assertEqual(self.old.inbuf_decode(ctx, 4, b'\0'*4), 0)
        self.assertFalse(self.old.inbuf_decode_is_complete(ctx))
        # This fixture initialized slot0 before losing it; free that one slot.
        self.old.iobuf_free(1, self.old.inbuf_decode_finish(ctx))

    def test_sanitized_unaligned_header(self):
        source = self.root / 'unaligned.c'
        source.write_text('#include "iobuffer.h"\nint main(void) { char p=1, out[32]; '
                          'struct fastrpc_io_buffer b[3]={{1,&p},{0,0},{1,&p}}; '
                          'outbufs_encode(3,b,out); return 0; }\n')
        command = ['cc', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                   '-I', str(self.root / 'src/include'), '-I', str(self.root / 'src/hexagonrpcd'),
                   str(source), str(self.root / 'src/hexagonrpcd/iobuffer.c'),
                   '-o', str(self.root / 'unaligned')]
        subprocess.run(command, check=True, capture_output=True)
        subprocess.run([str(self.root / 'unaligned')], check=True, capture_output=True)

    def test_portable_golden_vector_sanitized(self):
        output = self.root / 'golden'
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                        '-fno-sanitize-recover=all', '-I', str(self.root / 'src/include'),
                        '-I', str(self.root / 'src/hexagonrpcd'), str(FIXTURE / 'wire-cases.c'),
                        str(self.root / 'src/hexagonrpcd/iobuffer.c'), '-o', str(output)],
                       check=True, capture_output=True)
        subprocess.run([str(output)], check=True, capture_output=True)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        import shutil
        spec = importlib.util.spec_from_file_location('wire_profile', ROOT / 'userspace/sensors/rpc_wire_profile.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.recipe = self.root / 'recipe'
        (self.recipe / 'diagnostics').mkdir(parents=True)
        self.tree = self.root / 'inputs'
        profile = json.loads(PROFILE.read_text())
        for name in profile['fixtures']:
            target = self.tree / 'hexagonrpc' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FIXTURE / name, target)
        manifest = dict(fedora_commit='fixture-pin', sources=[dict(name='hexagonrpc',
                        version='0.4.0', sha256='fixture-archive', patches=[])])
        catalog = json.dumps(manifest).encode()
        (self.recipe / 'sources.json').write_bytes(catalog)
        profile['base_manifest_sha256'] = hashlib.sha256(catalog).hexdigest()
        (self.recipe / 'diagnostics/rpc-wire.json').write_text(json.dumps(profile))
        shutil.copyfile(PATCH, self.recipe / 'diagnostics/rpc-wire.patch')
        report = dict(fedora_commit='fixture-pin', sources=[dict(name='hexagonrpc',
                      version='0.4.0', archive_sha256='fixture-archive', patches=[],
                      patched_files=profile['fixtures'])])
        (self.tree / 'PREPARED.json').write_text(json.dumps(report))
        self.output = self.root / 'candidate'
        # The real verifier and patch transaction run; only their fixture roots differ.
        for owner in [self.module, self.module.build]:
            replacement = patch.object(owner, 'BASE', self.recipe)
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_exact_source_change_without_input_mutation(self):
        before = self.module.files(self.tree)
        result = self.module.prepare(self.tree, self.output)
        self.assertFalse(result['device_operations'])
        self.assertEqual(self.module.files(self.tree), before)
        self.assertEqual(result['profile']['changed_files'], ['hexagonrpcd/iobuffer.c'])

    def test_corrupt_source_refused_before_output(self):
        (self.tree / 'hexagonrpc/hexagonrpcd/iobuffer.c').write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.module.prepare(self.tree, self.output)
        self.assertFalse(self.output.exists())

    def test_corrupt_patch_refused(self):
        (self.recipe / 'diagnostics/rpc-wire.patch').write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'input hash mismatch'):
            self.module.prepare(self.tree, self.output)
        self.assertFalse(self.output.exists())

    def test_source_link_refused(self):
        path = self.tree / 'hexagonrpc/hexagonrpcd/iobuffer.c'
        path.unlink()
        path.symlink_to(FIXTURE / 'hexagonrpcd/iobuffer.c')
        with self.assertRaisesRegex(ValueError, 'links'):
            self.module.prepare(self.tree, self.output)

    def test_existing_output_refused(self):
        self.output.mkdir()
        (self.output / 'keep').write_text('unchanged')
        with self.assertRaisesRegex(ValueError, 'output must be absent'):
            self.module.prepare(self.tree, self.output)
        self.assertEqual((self.output / 'keep').read_text(), 'unchanged')

    def test_output_inside_base_refused(self):
        with self.assertRaisesRegex(ValueError, 'outside base sources'):
            self.module.prepare(self.tree, self.tree / 'candidate')


if __name__ == '__main__':
    unittest.main()
