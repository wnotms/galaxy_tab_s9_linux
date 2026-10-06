#!/usr/bin/env python3
"""Device-local once-only PPS observer; bounded window, checked unbind in finally.

No register configuration/INT access/PD request exists here. The opt-in kernel
worker owns charging. This observer uses Fedora continuous ADC arithmetic.
"""
import argparse,ctypes as c,fcntl,json,os,re,selectors,signal,subprocess,time
from pathlib import Path
class Msg(c.Structure):
    _fields_=[('addr',c.c_uint16),('flags',c.c_uint16),('length',c.c_uint16),('buf',c.POINTER(c.c_uint8))]
class Transfer(c.Structure):
    _fields_=[('msgs',c.POINTER(Msg)),('nmsgs',c.c_uint32)]

def values(raw):return dict(x.split('=',1) for x in raw.splitlines() if '=' in x)
def decoded(regs):
    pair=lambda n:(regs[n]<<5)|(regs[n+1]>>3)
    return dict(mode=regs[0x10]&12,adc_enabled=bool(regs[0x1c]&1),vbus_mv=4096+pair(0x1e),ibus_ua=pair(0x22)*625,vbat_uv=2048000+pair(0x27)*500,die_decic=225+regs[0x26]*5)

def check(s,started):
    b=s['battery'];a=s['adc'];temp=int(b['POWER_SUPPLY_TEMP'])
    if b['POWER_SUPPLY_HEALTH']!='Good' or b['POWER_SUPPLY_PRESENT']!='1' or not 150<=temp<420 or not 3500000<=int(b['POWER_SUPPLY_VOLTAGE_NOW'])<4400000:raise ValueError('pack health/temperature/voltage')
    if int(b['POWER_SUPPLY_CAPACITY'])>=80:raise ValueError('SOC no longer eligible')
    if a['mode'] not in (0,4):raise ValueError('unexpected pump/reverse mode')
    if a['mode']==4:
        t=s['tcpm']
        if t.get('POWER_SUPPLY_ONLINE')!='2' or '[PD_PPS]' not in t.get('POWER_SUPPLY_USB_TYPE','') or int(t['POWER_SUPPLY_CURRENT_NOW'])!=1800000 or not 8200000<=int(t['POWER_SUPPLY_VOLTAGE_NOW'])<=10500000 or abs(a['vbus_mv']*1000-int(t['POWER_SUPPLY_VOLTAGE_NOW']))>500000:raise ValueError('physical/requested PPS contract mismatch')
        if not a['adc_enabled'] or not 7700<=a['vbus_mv']<=10500 or a['ibus_ua']>1800000 or not 3500000<=a['vbat_uv']<4400000 or a['die_decic']>=850:raise ValueError('physical ADC safety envelope')
    elif started and a['ibus_ua']>1800000:raise ValueError('pump OFF excessive current')
    # ADC values are meaningful only after kernel initialization, not at idle.
    return a['mode']==4

FAIL=re.compile(r'direct-charge start failed|fixed fallback failed|stopping direct charge|retained fault=|failed to refresh PPS|latched fault:|Kernel panic|soft lockup|rcu.*stall|CSD.*(?:stall|non-responsive)|\bOops:|\bBUG:|I2C.*(?:error|timeout)',re.I)
def fault(message):return bool(FAIL.search(message))

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
        t=values(source[0].read_text());usb=values(Path('/sys/class/power_supply/sm5714-usb/uevent').read_text())
        if t.get('POWER_SUPPLY_ONLINE')!='1' or '[PD_PPS]' in t.get('POWER_SUPPLY_USB_TYPE','') or int(t['POWER_SUPPLY_VOLTAGE_NOW'])!=9000000 or int(t['POWER_SUPPLY_CURRENT_MAX'])>1500000:raise ValueError('fixed9 not restored')
        if usb.get('POWER_SUPPLY_ONLINE')!='1' or '[PD_PPS]' in usb.get('POWER_SUPPLY_USB_TYPE','') or not 100000<=int(usb['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])<=1500000:raise ValueError('switching supply not restored')
        return dict(pump_mode=mode,driver_unbound=True,tcpm=t,usb=usb)

def observe(hw,journal,emit,clock=time.monotonic,sleep=time.sleep):
    began=clock();active=None;started=False;samples=0;start_events=0;off_since=None
    try:
        while clock()-began<240:
            events=journal()
            for event in events:
                emit('kernel',event)
                if fault(event['MESSAGE']):raise ValueError('first kernel charging fault: '+event['MESSAGE'])
                if 'direct charge started: PPS ' in event['MESSAGE']:
                    start_events+=1
                    if start_events>1:raise ValueError('unexpected second pump start')
                    if active is None:active=clock()
                    started=True
            sample=hw.sample();emit('sample',sample);samples+=1
            on=check(sample,started)
            if on and active is None:active=clock();started=True
            if started and not on:
                if off_since is None:off_since=clock()
                if clock()-off_since>2:raise ValueError('pump OFF outside bounded refresh')
            else:off_since=None
            if active is not None and clock()-active>=30:break
            sleep(.5)
        else:raise TimeoutError('no bounded PPS start/window')
        if not started:raise ValueError('no PPS/pump start')
        return dict(verdict='PPS_30S_OBSERVED',samples=samples,active_seconds=clock()-active)
    except Exception as exc:
        emit('first-failure',dict(error=str(exc)))
        raise
    finally:
        try:emit('cleanup',hw.stop())
        except Exception as exc:
            emit('cleanup-failure',dict(error=str(exc)))
            raise

def run(boot,out):
    out.mkdir(exist_ok=False);os.close(os.open(out/'exclusive',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600))
    stream=(out/'events.jsonl').open('w',buffering=1)
    def emit(kind,data):stream.write(json.dumps(dict(kind=kind,data=data))+'\n');stream.flush()
    hw=Hardware(boot)
    proc=subprocess.Popen(['journalctl','-k','-b','-n','0','-f','-o','json','--no-pager'],stdout=subprocess.PIPE)
    os.set_blocking(proc.stdout.fileno(),False);pending=b''
    def journal():
        nonlocal pending
        chunk=proc.stdout.read() or b'';pending+=chunk;events=[]
        while b'\n' in pending:
            line,pending=pending.split(b'\n',1)
            if line:events.append(json.loads(line))
        if proc.poll() is not None:raise ValueError('kernel stream ended')
        return events
    def interrupted(signum,frame):raise RuntimeError('guardian interrupted')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    (out/'armed').write_text(boot)
    result={}
    try:result=observe(hw,journal,emit);result['cleanup_verified']=True
    except Exception as exc:result=dict(verdict='STOP_FIRST_NON_CLEAN',error=str(exc),samples_evidence='events.jsonl')
    finally:
        proc.terminate();proc.wait(timeout=3);os.close(hw.fd);stream.close()
        (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        (out/'finished').write_text('finished')
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--boot',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();print(json.dumps(run(a.boot,a.out)))
