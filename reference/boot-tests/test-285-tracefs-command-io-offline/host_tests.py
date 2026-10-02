#!/usr/bin/env python3
"""Mock syscall tests plus real HOST seq_file open regression; no device access."""
import errno
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

A = Path(__file__).resolve().parent
sys.path.insert(0, str(A.parent/'test-279-fresh-trace-collector-offline'))
import collector
import tracefs_io


class CommandIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fs = tracefs_io.TraceFS(self.root)

    def test_one_write_no_append_truncate_create_or_seek(self):
        payload = b'p:owned/probe sm5440_poll\n'
        with patch.object(tracefs_io.os, 'open', return_value=7) as opened, \
             patch.object(tracefs_io.os, 'write', return_value=len(payload)) as written, \
             patch.object(tracefs_io.os, 'close') as closed, \
             patch.object(tracefs_io.os, 'lseek', side_effect=AssertionError('seek forbidden')):
            self.fs.write('kprobe_events', payload.decode().strip())
        opened.assert_called_once_with(self.root/'kprobe_events', os.O_WRONLY|os.O_CLOEXEC)
        self.assertFalse(opened.call_args.args[1] & (os.O_APPEND|os.O_TRUNC|os.O_CREAT))
        written.assert_called_once_with(7, payload); closed.assert_called_once_with(7)

    def test_deletion_is_one_owned_command_not_global_clear(self):
        payload=b'-:owned/probe\n'
        with patch.object(tracefs_io.os,'open',return_value=7), \
             patch.object(tracefs_io.os,'write',return_value=len(payload)) as written, \
             patch.object(tracefs_io.os,'close'):
            self.fs.write('kprobe_events','-:owned/probe')
        written.assert_called_once_with(7,payload)

    def test_open_einval_names_stage_and_never_writes(self):
        with patch.object(tracefs_io.os,'open',side_effect=OSError(errno.EINVAL,'seq_file')) as opened, \
             patch.object(tracefs_io.os,'write') as written, patch.object(tracefs_io.os,'close') as closed:
            with self.assertRaisesRegex(OSError,'open failed before write'):
                self.fs.write('kprobe_events','p:owned/probe sm5440_poll')
        self.assertEqual(opened.call_count,1); written.assert_not_called();closed.assert_not_called()

    def test_write_einval_names_stage_closes_no_retry(self):
        with patch.object(tracefs_io.os,'open',return_value=7), \
             patch.object(tracefs_io.os,'write',side_effect=OSError(errno.EINVAL,'rejected')) as written, \
             patch.object(tracefs_io.os,'close') as closed:
            with self.assertRaisesRegex(OSError,'write failed; no retry') as error:
                self.fs.write('kprobe_events','p:owned/probe sm5440_poll')
            self.assertEqual(error.exception.errno,errno.EINVAL)
        self.assertEqual(written.call_count,1);closed.assert_called_once_with(7)

    def test_short_write_closes_no_suffix_retry(self):
        for count in [0,1]:
            with self.subTest(count=count), patch.object(tracefs_io.os,'open',return_value=7), \
                 patch.object(tracefs_io.os,'write',return_value=count) as written, \
                 patch.object(tracefs_io.os,'close') as closed:
                with self.assertRaisesRegex(OSError,'short command write'):
                    self.fs.write('kprobe_events','p:owned/probe sm5440_poll')
                self.assertEqual(written.call_count,1);closed.assert_called_once_with(7)

    def test_unknown_open_write_errors_stop(self):
        for error in [errno.EACCES,errno.ENOENT,errno.EIO]:
            with self.subTest(error=error), patch.object(tracefs_io.os,'open',side_effect=OSError(error,'failure')):
                with self.assertRaises(OSError) as result:
                    self.fs.write('kprobe_events','p:owned/probe sm5440_poll')
                self.assertEqual(result.exception.errno,error)

    def test_multi_empty_nul_and_oversized_commands_rejected_before_open(self):
        for value in ['', 'p:x/y f\n-:other/z','p:x/y f\r','p:x/y f\0', 'x'*4094, None]:
            with self.subTest(value=str(value)[:30]), patch.object(tracefs_io.os,'open') as opened:
                with self.assertRaises(ValueError):self.fs.write('kprobe_events',value)
                opened.assert_not_called()

    def test_private_control_write_behavior_unchanged(self):
        control=self.root/'instances/owned/tracing_on';control.parent.mkdir(parents=True)
        control.write_text('1\n')
        self.fs.write('instances/owned/tracing_on','0')
        self.assertEqual(control.read_bytes(),b'0\n')

    def test_other_adapter_methods_and_session_not_reimplemented(self):
        for method in ['read','mkdir','rmdir','list']:
            self.assertIs(getattr(tracefs_io.TraceFS,method),getattr(collector.TraceFS,method))
        self.assertEqual({n for n in tracefs_io.TraceFS.__dict__ if not n.startswith('__')}, {'write'})

    def test_interruption_closes_descriptor_without_retry(self):
        with patch.object(tracefs_io.os,'open',return_value=7), \
             patch.object(tracefs_io.os,'write',side_effect=KeyboardInterrupt) as written, \
             patch.object(tracefs_io.os,'close') as closed:
            with self.assertRaises(KeyboardInterrupt):
                self.fs.write('kprobe_events','p:owned/probe sm5440_poll')
        self.assertEqual(written.call_count,1);closed.assert_called_once_with(7)

    def test_real_host_seq_file_append_failure_before_write(self):
        # This targets this process's HOST proc entry. No write method is ever
        # reached; no tracing, device command, scheduler reset or probe occurs.
        (self.root/'kprobe_events').symlink_to('/proc/self/sched')
        with self.assertRaises(OSError) as result:
            collector.TraceFS(self.root).write('kprobe_events','p:owned/probe sm5440_poll')
        self.assertEqual(result.exception.errno,errno.EINVAL)

    def test_new_open_on_same_host_seq_file_succeeds_zero_actual_writes(self):
        (self.root/'kprobe_events').symlink_to('/proc/self/sched')
        command='p:owned/probe sm5440_poll'
        # Actual nonseeking open/close, mocked write, no host kernel mutation.
        with patch.object(tracefs_io.os,'write',return_value=len(command)+1) as written, \
             patch.object(tracefs_io.os,'lseek',side_effect=AssertionError('seek forbidden')):
            self.fs.write('kprobe_events',command)
        self.assertEqual(written.call_count,1)


if __name__=='__main__':unittest.main(verbosity=2)
