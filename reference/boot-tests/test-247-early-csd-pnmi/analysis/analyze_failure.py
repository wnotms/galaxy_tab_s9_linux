"""Offline attribution and source-clock comparison; no device operations."""
from pathlib import Path
import re,json,subprocess
P=Path(__file__).resolve().parents[1];A=P/'analysis'
boot='e432f1a0f6ab4e82be704c9ba7ab80cb';observer='ca2235aee5c94129858c9cea934a2c52'
rows=[json.loads(line) for line in (P/'target-run/final-json.txt').read_text().splitlines()]
all_rows=[json.loads(line) for line in (P/'observer/target-all-json.txt').read_text().splitlines()]
assert all(r['_BOOT_ID']==boot for r in rows+all_rows)
ids=[line.split()[1] for line in (P/'observer/identity-history.txt').read_text().splitlines() if re.match(r'^\s*-?\d+\s+[a-f0-9]{32}\s',line)]
assert ids[ids.index(boot)+1:]==[observer]
raw=(P/'retained/a-dmesg-ramoops-0').read_text();console=(P/'retained/a-console-ramoops-0').read_text()
identity=json.loads((P/'target/identity.json').read_text());assert identity['runtime_minus_link']==0x88000
for text in (raw,console):assert 'id='+identity['capture_id'] in text and 'Kernel Offset: 0x88000' in text
pattern=re.compile(r'^(?:<\d+>)?\[\s*(\d+)\.(\d{6})\]\[.*?\] (.*)$')
def retained(text):
 result={}
 for line in text.splitlines():
  m=pattern.match(line)
  if m:result.setdefault(int(m[1])*1000000+int(m[2]),[]).append(m[3])
 return result
panic=retained(raw);con=retained(console)
first_csd=next(int(r['_SOURCE_BOOTTIME_TIMESTAMP']) for r in rows if 'csd: Detected' in r.get('MESSAGE',''))
keys=['csd: Detected non-responsive CSD lock','NMI backtrace for cpu 4','hvc_dcc0_put_chars','pmr:','x8 :']
selected=[r for r in rows if int(r.get('_SOURCE_BOOTTIME_TIMESTAMP',0))>=first_csd and isinstance(r.get('MESSAGE'),str) and any(k in r['MESSAGE'] for k in keys)]
comparisons=[]
for r in selected:
 t=int(r['_SOURCE_BOOTTIME_TIMESTAMP']);m=r['MESSAGE']
 comparisons.append({'source_us':t,'message':m,'panic_matches_live':m in panic.get(t,[]),'console_matches_live':m in con.get(t,[])})
assert comparisons and all(r['panic_matches_live'] and r['console_matches_live'] for r in comparisons)
(A/'live-retained-overlap.json').write_text(json.dumps({'scope':'Selected failure/backtrace messages from the first CSD report at exact source times, not the entire crash payload','initial_broad_selection_note':'An initial exploratory comparison also selected unrelated early-boot register-warning lines at0.296954/0.297480 s; they are in panic but not the retained console. They are outside this explicitly bounded failure comparison, not claimed corrupt.','records':comparisons},indent=2)+'\n')
users=[{'source_us':r.get('_SOURCE_BOOTTIME_TIMESTAMP',r.get('__MONOTONIC_TIMESTAMP')),'message':r['MESSAGE']} for r in all_rows if isinstance(r.get('MESSAGE'),str) and ('hvc0' in r['MESSAGE'] or 'hvc_dcc' in r['MESSAGE'])]
(A/'hvc-startup.json').write_text(json.dumps(users,indent=2)+'\n')
commands=['llvm-objdump','-d','--no-show-raw-insn','--disassemble-symbols=hvc_dcc0_put_chars,hvc_write','out/test247/vmlinux']
r=subprocess.run(commands,capture_output=True,check=True);(A/'dcc-disassembly.txt').write_bytes(r.stdout)
# Source snapshots were saved at first analysis; do not overwrite them on replay.
import hashlib
for name,digest in json.loads((A/'source-files.json').read_text()).items():
 assert hashlib.sha256((A/name).read_bytes()).hexdigest()==digest
times=[t/1e6 for t,messages in panic.items() if 'NMI backtrace for cpu 4' in messages]
assert len(times)==3
panic_time=next(t/1e6 for t,messages in panic.items() if any('Kernel panic - not syncing:' in m for m in messages))
(A/'verdict.json').write_text(json.dumps({'verdict':'natural_failure_target_stack_captured','boot_id':identity['boot_id'],'capture_id':identity['capture_id'],'runtime_minus_link':hex(identity['runtime_minus_link']),'immediate_retained_observer':observer,'first_csd_source_seconds':first_csd/1e6,'target_backtrace_seconds':times,'failed_cpu':4,'failed_task_pid':1251,'failed_task_comm':'(agetty)','target_pc':'hvc_dcc0_put_chars+0x34/0x48','saved_pmr':'0xc0','saved_mdccsr_el0_last_read_x9':'0x20000000','instruction':'yield in loop polling MDCCSR_EL0 bit29 (DCC TX busy)','ordinary_irq_masked':True,'pseudo_nmi_response_observed':True,'panic_seconds':panic_time,'root_cause_scope':'This boot: DCC transmit busy wait under hvc_write IRQ-disabled spinlock prevents ordinary IPI progress; getty on hvc0 was started. No fix has been applied and earlier failures need their own attribution.','failed_process_proc_inspection_available':False,'proc_inspection_limitation':'failure-live/identity-process belongs to recovered observer ca2235ae; its PID1251 is a NetworkManager thread, not the failed agetty. Do not use observer proc data as target evidence.','cpu_stall_repair_established':False},indent=2)+'\n')
print('PASS: attributed target stack; selected live/retained message matches:',len(comparisons),'target backtrace times:',times)
