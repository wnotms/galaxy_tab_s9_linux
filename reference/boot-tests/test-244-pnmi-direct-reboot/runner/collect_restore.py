import control,monitor,json
meta=json.loads((control.P/'target/identity.json').read_text());boot=meta['boot_id']
assert json.loads((control.P/'natural/verdict.json').read_text())['verdict']=='clean_window'
s,_=control.shell('natural','final-health','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; gts9_capture=$(cat /sys/module/gts9_lastactivity/parameters/capture_id); printf "capture=%s\n" "$gts9_capture"; cat /sys/module/gts9_pnmi_test/parameters/enable; cat /sys/module/gts9_pnmi_test/parameters/status; timeout 5 systemctl --failed --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=10)
l=s.splitlines();assert l[0]==l[-1]==boot and l[2]=='capture=' and l[3]=='N' and 'started=0' in l[4] and '0 loaded units listed.' in s
j,_=control.shell('natural','kernel-json','journalctl -b '+boot.replace('-','')+' -k --no-pager -o json',timeout=12)
rows=[json.loads(x) for x in j.splitlines()];assert rows and all(r['_BOOT_ID']==boot.replace('-','') for r in rows) and monitor.classify(j)[0] is None
assert not any('GTS9_LA_READY' in str(r.get('MESSAGE','')) or 'GTS9_PNMI_TEST_BEGIN' in str(r.get('MESSAGE','')) for r in rows)
stream=[json.loads(x) for x in (control.P/'natural/kernel-follow.jsonl').read_text().splitlines()]
assert all(r['_BOOT_ID']==boot.replace('-','') for r in stream)
marker=json.loads((control.P/'target/marker.json').read_text())
assert sum(r.get('MESSAGE')==marker['MESSAGE'] for r in rows)==1 and sum(r.get('MESSAGE')==marker['MESSAGE'] for r in stream)==1
(control.P/'natural/json-check.json').write_text(json.dumps({'boot_id':boot,'final_rows':len(rows),'stream_rows':len(stream),'stream_source_timestamp_rows':sum('_SOURCE_BOOTTIME_TIMESTAMP' in r for r in stream),'marker_unique_in_both':True,'complete_stream_json':True,'no_fault_signature':True},indent=2)+'\n')
print('final and live JSON verified',len(rows),len(stream),flush=True)
control.recover('to-recovery')
control.poll('twrp-restore',recovery=True,tries=9)
control.recovery_capture('twrp-restore')
control.flash('restore',restore=True)
