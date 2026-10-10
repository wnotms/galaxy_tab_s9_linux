from pathlib import Path
import json,hashlib,subprocess,shutil,datetime
R=Path.cwd();E=R/'reference/boot-tests/test-390-ssc-missing-file-status'
def load(p):return json.loads(p.read_text())
def save(n,v):(E/n).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rollback=next(p for p in E.glob('rollback-*') if p.is_dir()); accepted=load(rollback/'summary.json'); assert accepted['verdict']=='EXACT370_DEBIAN_RESTORED' and not accepted['kernel_fault_counts']
cmd=['/mnt/d/android/platform-tools/adb.exe','-s','gts9wifi-0001','shell','cat /proc/sys/kernel/random/boot_id; systemctl is-active gdm3 gts9-palm gts9-adbd gts9-usb-acm; for f in capacity temp voltage_now status; do printf "%s=" "$f"; cat /sys/class/power_supply/sm5714-battery/$f; done; cat /sys/class/remoteproc/remoteproc*/state']
start=datetime.datetime.now(datetime.timezone.utc);run=subprocess.run(cmd,capture_output=True,timeout=12,check=True)
(E/'resume-readonly.txt').write_bytes(run.stdout);(E/'resume-readonly.stderr').write_bytes(run.stderr);save('resume-readonly.command.json',dict(argv=cmd,status=run.returncode,started_utc=start.isoformat(),ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),readonly=True))
assert run.stdout.decode().splitlines()[0].replace('-','')==accepted['boot_id']; assert run.stdout.decode().splitlines()[1:5]==['active']*4
stage=Path('/mnt/d/android/gts9-active/gts9-test390');manifest=load(E/'staged-files.json');assert set(p.name for p in stage.iterdir())==set(manifest)
for n,d in manifest.items():
 p=stage/n;assert not p.is_symlink() and p.is_file() and p.stat().st_size==d['bytes'] and sha(p)==d['sha256'],n
save('WINDOWS_STAGE_CLEANUP.json',dict(removed_path=str(stage),removed_files=len(manifest),removed_bytes=sum(d['bytes'] for d in manifest.values()),files=manifest,after_exact370_restore=True))
for n in manifest:(stage/n).unlink()
stage.rmdir()
for n in ['install.stdout','install.stderr','discover.stdout','discover.stderr','preflight.stdout','preflight.stderr']:shutil.copyfile(R/'out/ssc-open-error390'/n,E/n)
content=load(E/'runtime-discovery/discovery-rpc-return-content.json');stat=load(E/'runtime-discovery/discovery-rpc-stat-metadata.json');frames=load(E/'runtime-discovery/discovery-rpc-return-frames.json');missing=load(E/'runtime-discovery/discovery-missing-file-status.json');trace=load(E/'runtime-discovery/glink-complete.json');physical=load(E/'runtime-discovery/summary.json');assert content['complete'] and content['observed_sessions']==178 and stat['complete'] and stat['observed_entries']==35 and frames['complete'] and missing['calls'][0]['status']==69 and trace['complete']
commands=sorted((E/'runtime-discovery').glob('accelerometer-*.command.json'))
probe=[load(p) for p in commands];start_rpc=load(E/'runtime-discovery/runtime-start.command.json')
save('summary.json',dict(verdict='STOP_STATUS69_SSC_ABSENT_RESTORED370',registered_attempts=1,candidate_boot=physical['boot_id'],restored_boot=accepted['boot_id'],callback_status_proved=missing,SSC_service_present=False,accelerometer_sample=False,physical_rotation_tested=False,registered_query_window_seconds=60,elapsed_through_collection_and_verdict_seconds=physical['observation_seconds'],accelerometer_probes=len(probe),last_probe_end_utc=probe[-1]['ended_utc'],runtime_start_end_utc=start_rpc['ended_utc'],registry_matching_sessions=178,stat_matching_entries=35,kernel_fault_counts=physical['kernel_fault_counts'],raw_journal_bytes=(E/'runtime-discovery/discovery-unit-journal.txt').stat().st_size,trace_bytes=trace['trace_bytes'],final_acceptance=str((rollback/'summary.json').relative_to(E)),control_transport='adb',PPS=False,pump_ON=False,full_regression=dict(executed=False,reason='Results-only;32 namespace and105 callback qualification reused unchanged.'),kernel_build=dict(executed=False),github_actions=False,no_retry=True,goal_complete=False))
print(json.dumps(dict(verdict=physical['verdict'],restored_boot=accepted['boot_id'],probes=len(probe),registry=178,stat=35,GLINK_bytes=trace['trace_bytes'],Windows_removed_bytes=sum(d['bytes'] for d in manifest.values()),same_boot_read=run.stdout.decode().splitlines()),indent=2))
