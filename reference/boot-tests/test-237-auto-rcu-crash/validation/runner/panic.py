import control,json
meta=json.loads((control.P/'source/identity.json').read_text())
s,_=control.shell('source','panic-preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/sys/kernel/panic; cat /sys/module/gts9_lastactivity/parameters/test_status; timeout 5 systemctl --failed --no-pager; sync; cat /proc/sys/kernel/random/boot_id',timeout=15)
l=s.splitlines();assert l[0]==l[-1]==meta['boot_id'] and l[1]=='10' and l[2]=='started=1 finished=1 gp_done=1' and '0 loaded units listed.' in s
assert json.loads((control.P/'source/snapshot.json').read_text())['trigger']=='rcu'
control.shell('source','controlled-panic','echo c > /proc/sysrq-trigger',timeout=6,check=False)
