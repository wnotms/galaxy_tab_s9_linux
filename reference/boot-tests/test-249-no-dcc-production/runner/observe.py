"""Two registered production boot paths, each independently attributed."""
import datetime,hashlib,json,re,subprocess,time
from pathlib import Path
import control

def classify(text):
    bad=[s for s in ("CPUS still haven't responded",'BUG: workqueue lockup','soft lockup - CPU',
                    'detected stalls','self-detected stall','CSD lock','Kernel panic - not syncing','Oops:') if s in text]
    if bad:return 'failure_observed',bad
    suspect=[s for s in ('vblank wait timed out','CTL_START timeout','Timeout waiting for hardware cmd interrupt','rpmh_rsc_send_data: Error') if s in text]
    if re.search(r'mmc\d.*(?:timed out|timeout)',text,re.I):suspect.append('MMC timeout')
    return ('suspect',suspect) if suspect else (None,[])

def profile(phase,boot):
    s,_=control.shell(phase,'profile','cat /proc/sys/kernel/random/boot_id; cat /proc/cmdline; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /sys/module/ramoops/parameters/ecc; sha256sum /sys/kernel/notes; grep -E " (_text|_stext|do_nothing|rcu_barrier_handler|irq_work_run|ipi_types)$" /proc/kallsyms; cat /proc/sys/kernel/random/boot_id',timeout=8)
    l=s.splitlines();assert l[0]==l[-1]==boot
    expected=(control.ROOT/'boot/cmdline.example.txt').read_text().split()
    assert all(t in l[1].split() for t in expected)
    assert not any(t.split('=',1)[0] in {'csdlock_debug','gts9_lastactivity','irqchip.gicv3_pseudo_nmi','gts9_watchdog_debug','softlockup_panic'} for t in l[1].split())
    assert l[2:7]==['0']*5
    assert l[7].split()[0]==hashlib.sha256((control.ROOT/'out/test249/kernel-notes.bin').read_bytes()).hexdigest()
    link={row.split()[2]:int(row.split()[0],16) for row in (control.ROOT/'out/test249/System.map').read_text().splitlines()}
    anchors={row.split()[2]:int(row.split()[0],16)-link[row.split()[2]] for row in l[8:-1]}
    assert len(anchors)==6 and len(set(anchors.values()))==1
    s,_=control.shell(phase,'removed-capabilities','cat /proc/sys/kernel/random/boot_id; zcat /proc/config.gz | grep -E "^# CONFIG_(HVC_DCC|HVC_DRIVER|ARM64_PSEUDO_NMI|CSD_LOCK_WAIT_DEBUG) is not set$"; test ! -e /dev/hvc0 && test ! -e /sys/class/tty/hvc0 && test ! -e /sys/module/smp/parameters/csd_lock_timeout && test ! -e /sys/module/gts9_lastactivity && test ! -e /sys/module/gts9_pnmi_test && echo removed_paths_absent; systemctl is-active serial-getty@hvc0.service; cat /proc/fb; cat /proc/consoles; cat /proc/sys/kernel/random/boot_id',timeout=8)
    lines=s.splitlines();assert lines[0]==lines[-1]==boot
    for sym in ('HVC_DCC','HVC_DRIVER','ARM64_PSEUDO_NMI','CSD_LOCK_WAIT_DEBUG'):
        assert '# CONFIG_'+sym+' is not set' in lines,sym
    assert 'removed_paths_absent' in lines and 'inactive' in lines
    assert any(row.startswith('0 ') for row in lines) and any(row.startswith('tty0 ') and 'E' in row for row in lines)
    s,_=control.shell(phase,'module-hashes','cat /proc/sys/kernel/random/boot_id; find /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty -type f -exec sha256sum {} +; cat /proc/modules; cat /proc/sys/kernel/random/boot_id',timeout=8)
    lines=s.splitlines();assert lines[0]==lines[-1]==boot
    actual={r.split()[1].removeprefix('/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty/'):r.split()[0] for r in lines if re.match(r'^[0-9a-f]{64}\s',r)}
    expected={r.split(maxsplit=1)[1]:r.split()[0] for r in (control.P/'validation/candidate-module-checksums.txt').read_text().splitlines()}
    assert actual==expected and len(actual)==181
    identity={'boot_id':boot,'notes_sha256':l[7].split()[0],'anchors':anchors,'runtime_minus_link':next(iter(anchors.values())),'temporary_instrumentation_removed':True,'DCC_path_absent':True,'module_files_verified':len(actual)}
    (control.P/phase/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')

def run(phase,anchor):
    assert phase in {'production-twrp','production-warm'}
    p=control.P/phase;p.mkdir(exist_ok=False)
    verdict={'budget_uptime_seconds':120,'boot_path':phase,'historical_all_causes_proven':False}
    for i in range(20):
        s,rc=control.shell(phase,'poll-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id',timeout=4,check=False)
        l=s.splitlines()
        if rc==0 and len(l)==3 and l[0]==l[-1] and l[0]!=anchor:break
        time.sleep(3)
    else:raise RuntimeError('No new attributed boot; inspect current state before any action')
    boot=l[0];verdict.update(boot_id=boot,first_connection_uptime=float(l[1].split()[0]))
    command=[control.ADB,'-s',control.LIVE,'shell',f'journalctl -b {boot.replace("-", "")} -k -f -n all --no-pager -o json']
    stream=p/'kernel-follow.jsonl';meta={'command':command,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with stream.open('wb') as output,(p/'kernel-follow.stderr').open('wb') as error:
        proc=subprocess.Popen(command,stdout=output,stderr=error)
        try:
            time.sleep(1);profile(phase,boot)
            for i in range(30):
                s,rc=control.shell(phase,'identity-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id',timeout=5,check=False)
                kind,markers=classify(stream.read_text(errors='replace'))
                if kind:
                    verdict.update(verdict=kind,markers=markers)
                    if kind=='failure_observed':time.sleep(20)
                    break
                if rc!=0:
                    verdict.update(verdict='inconclusive',reason='identity transport loss');time.sleep(20);break
                l=s.splitlines();assert len(l)==3 and l[0]==l[-1]==boot
                uptime=float(l[1].split()[0]);verdict['uptime']=uptime
                assert proc.poll() is None and stream.stat().st_size
                print(phase,boot,uptime,flush=True)
                if uptime>=120:verdict['verdict']='clean_window';break
                time.sleep(min(5,max(0,120-uptime)))
            else:raise RuntimeError('Observation budget exhausted')
            text,_=control.shell(phase,'final-json',f'journalctl -b {boot.replace("-", "")} -k --no-pager -o json',timeout=10)
            kind,markers=classify(text+'\n'+stream.read_text(errors='replace'))
            if kind:verdict.update(verdict=kind,markers=markers)
            rows=[json.loads(l) for l in text.splitlines()]
            assert rows and all(r['_BOOT_ID']==boot.replace('-','') and '_SOURCE_BOOTTIME_TIMESTAMP' in r for r in rows)
            verdict['source_timestamp_rows']=len(rows)
            s,_=control.shell(phase,'final-health','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; systemctl --failed --no-legend --plain --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=8)
            l=s.splitlines();assert l[0]==l[-1]==boot
            verdict['failed_units']=[r.split()[0] for r in l[2:-1] if r.strip()]
            assert not verdict['failed_units'],'failed service requires review'
            history,_=control.shell(phase,'boot-list','journalctl --list-boots --no-pager',timeout=8)
            ids=[r.split()[1] for r in history.splitlines() if re.match(r'^\s*-?\d+\s+[a-f0-9]{32}\s',r)]
            previous=anchor.replace('-','');assert previous in ids and ids[ids.index(previous)+1:]==[boot.replace('-','')]
        except Exception as exc:
            if verdict.get('verdict') not in {'failure_observed','suspect'}:verdict['verdict']='inconclusive'
            verdict['error']=repr(exc)
        finally:
            running=proc.poll() is None
            if running:proc.terminate()
            try:status=proc.wait(timeout=3)
            except subprocess.TimeoutExpired:proc.kill();status=proc.wait(timeout=3)
            meta.update(status=status,host_stopped_at_observation_end=running)
            (p/'kernel-follow.json').write_text(json.dumps(meta,indent=2)+'\n')
            (p/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n')
    print(verdict,flush=True)
    assert verdict.get('verdict')=='clean_window','stop for evidence/recovery review'
    return boot
