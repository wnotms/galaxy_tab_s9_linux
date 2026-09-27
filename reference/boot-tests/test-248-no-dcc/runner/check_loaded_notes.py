import json
import control
boot=json.loads((control.P/'target-run/verdict.json').read_text())['boot_id']
expected=json.loads((control.P/'validation/expected-module-notes.json').read_text())
command='cat /proc/sys/kernel/random/boot_id; '+ '; '.join('sha256sum /sys/module/'+name+'/notes/.note.gnu.build-id' for name in expected)+'; cat /proc/sys/kernel/random/boot_id'
s,_=control.shell('target','loaded-module-notes',command,timeout=8)
l=s.splitlines();assert l[0]==l[-1]==boot
actual={row.split()[1].split('/')[3]:row.split()[0] for row in l[1:-1]}
assert actual==expected
(control.P/'target/loaded-module-notes-check.json').write_text(json.dumps({'boot_id':boot,'matches_candidate':True,'modules':actual,'scope':'Build-id note match; not complete in-memory code attestation'},indent=2)+'\n')
