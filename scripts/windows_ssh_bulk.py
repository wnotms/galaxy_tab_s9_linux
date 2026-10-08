"""Bulk-only native Windows TCP proxy; existing charging transport is frozen.

Local OpenSSH still owns keys and host trust. No key/file is staged on Windows.
Nonblocking writes track their exact offset, including after would-block; the
30-second deadline measures lack of progress, not total transfer duration.
"""
import inspect
import select
import shlex
import time

from windows_ssh_transport import WINDOWS_PYTHON, ssh_argv


def send_pending(sock, data, stop, stall_seconds=30):
    pos = 0
    deadline = time.monotonic() + stall_seconds
    while pos < len(data):
        if stop.is_set():
            raise ConnectionAbortedError('proxy stopped during upload')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('bulk proxy upload made no progress')
        _, writable, _ = select.select([], [sock], [], min(1, remaining))
        if not writable:
            continue
        try:
            n = sock.send(memoryview(data)[pos:])
        except (BlockingIOError, InterruptedError):
            continue
        if n <= 0:
            raise ConnectionError('bulk proxy socket closed during upload')
        pos += n
        deadline = time.monotonic() + stall_seconds


PROXY = 'import socket,os,sys,threading,msvcrt,select,time\n' + inspect.getsource(send_pending) + r'''
if sys.platform != "win32": raise RuntimeError("native Windows TCP required")
msvcrt.setmode(0,os.O_BINARY);msvcrt.setmode(1,os.O_BINARY)
s=socket.create_connection((sys.argv[1],22),3)
s.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,65536)
s.setblocking(False)
stop=threading.Event()
errors=[]
def upload():
 try:
  while not stop.is_set():
   data=os.read(0,65536)
   if not data:
    s.shutdown(socket.SHUT_WR)
    return
   send_pending(s,data,stop)
 except BaseException as exc:
  errors.append(exc);stop.set()
threading.Thread(target=upload,daemon=True).start()
try:
 while not stop.is_set():
  readable,_,_=select.select([s],[],[],1)
  if not readable:continue
  try:data=s.recv(65536)
  except (BlockingIOError,InterruptedError):continue
  if not data:break
  pos=0
  while pos<len(data):
   n=os.write(1,data[pos:])
   if n<=0:raise OSError("proxy stdout closed")
   pos+=n
 if errors:raise errors[0]
finally:stop.set();s.close()
'''


def bulk_ssh_argv(key, known_hosts, alias, address, command, *, windows_python=WINDOWS_PYTHON):
    # Delegate endpoint and executable validation plus authentication options to
    # the existing helper, replacing only its bulk-unsafe byte relay.
    argv = ssh_argv(key, known_hosts, alias, address, command,
                    transport='windows-tcp', windows_python=windows_python)
    for i, arg in enumerate(argv):
        if arg.startswith('ProxyCommand='):
            argv[i] = 'ProxyCommand=' + shlex.join([windows_python, '-u', '-c', PROXY, address])
    return argv
