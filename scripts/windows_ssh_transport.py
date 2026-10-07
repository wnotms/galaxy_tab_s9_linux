"""WSL SSH identity/trust, optional native Windows TCP path; no device mutation.

No private key or known-hosts file is copied to Windows. Windows receives only
an encrypted SSH byte stream; local OpenSSH remains the authentication owner.
The helper is passed with -c to an existing Windows Python, not staged on disk.
"""
import ipaddress
from pathlib import Path
import shlex

WINDOWS_PYTHON='/mnt/f/msys64/ucrt64/bin/python.exe'
PROXY=r'''import socket,os,sys,threading,msvcrt
if sys.platform!="win32":raise RuntimeError("native Windows TCP required")
msvcrt.setmode(0,os.O_BINARY);msvcrt.setmode(1,os.O_BINARY)
s=socket.create_connection((sys.argv[1],22),3);s.settimeout(1)
stop=threading.Event()
def upload():
 try:
  while not stop.is_set():
   data=os.read(0,65536)
   if not data:break
   s.sendall(data)
 finally:stop.set()
threading.Thread(target=upload,daemon=True).start()
try:
 while not stop.is_set():
  try:data=s.recv(65536)
  except socket.timeout:continue
  if not data:break
  pos=0
  while pos<len(data):
   n=os.write(1,data[pos:])
   if n<=0:raise OSError("proxy stdout closed")
   pos+=n
finally:stop.set();s.close()
'''


def ssh_argv(key,known_hosts,alias,address,command,*,transport='direct',windows_python=WINDOWS_PYTHON):
    ip=ipaddress.IPv4Address(address)
    if not any(ip in ipaddress.IPv4Network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
        raise ValueError('enrolled private IPv4 required')
    result=['ssh','-i',str(key),'-o','BatchMode=yes','-o','ConnectTimeout=3',
            '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known_hosts),
            '-o','HostKeyAlias='+alias]
    if transport=='windows-tcp':
        if not Path(windows_python).is_file():raise ValueError('registered native Windows Python unavailable')
        result+=['-o','ProxyCommand='+shlex.join([windows_python,'-u','-c',PROXY,str(ip)])]
    elif transport!='direct':raise ValueError('unknown SSH transport')
    return result+['root@'+str(ip),command]
