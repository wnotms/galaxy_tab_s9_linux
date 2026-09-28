import sys,subprocess,json,datetime
from pathlib import Path
root=Path('reference/boot-tests/test-253-adbd-usb-reconnect')
folder=root/sys.argv[1];folder.mkdir(parents=True,exist_ok=True);name=sys.argv[2];args=sys.argv[3:]
target=folder/(name+'.txt');assert not target.exists()
started=datetime.datetime.now(datetime.timezone.utc).isoformat();data=None
if args[0]=='--input':data=Path(args[1]).read_bytes();args=args[2:]
try:
 r=subprocess.run(args,input=data,capture_output=True,timeout=55);out,err,status=r.stdout,r.stderr,r.returncode
except subprocess.TimeoutExpired as e:out,err,status=e.stdout or b'',e.stderr or b'','timeout'
target.write_bytes(out);(folder/(name+'.stderr')).write_bytes(err)
(folder/(name+'.command.json')).write_text(json.dumps(dict(argv=args,started_utc=started,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status=status),indent=2)+'\n')
print(out.decode(errors='replace')[-1000:]);print(err.decode(errors='replace')[-500:],file=sys.stderr)
if status!=0:raise SystemExit('command failed: '+str(status))
