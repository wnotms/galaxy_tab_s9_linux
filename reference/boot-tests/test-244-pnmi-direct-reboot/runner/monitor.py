import control,json,time,subprocess,re,datetime

def classify(text):
 bad=[x for x in ("CPUS still haven't responded",'BUG: workqueue lockup','soft lockup - CPU','detected stalls','self-detected stall','CSD lock','Kernel panic - not syncing','Oops:') if x in text]
 if bad:return 'failure_observed',bad
 suspect=[x for x in ('vblank wait timed out','CTL_START timeout','Timeout waiting for hardware cmd interrupt','rpmh_rsc_send_data: Error') if x in text]
 if re.search(r'mmc\d.*(?:timed out|timeout)',text,re.I):suspect.append('MMC timeout')
 if suspect:return 'suspect',suspect
 return None,[]

def main():
 meta=json.loads((control.P/'target/identity.json').read_text());boot=meta['boot_id'];cap=meta['boot_id']
 p=control.P/'natural';p.mkdir(exist_ok=False)
 cmd=[control.ADB,'-s',control.LIVE,'shell','journalctl -b '+boot.replace('-','')+' -k -f -n all --no-pager -o json']
 stream=p/'kernel-follow.jsonl';verdict={'boot_id':boot,'lastactivity_enabled':False,'cpu_stall_repair_established':False}
 started=time.monotonic()
 with stream.open('wb') as out,(p/'kernel-follow.stderr').open('wb') as err:
  proc=subprocess.Popen(cmd,stdout=out,stderr=err)
  process={'command':cmd,'host_pid':proc.pid,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
  (p/'kernel-follow.json').write_text(json.dumps(process,indent=2)+'\n')
  try:
   time.sleep(1)
   for i in range(24):
    s,rc=control.shell('natural','identity-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/module/gts9_pnmi_test/parameters/enable; cat /sys/module/gts9_pnmi_test/parameters/status; cat /proc/sys/kernel/random/boot_id',timeout=6,check=False)
    kind,markers=classify(stream.read_text(errors='replace'))
    if kind:verdict.update(verdict=kind,markers=markers);break
    if rc!=0:verdict.update(verdict='unattributed',reason='identity transport failure');break
    l=s.splitlines()
    if len(l)!=5 or l[0]!=l[-1] or l[0]!=boot:verdict.update(verdict='unattributed',reason='changed or incomplete boot identity');break
    if l[2]!='N' or 'started=0' not in l[3]:verdict.update(verdict='unattributed',reason='calibration state changed');break
    uptime=float(l[1].split()[0]);verdict['uptime']=uptime;print('target uptime',uptime,'stream bytes',stream.stat().st_size,flush=True)
    if proc.poll() is not None or not stream.stat().st_size:verdict.update(verdict='unattributed',reason='kernel stream stopped or empty',stream_status=proc.poll());break
    if uptime>=300:verdict.update(verdict='clean_window');break
    time.sleep(15)
   else:verdict.update(verdict='unattributed',reason='observation budget exhausted')
   if verdict.get('verdict')=='failure_observed':
    print('Positive failure; retain stream for up to 20 seconds for target backtrace',flush=True);time.sleep(20)
   j,rc=control.shell('natural','final-journal','journalctl -b '+boot.replace('-','')+' --no-pager -o short-monotonic',timeout=10,check=False)
   kind,markers=classify(j+'\n'+stream.read_text(errors='replace'))
   if kind:verdict.update(verdict=kind,markers=markers)
   elif verdict.get('verdict')=='clean_window' and (rc!=0 or not j or 'GTS9_PNMI_TARGET boot_id='+boot not in j):verdict.update(verdict='unattributed',reason='final attributed journal missing')
   history,hrc=control.shell('natural','boot-list','journalctl --list-boots --no-pager',timeout=10,check=False)
   if verdict.get('verdict')=='clean_window':
    ids=[line.split()[1] for line in history.splitlines() if re.match(r'^\s*-?\d+\s+[0-9a-f]{32}\s',line)]
    if hrc!=0 or not ids or ids[-1]!=boot.replace('-',''):verdict.update(verdict='unattributed',reason='retained boot attribution changed')
  finally:
   was_running=proc.poll() is None
   if was_running:proc.terminate()
   try:status=proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();status=proc.wait(timeout=5)
   process.update(status=status,host_stopped_at_observation_end=was_running,elapsed_host_seconds=time.monotonic()-started)
   (p/'kernel-follow.json').write_text(json.dumps(process,indent=2)+'\n')
   (p/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n')
 print(verdict,flush=True)
 if verdict.get('verdict')!='clean_window':raise SystemExit(10)

if __name__=='__main__':main()
