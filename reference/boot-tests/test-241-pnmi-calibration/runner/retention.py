import control,pathlib,json,hashlib,re,sys

def region(raw,cal,pstore=False):
 lines=raw.splitlines()
 if pstore:
  lines=[re.sub(rb'^\[ *\d+\.\d+\](?:\[ *[CT]\d+\])? ',b'',x) for x in lines]
 begin=b'GTS9_PNMI_TEST_BEGIN id='+cal.encode()+b' '
 end=b'GTS9_PNMI_TEST_END id='+cal.encode()+b' '
 a=[i for i,x in enumerate(lines) if x.startswith(begin)]
 b=[i for i,x in enumerate(lines) if x.startswith(end)]
 assert len(a)==len(b)==1 and a[0]<b[0],(a,b)
 data=b'\n'.join(lines[a[0]:b[0]+1])+b'\n'
 assert b'NMI backtrace for cpu 0' in data and b'gts9_pnmi_masked_region+' in data
 return data

if __name__=='__main__':
 meta=json.loads((control.P/'target/identity.json').read_text());cal=meta['calibration_id'];boot=meta['boot_id']
 if sys.argv[1]=='source':
  s,_=control.shell('retention-source','identity','cat /proc/sys/kernel/random/boot_id; cat /sys/module/gts9_pnmi_test/parameters/capture_id; cat /proc/sys/kernel/printk; cat /sys/module/ramoops/parameters/ecc; cat /proc/sys/kernel/random/boot_id',timeout=8)
  l=s.splitlines();assert l[0]==l[-1]==boot and l[1]==cal and int(l[2].split()[0])==5 and l[3]=='64'
  j,_=control.shell('retention-source','journal','journalctl -b '+boot.replace('-','')+' -k -p warning --no-pager -o cat',timeout=12)
  data=region(j.encode(),cal)
  p=control.P/'retention-source';(p/'payload.bin').write_bytes(data)
  (p/'reference.json').write_text(json.dumps({'boot_id':boot,'calibration_id':cal,'payload_sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'lines':len(data.splitlines()),'priority_max':4},indent=2)+'\n')
  control.shell('retention-source','boot-list','journalctl --list-boots --no-pager',timeout=12)
 elif sys.argv[1]=='observer':
  p=control.P/'retention-observer';p.mkdir(parents=True,exist_ok=True)
  for i in range(2):
   name='console-'+str(i)
   control.capture('retention-observer',name,['pull','/var/lib/systemd/pstore/console-ramoops-0','D:\\android\\gts9-test241\\'+name+'.bin'],timeout=10)
   (p/(name+'.bin')).write_bytes(pathlib.Path('/mnt/d/android/gts9-test241/'+name+'.bin').read_bytes())
  s,_=control.shell('retention-observer','identity','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; sha256sum /var/lib/systemd/pstore/console-ramoops-0; cat /sys/module/ramoops/parameters/ecc; cat /sys/module/gts9_pnmi_test/parameters/capture_id; cat /sys/module/gts9_pnmi_test/parameters/status; cat /proc/sys/kernel/random/boot_id',timeout=8)
  l=s.splitlines();observer=l[0];assert observer==l[-1] and observer!=boot and l[3]=='64' and l[4]!=cal and 'started=0' in l[5]
  raw=(p/'console-0.bin').read_bytes();assert raw==(p/'console-1.bin').read_bytes() and hashlib.sha256(raw).hexdigest()==l[2].split()[0]
  payload=region(raw,cal,pstore=True);(p/'payload.bin').write_bytes(payload)
  expected=(control.P/'retention-source/payload.bin').read_bytes()
  notice=re.search(rb'\nECC: (No errors detected|\d+ Corrected bytes, \d+ unrecoverable blocks)\n\Z',raw)
  assert notice and (notice[1]==b'No errors detected' or notice[1].endswith(b', 0 unrecoverable blocks'))
  history,_=control.shell('retention-observer','boot-list','journalctl --list-boots --no-pager',timeout=12)
  ids=[x.split()[1] for x in history.splitlines() if re.match(r'^\s*-?\d+\s+[0-9a-f]{32}\s',x)]
  assert ids[ids.index(boot.replace('-',''))+1]==observer.replace('-','')
  control.shell('retention-observer','journal','journalctl -b --no-pager -o short-monotonic',timeout=12)
  verdict={'source_boot_id':boot,'observer_boot_id':observer,'calibration_id':cal,'adjacent_retained_boots':True,'two_pulls_and_device_hash_match':True,'ecc_notice':notice[1].decode(),'payload_sha256':hashlib.sha256(payload).hexdigest(),'payload_bytes':len(payload),'payload_lines':len(payload.splitlines()),'source_payload_exact':payload==expected,'natural_failure_capture_proven':False}
  (p/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n');print(verdict)
  assert payload==expected,'Retained backtrace payload differs from live source'
 else:raise SystemExit('source or observer required')
