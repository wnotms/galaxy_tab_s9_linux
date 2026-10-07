#!/usr/bin/env python3
"""Test339 device-local guardian. Raw reads only; kernel owns one-shot/PPS/pump.

finally unbind is a stop operation, not a charging request. No execution/import
contacts hardware until run() is explicitly invoked with the frozen plan.
"""
import argparse,ctypes as c,fcntl,gzip,hashlib,json,os,re,signal,subprocess,time,threading
from pathlib import Path
class Msg(c.Structure):
    _fields_=[('addr',c.c_uint16),('flags',c.c_uint16),('length',c.c_uint16),('buf',c.POINTER(c.c_uint8))]
class Transfer(c.Structure):
    _fields_=[('msgs',c.POINTER(Msg)),('nmsgs',c.c_uint32)]

def values(raw):return dict(x.split('=',1) for x in raw.splitlines() if '=' in x)
def decoded(regs):
    pair=lambda n:(regs[n]<<5)|(regs[n+1]>>3)
    return dict(mode=regs[0x10]&12,adc_enabled=bool(regs[0x1c]&1),vbus_mv=4096+pair(0x1e),ibus_ua=pair(0x22)*625,vbat_uv=2048000+pair(0x27)*500,die_decic=225+regs[0x26]*5)

class Hardware:
    def __init__(self,boot):
        self.boot=boot;self.node=Path('/sys/bus/i2c/devices/0-0063').resolve(strict=True)
        if (self.node/'driver').resolve(strict=True).name!='sm5440-fedora' or b'siliconmitus,sm5440' not in (self.node/'of_node/compatible').read_bytes().split(b'\0'):raise ValueError('provider')
        self.fd=os.open('/dev/i2c-0',os.O_RDWR)
    def read(self,reg,length=1):
        pointer=(c.c_uint8*1)(reg);out=(c.c_uint8*length)();messages=(Msg*2)(Msg(0x63,0,1,pointer),Msg(0x63,1,length,out));packet=Transfer(messages,2);fcntl.ioctl(self.fd,0x0707,packet);return list(out)
    def sample(self):
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip().replace('-','')!=self.boot:raise ValueError('boot changed')
        regs={n:self.read(n)[0] for n in [0x10,0x1c]}
        for n in [0x1e,0x22,0x27]:
            raw=self.read(n,2);regs[n]=raw[0];regs[n+1]=raw[1]
        regs[0x26]=self.read(0x26)[0]
        pack=values(Path('/sys/class/power_supply/sm5714-battery/uevent').read_text())
        source_paths=list(Path('/sys/kernel/debug').glob('sm5714-*/current-port'))
        if len(source_paths)!=1:raise ValueError('source provider')
        tcpm=list(Path('/sys/class/power_supply').glob('tcpm-source-psy-*/uevent'))
        if len(tcpm)!=1:raise ValueError('TCPM provider')
        return dict(boottime_seconds=time.clock_gettime(time.CLOCK_BOOTTIME),boot_id=self.boot,battery=pack,registers=regs,adc=decoded(regs),source_raw=source_paths[0].read_text(),tcpm=values(tcpm[0].read_text()),calibrated=False,configuration_register_data_written=False)
    def stop(self):
        # devm drains the kernel worker, proves OFF and restores the fixed lease.
        command='from pathlib import Path; Path("/sys/bus/i2c/drivers/sm5440-fedora/unbind").write_text("0-0063")'
        subprocess.run(['python3','-c',command],check=True,timeout=8)
        if (self.node/'driver').exists():raise ValueError('driver remained bound')
        mode=self.read(0x10)[0]
        if mode&12:raise ValueError('pump OFF not proven after cleanup')
        source=list(Path('/sys/class/power_supply').glob('tcpm-source-psy-*/uevent'))
        if len(source)!=1:raise ValueError('cleanup TCPM provider')
        t=values(source[0].read_text());usb=values(Path('/sys/class/power_supply/sm5714-usb/uevent').read_text())
        p=subprocess.run(['journalctl','-k','-b','-o','json','--no-pager'],capture_output=True,text=True,timeout=8)
        if p.returncode:raise ValueError('cleanup journal unavailable')
        rows=[json.loads(x) for x in p.stdout.splitlines()]
        # Unbind drained the only worker before this final phase proof.
        proof=validate_cleanup(rows,self.boot,mode,t,usb)
        return dict(proof,pump_mode=mode,driver_unbound=True,tcpm=t,usb=usb)


