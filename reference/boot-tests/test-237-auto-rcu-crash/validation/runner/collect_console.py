import control,pathlib,json,hashlib,re,importlib.util
P=control.P/'observer';P.mkdir(parents=True,exist_ok=True)
# Grab persisted bytes before journal queries: those can stall on a wedged CPU.
for i in range(2):
 name='console-'+str(i)
 control.capture('observer',name,['pull','/var/lib/systemd/pstore/console-ramoops-0','D:\\android\\gts9-test237\\'+name+'.bin'],timeout=8)
 (P/(name+'.bin')).write_bytes(pathlib.Path('/mnt/d/android/gts9-test237/'+name+'.bin').read_bytes())
s,_=control.shell('observer','identity','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; sha256sum /var/lib/systemd/pstore/console-ramoops-0; cat /sys/module/ramoops/parameters/ecc; cat /proc/cmdline',timeout=8);print(s)
b=(P/'console-0.bin').read_bytes();assert b==(P/'console-1.bin').read_bytes() and hashlib.sha256(b).hexdigest() in s
meta=json.loads((control.P/'source/identity.json').read_text());assert s.splitlines()[0]!=meta['boot_id']
spec=importlib.util.spec_from_file_location('evidence',control.ROOT/'scripts/lastactivity-evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=m.parse(b.decode(errors='replace'),meta['capture_id']);source=json.loads((control.P/'source/snapshot.json').read_text());assert r['snapshot_sha256']==source['snapshot_sha256']
notice=re.search(rb'\nECC: (No errors detected|\d+ Corrected bytes, \d+ unrecoverable blocks)\n\Z',b);assert notice and (notice[1]==b'No errors detected' or notice[1].endswith(b', 0 unrecoverable blocks'))
r.update(ecc_notice=notice[1].decode(),raw_sha256=hashlib.sha256(b).hexdigest(),two_pulls_and_device_hash_match=True,source_snapshot_exact=True,ready_for_wedge_series=False)
(P/'verdict.json').write_text(json.dumps(r,indent=2)+'\n');print({k:v for k,v in r.items() if k not in ('cpus','records')})
control.shell('observer','boot-list','journalctl --list-boots --no-pager',timeout=12)
control.shell('observer','journal','journalctl -b --no-pager -o short-monotonic',timeout=12)
