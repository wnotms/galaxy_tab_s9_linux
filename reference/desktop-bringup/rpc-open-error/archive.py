import pathlib, json, subprocess, hashlib, shutil, time
R=pathlib.Path.cwd(); E=R/'reference/desktop-bringup/rpc-open-error'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v): (E/n).write_text(json.dumps(v,indent=2)+'\n')
cmd=['/mnt/d/android/platform-tools/adb.exe','-s','gts9wifi-0001','shell','cat /proc/sys/kernel/random/boot_id; uptime; systemctl is-active gdm3; for f in capacity temp voltage_now status; do printf "%s=" "$f"; cat /sys/class/power_supply/sm5714-battery/$f; done; cat /sys/class/remoteproc/remoteproc*/name; cat /sys/class/remoteproc/remoteproc*/state']
start=time.monotonic(); run=subprocess.run(cmd,capture_output=True,timeout=12)
(E/'device-readonly.txt').write_bytes(run.stdout); (E/'device-readonly.stderr').write_bytes(run.stderr)
save('device-readonly.command.json',dict(argv=cmd,returncode=run.returncode,seconds=time.monotonic()-start,readonly=True))
assert run.returncode==0 and b'0f360b00-4f24-43cf-8ce5-1aa135c5f7a3' in run.stdout and b'active' in run.stdout
for name in ['check.py','host.py','archive.py']: shutil.copyfile(R/'out/rpc-open-error/qualification'/name,E/name)
tracked=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
protected=[p for p in tracked if p and (p.startswith(('kernel/','rootfs/','scripts/','reference/boot-tests/')) or p=='userspace/sensors/sources.json')]
subprocess.run(['git','diff','--exit-code','HEAD','--','kernel/','rootfs/','scripts/','reference/boot-tests/','userspace/sensors/sources.json'],check=True,stdout=subprocess.DEVNULL)
save('PROTECTED.json',dict(base_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),checked=len(protected),successful=True,kernel_config_DTS_modules_source_changed=False,rootfs_USB_ADB_charging_changed=False,default_sensor_sources_changed=False,physical_history_changed=False,device_mutation=False))
save('summary.json',dict(verdict='RPC_ENOENT_ARM64_QUALIFIED_NOT_DEPLOYED',host_tests=105,host_skips=0,ARM64_cases=18,upstream_tests=2,compiled_sources=56,changed_sources=['hexagonrpcd/aee_error.h','hexagonrpcd/apps_std.c'],missing_file_status=dict(before=1,after=69),library_unchanged=True,DSP_or_SSC_effect_proved=False,hardware_tested=False,installed=False,kernel_build=dict(executed=False),full_host_regression=dict(executed=False),github_actions=False,goal_complete=False))
print(json.dumps(dict(protected_files=len(protected),device_read=run.stdout.decode().splitlines())))
