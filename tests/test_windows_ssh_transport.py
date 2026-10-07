"""Host-only transport path; identity remains in local OpenSSH."""
from pathlib import Path
import shlex
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import windows_ssh_transport as t


class WindowsSSHTransportTests(unittest.TestCase):
    def test_direct_preserves_private_key_trust_alias_and_remote_command(self):
        a=t.ssh_argv('/private/key','/private/trust','accepted','10.1.2.3','cat /proc/uptime')
        self.assertEqual(a[-2:],['root@10.1.2.3','cat /proc/uptime'])
        self.assertIn('StrictHostKeyChecking=yes',a)
        self.assertIn('UserKnownHostsFile=/private/trust',a)
        self.assertIn('HostKeyAlias=accepted',a)
        self.assertFalse(any(x.startswith('ProxyCommand=') for x in a))

    def test_proxy_receives_only_public_code_and_numeric_endpoint(self):
        with patch.object(t.Path,'is_file',return_value=True):
            a=t.ssh_argv('/private/key','/private/trust','accepted','10.1.2.3','id',transport='windows-tcp',windows_python='/path with spaces/python.exe')
        command=next(x.removeprefix('ProxyCommand=') for x in a if x.startswith('ProxyCommand='))
        proxy=shlex.split(command)
        self.assertEqual(proxy,['/path with spaces/python.exe','-u','-c',t.PROXY,'10.1.2.3'])
        self.assertNotIn('/private/key',command);self.assertNotIn('/private/trust',command)
        self.assertNotIn('id',proxy)
        self.assertIn('StrictHostKeyChecking=yes',a)

    def test_missing_python_or_unknown_profile_never_falls_back_to_untrusted_ssh(self):
        with patch.object(t.Path,'is_file',return_value=False),self.assertRaises(ValueError):
            t.ssh_argv('key','trust','alias','10.1.2.3','id',transport='windows-tcp')
        with self.assertRaises(ValueError):t.ssh_argv('key','trust','alias','10.1.2.3','id',transport='other')

    def test_invalid_or_public_address_rejected_before_process_creation(self):
        for address in ('example.com','10.1.2.3;id','8.8.8.8','127.0.0.1','::1'):
            with self.subTest(address=address),self.assertRaises(ValueError):
                t.ssh_argv('key','trust','alias',address,'id')

    def test_binary_relay_preserves_bytes_across_timeout_partial_writes_and_eof(self):
        import os,threading,types
        payload=[TimeoutError(),b'SSH-2.0\r\n',b'\x00\n\xff',b'']
        sent=bytearray();modes=[];connected=[];closed=[]
        class Sock:
            def settimeout(self,n):self.timeout=n
            def recv(self,n):
                x=payload.pop(0)
                if isinstance(x,Exception):raise x
                return x
            def close(self):closed.append(True)
        sock=Sock()
        def connect(endpoint,timeout):connected.append((endpoint,timeout));return sock
        def write(fd,data):
            self.assertEqual(fd,1);count=min(2,len(data));sent.extend(data[:count]);return count
        class Thread:
            def __init__(self,target,daemon):self.target=target;self.daemon=daemon
            def start(self):pass  # exercise the receiving pipe independently
        fake_os=types.SimpleNamespace(O_BINARY=32768,write=write)
        fake_socket=types.SimpleNamespace(create_connection=connect,timeout=TimeoutError)
        fake_msvcrt=types.SimpleNamespace(setmode=lambda fd,mode:modes.append((fd,mode)))
        fake_threads=types.SimpleNamespace(Event=threading.Event,Thread=Thread)
        with patch.dict(sys.modules,dict(os=fake_os,socket=fake_socket,msvcrt=fake_msvcrt,threading=fake_threads)),patch.object(sys,'platform','win32'),patch.object(sys,'argv',['proxy','10.1.2.3']):
            exec(t.PROXY,{})
        self.assertEqual(sent,b'SSH-2.0\r\n\x00\n\xff')
        self.assertEqual(modes,[(0,32768),(1,32768)])
        self.assertEqual(connected,[(('10.1.2.3',22),3)])
        self.assertEqual(closed,[True])


if __name__=='__main__':unittest.main()