def validate_cleanup(rows,boot,mode,t,usb):
    if mode&12:raise ValueError('cleanup pump OFF not proven')
    if not rows or any(r.get('_BOOT_ID')!=boot for r in rows) or min(int(r['__MONOTONIC_TIMESTAMP']) for r in rows)>5000000 or not any(str(r.get('MESSAGE','')).startswith(('Linux version ', 'Linux boot')) and int(r['__MONOTONIC_TIMESTAMP'])<=5000000 for r in rows):
        raise ValueError('cleanup full phase journal missing')
    entered=any(any(k in str(r.get('MESSAGE','')) for k in ('one-shot entry begins:', 'direct charge started:', 'one-shot pump started:', 'one-shot refresh ', 'one-shot pump complete:', 'fixed return verified:')) for r in rows)
    for r in rows:
        msg=str(r.get('MESSAGE',''))
        if 'one-shot pump stopped:' in msg:
            m=re.search(r'primary=(-?\d+) cleanup=(-?\d+) lease=(\d+) no_restart=1$',msg)
            if not m or int(m[2]) or int(m[3]):raise ValueError('native cleanup/lease unproven')
    online=int(t.get('POWER_SUPPLY_ONLINE','-1'))
    mv=int(t.get('POWER_SUPPLY_VOLTAGE_NOW','-1'))
    if entered:
        if online!=1 or mv!=9000000 or not 0<int(t['POWER_SUPPLY_CURRENT_MAX'])<=1500000:
            raise ValueError('fixed9 not restored after entry')
        if usb.get('POWER_SUPPLY_ONLINE')!='1' or not 100000<=int(usb['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])<=1500000:
            raise ValueError('switching supply not restored after entry')
        return dict(pre_entry=False,fixed9_restored=True)
    # No entry witness in complete sameboot journal after draining the worker:
    # no lease/PPS/pump operation. Ordinary offline/PC5/fixed9 may remain.
    if online==0:
        if mv!=0 or usb.get('POWER_SUPPLY_ONLINE')!='0':raise ValueError('pre-entry offline mismatch')
    elif online==1 and mv in (5000000,9000000):
        limit=1800000 if mv==5000000 else 1500000
        if not 0<int(t['POWER_SUPPLY_CURRENT_MAX'])<=limit or usb.get('POWER_SUPPLY_ONLINE')!='1' or not 100000<=int(usb['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])<=limit:
            raise ValueError('pre-entry ordinary source limit')
    else:raise ValueError('unexplained PPS/source before entry')
    return dict(pre_entry=True,fixed9_restored=False,ordinary_source_preserved=True)


class CleanupFailure(RuntimeError):
    def __init__(self,primary,cleanup):
        self.primary_error=repr(primary) if primary is not None else None
        self.cleanup_error=repr(cleanup)
        super().__init__('primary='+str(self.primary_error)+'; cleanup='+self.cleanup_error)

FAIL = re.compile(r'one-shot pump stopped:|direct-charge start failed|fixed fallback failed|stopping direct charge|retained fault=|failed to refresh PPS|latched fault:|Kernel panic|soft lockup|hard LOCKUP|rcu.*stall|CSD.*(?:stall|non-responsive)|\bOops:|\bBUG:|Internal error|SError|blocked for more than|workqueue lockup|WARNING: CPU:|I2C.*(?:error|timeout)', re.I)


def check_sample(s):
    b, a, t = s['battery'], s['adc'], s['tcpm']
    if b.get('POWER_SUPPLY_HEALTH') != 'Good' or b.get('POWER_SUPPLY_PRESENT') != '1':
        raise ValueError('pack health')
    if not 20 <= int(b['POWER_SUPPLY_CAPACITY']) < 80 or not 200 <= int(b['POWER_SUPPLY_TEMP']) < 420 or not 3500000 <= int(b['POWER_SUPPLY_VOLTAGE_NOW']) < 4400000 or int(b['POWER_SUPPLY_CURRENT_NOW']) > 3600000:
        raise ValueError('pack safety')
    if a['mode'] not in (0, 4):
        raise ValueError('unknown pump/reverse mode')
    if a['mode'] == 4:
        if t.get('POWER_SUPPLY_ONLINE') != '2' or int(t['POWER_SUPPLY_CURRENT_NOW']) != 1800000 or not 8200000 <= int(t['POWER_SUPPLY_VOLTAGE_NOW']) <= 10500000:
            raise ValueError('active PPS budget')
        if not a['adc_enabled'] or a['ibus_ua'] > 1800000 or not 3500000 <= a['vbat_uv'] < 4400000 or a['die_decic'] >= 850 or abs(a['vbat_uv'] - int(b['POWER_SUPPLY_VOLTAGE_NOW'])) > 200000 or abs(a['vbus_mv']*1000-int(t['POWER_SUPPLY_VOLTAGE_NOW'])) > 500000 or a['vbus_mv'] > 10800:
            raise ValueError('physical sample safety')
    return a['mode'] == 4


def native_proof(rows, boot, required=False):
    """Full journal, kernel source time, one attempt with paired parked refreshes."""
    if not rows or any(r.get('_BOOT_ID') != boot for r in rows) or min(int(r['__MONOTONIC_TIMESTAMP']) for r in rows) > 5000000:
        raise ValueError('incomplete/mixed kernel journal')
    starts, fixed, terminal, direct = [], [], [], []
    parked = None
    refreshes = 0
    previous = -1
    for r in rows:
        msg = str(r.get('MESSAGE', ''))
        if FAIL.search(msg):
            raise ValueError('first native/kernel fault: ' + msg)
        if not any(x in msg for x in ('one-shot ', 'fixed return verified:', 'direct charge started:')):
            continue
        stamp = int(r['_SOURCE_MONOTONIC_TIMESTAMP'])
        if stamp < previous:
            raise ValueError('native timestamp order')
        previous = stamp
        if 'one-shot pump started:' in msg:
            m = re.search(r'target=(\d+)mV/(\d+)mA deadline=(\d+)ms max_ms=30000 no_restart=1$', msg)
            if not m or starts:
                raise ValueError('invalid/repeated native start')
            mv, ma, deadline = map(int, m.groups())
            if not 8200 <= mv <= 10500 or mv % 20 or ma != 1800 or not 29000 <= deadline-stamp//1000 <= 30000:
                raise ValueError('native target/deadline')
            starts.append((stamp, mv, ma, deadline))
        elif 'direct charge started:' in msg:
            direct.append(stamp)
            if len(direct) > 1:
                raise ValueError('second entry')
        elif 'one-shot refresh parked:' in msg:
            if not starts or parked is not None or terminal or 'pump_OFF=1' not in msg:
                raise ValueError('unpaired park')
            parked = stamp
        elif 'one-shot refresh resumed:' in msg:
            m = re.search(r'target=(\d+)mV/(\d+)mA deadline=(\d+)ms$', msg)
            if not m or parked is None or stamp-parked > 2000000 or terminal:
                raise ValueError('unpaired/late refresh')
            mv, ma, deadline = map(int, m.groups())
            if not 8200 <= mv <= 10500 or mv % 20 or ma != 1800 or deadline != starts[0][3] or stamp >= deadline*1000:
                raise ValueError('refresh bounds/deadline')
            parked = None
            refreshes += 1
        elif 'fixed return verified:' in msg:
            if not starts or fixed or terminal or parked is not None:
                raise ValueError('invalid fixed-return order')
            m = re.search(r'vbus=(\d+)uV samples=(\d+) range=(\d+)\.\.(\d+)mV settled=(\d+)ms raw_ibus=0 pump_off=1$', msg)
            if not m:
                raise ValueError('fixed physical proof missing')
            vbus, count, low, high, settle = map(int, m.groups())
            if not 8550 <= low <= high <= 9450 or high-low > 100 or not low*1000 <= vbus <= high*1000 or count < 3 or settle < 100:
                raise ValueError('fixed physical bounds')
            fixed.append(stamp)
        elif 'one-shot pump complete:' in msg:
            m = re.search(r'lease=0 fixed_return=1 positive_samples=(\d+) no_restart=1$', msg)
            if not m or int(m[1]) <= 0 or not starts or not fixed or terminal or parked is not None:
                raise ValueError('invalid completion/charge proof')
            if stamp < starts[0][3]*1000 or stamp-starts[0][3]*1000 > 3000000:
                raise ValueError('completion deadline/cleanup latency')
            terminal.append(stamp)
    if terminal:
        if len(direct) != 1 or not 0 < starts[0][0]-direct[0] < 100000 or not 1 <= refreshes <= 7:
            raise ValueError('missing entry/refresh proof')
        return dict(target_mv=starts[0][1], target_ma=1800, deadline_ms=starts[0][3],
                    started_us=starts[0][0], completed_us=terminal[0], refreshes=refreshes,
                    fixed_return=True, pump_ON_observed=True, no_restart=True)
    if required:
        raise ValueError('native transaction incomplete')
    return None


def observe(hw, journal, emit, boot, clock=time.monotonic, sleep=time.sleep):
    began, seen_on, samples = clock(), False, 0
    primary=None
    try:
        rows = journal()
        while clock()-began < 280:
            proof = native_proof(rows, boot)
            sample = hw.sample()
            emit('sample', sample)
            samples += 1
            seen_on |= check_sample(sample)
            if proof:
                if not seen_on or sample['adc']['mode'] != 0 or sample['tcpm'].get('POWER_SUPPLY_ONLINE') != '1' or int(sample['tcpm']['POWER_SUPPLY_VOLTAGE_NOW']) != 9000000:
                    raise ValueError('no live pump sample or fixed endpoint')
                return dict(verdict='BOUNDED_NATIVE_RETURN_PASS', native=proof, samples=samples)
            sleep(.5)
            rows = journal()
        raise TimeoutError('bounded native completion missing')
    except Exception as exc:
        primary=exc
        emit('first-failure', dict(error=repr(exc)))
        raise
    finally:
        try:
            emit('cleanup', hw.stop())
        except Exception as cleanup:
            emit('cleanup-failure',dict(primary_error=repr(primary) if primary is not None else None,cleanup_error=repr(cleanup)))
            raise CleanupFailure(primary,cleanup) from primary


def run(plan, out):
    # Frozen identity gate before touching the provider/unbind interface.
    config = gzip.decompress(Path('/proc/config.gz').read_bytes())
    tokens = Path('/proc/cmdline').read_text().split()
    flag = plan['cmdline_flag']
    if tokens.count(flag) != 1:
        raise ValueError('unique one-shot opt-in missing')
    tokens.remove(flag)
    if tokens != plan['runtime_cmdline'].split() or hashlib.sha256(config).hexdigest() != plan['candidate_config_sha256'] or hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest() != plan['candidate_notes_sha256'] or Path('/etc/machine-id').read_text().strip() != plan['machine_id']:
        raise ValueError('candidate identity drift')
    params = Path('/sys/module/sm5440_fedora/parameters')
    if (params/'direct_charge_once').read_text().strip() != 'Y' or any((params/n).read_text().strip() != 'N' for n in ('direct_charge','fixed_return_check','pps_return_check')):
        raise ValueError('exclusive test mode')
    if b'# CONFIG_HVC_DCC is not set' not in config or Path('/dev/hvc0').exists() or Path('/sys/class/tty/hvc0').exists():
        raise ValueError('DCC restored')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip().replace('-','')
    if boot != plan['boot_id']:
        raise ValueError('boot identity changed')
    out.mkdir(exist_ok=False)
    stream = (out/'events.jsonl').open('x', buffering=1)
    lock = threading.Lock()
    def emit(kind, data):
        with lock:
            stream.write(json.dumps(dict(kind=kind,data=data))+'\n')
    hw = Hardware(boot)
    def full_journal():
        p = subprocess.run(['journalctl','-k','-b','-o','json','--no-pager'], capture_output=True, text=True, timeout=8)
        if p.returncode:
            raise ValueError('kernel journal collection failure')
        emit('full-journal',dict(raw=p.stdout))
        return [json.loads(x) for x in p.stdout.splitlines()]
    rows, errors, follower, feed_thread = [], [], None, None
    def journal():
        nonlocal rows, follower, feed_thread
        if follower is None:
            rows = full_journal()
            if not rows:
                raise ValueError('empty journal')
            follower = subprocess.Popen(['journalctl','-k','-b','-f','-o','json','--no-pager',
                '--after-cursor='+rows[-1]['__CURSOR']], stdout=subprocess.PIPE, text=True)
            def feed():
                try:
                    for line in follower.stdout:
                        row = json.loads(line)
                        with lock:
                            rows.append(row)
                        emit('kernel',row)
                except Exception as exc:
                    errors.append(repr(exc))
            feed_thread = threading.Thread(target=feed,daemon=True)
            feed_thread.start()
        if errors or follower.poll() is not None:
            raise ValueError('journal follower lost')
        with lock:
            return list(rows)
    def interrupted(signum, frame):
        raise RuntimeError('guardian interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    (out/'armed').write_text(boot)
    result = {}
    try:
        result = observe(hw, journal, emit, boot)
        native_proof(full_journal(),boot,required=True)
    except Exception as exc:
        result = dict(verdict='STOP_FIRST_NON_CLEAN', error=repr(exc),primary_error=getattr(exc,'primary_error',repr(exc)),cleanup_error=getattr(exc,'cleanup_error',None))
    finally:
        if follower is not None:
            follower.terminate()
            follower.wait(timeout=3)
            feed_thread.join(timeout=3)
        os.close(hw.fd)
        stream.close()
        (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        (out/'finished').write_text('finished')
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(run(json.loads(args.plan.read_text()), args.out)))
