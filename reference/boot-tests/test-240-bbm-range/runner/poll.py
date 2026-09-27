import control,time,sys
phase=sys.argv[1];exclude=sys.argv[2] if len(sys.argv)>2 else ''
for i in range(8):
 s,r=control.shell(phase,'poll-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime',timeout=5,check=False)
 if r==0 and s.splitlines()[0]!=exclude:
  print(s);break
 time.sleep(5)
else:raise SystemExit('No attributed response; inspect before further power actions')
