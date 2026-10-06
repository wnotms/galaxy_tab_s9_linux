#!/usr/bin/env python3
"""Single read-only Wi-Fi observer; kernel one-shot owns all hardware writes."""
import gzip,hashlib,json,os,re,subprocess,sys,threading,time
from pathlib import Path
BOOT=sys.argv[1];CONFIG=sys.argv[2];NOTES=sys.argv[3]
FAULT=re.compile(r'\b(?:Kernel panic|BUG:|Oops:|Internal error:|SError|soft lockup|hard LOCKUP|rcu.*(?:detected.*stall|INFO:.*stall)|blocked for more than|non-responsive|workqueue lockup|CSD.*(?:stall|non.response))',re.I)
rows=[];lock=threading.Lock();emit_lock=threading.Lock();journal=None

def emit(kind,**d):
    with emit_lock:print(json.dumps(dict(kind=kind,**d)),flush=True)
def text(p):return Path(p).read_text().strip()
def values(p):return dict(x.split('=',1) for x in text(p).splitlines() if '=' in x)
def capture_pump():
    import ctypes as c,fcntl
    class Msg(c.Structure):_fields_=[('addr',c.c_uint16),('flags',c.c_uint16),('length',c.c_uint16),('buf',c.POINTER(c.c_uint8))]
    class Transfer(c.Structure):_fields_=[('msgs',c.POINTER(Msg)),('nmsgs',c.c_uint32)]
    node=Path('/sys/bus/i2c/devices/0-0063')
    if (node/'driver').resolve().name!='sm5440-fedora':raise ValueError('pump provider')
    fd=os.open('/dev/i2c-0',os.O_RDWR)
    try:
        pointer=(c.c_uint8*1)(16);out=(c.c_uint8*1)();msgs=(Msg*2)(Msg(0x63,0,1,pointer),Msg(0x63,1,1,out))
        fcntl.ioctl(fd,0x0707,Transfer(msgs,2));return int(out[0])
    finally:os.close(fd)
def feed():
    for line in journal.stdout:
        try:r=json.loads(line)
        except ValueError:continue
        with lock:rows.append(r)
        emit('kernel',row=r)

def sample():
    boot=text('/proc/sys/kernel/random/boot_id').replace('-','')
    if boot!=BOOT:raise ValueError('unexplained boot')
    if text('/sys/module/sm5440_fedora/parameters/direct_charge') not in ('N','0') or text('/sys/module/sm5440_fedora/parameters/fixed_return_check') not in ('Y','1'):raise ValueError('OFF-only flags')
    b=values('/sys/class/power_supply/sm5714-battery/uevent');u=values('/sys/class/power_supply/sm5714-usb/uevent')
    ps=list(Path('/sys/class/power_supply').glob('tcpm-source-psy-*/uevent'))
    if len(ps)!=1:raise ValueError('TCPM supply identity')
    p=values(ps[0]);pump=capture_pump()
    if pump&12:raise ValueError('pump unexpectedly ON')
    if b.get('POWER_SUPPLY_HEALTH')!='Good' or b.get('POWER_SUPPLY_PRESENT')!='1':raise ValueError('battery health')
    if not 20<=int(b['POWER_SUPPLY_CAPACITY'])<80 or not 3500000<=int(b['POWER_SUPPLY_VOLTAGE_NOW'])<4300000 or not 200<=int(b['POWER_SUPPLY_TEMP'])<380:raise ValueError('registered pack bounds')
    if p.get('POWER_SUPPLY_ONLINE') not in ('0','1'):raise ValueError('unexpected PPS/AVS contract')
    if p.get('POWER_SUPPLY_ONLINE')=='1' and int(p['POWER_SUPPLY_VOLTAGE_NOW']) not in (5000000,9000000):raise ValueError('unsupported fixed voltage')
    if p.get('POWER_SUPPLY_ONLINE')=='1' and int(p['POWER_SUPPLY_VOLTAGE_NOW'])==9000000:
        if text('/sys/class/typec/port0/power_role')!='[sink]' or text('/sys/class/typec/port0/data_role')!='[device]':raise ValueError('unexpected Type-C role')
    d=dict(boot=boot,uptime=float(text('/proc/uptime').split()[0]),monotonic=time.monotonic(),battery=b,usb=u,tcpm=p,pump=pump,config_data_written=False)
    emit('sample',**d);return d

try:
    if hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest()!=CONFIG or hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest()!=NOTES:raise ValueError('candidate identity')
    journal=subprocess.Popen(['journalctl','-k','-b','-f','--no-pager','-o','json','--lines=all'],stdout=subprocess.PIPE,text=True)
    thread=threading.Thread(target=feed,daemon=True);thread.start()
    initial=sample();start=time.monotonic();complete_at=None;emit('armed',boot=BOOT,wait_seconds=240,observation_seconds=30)
    while True:
        if time.monotonic()-start>270:raise TimeoutError('bounded observation')
        d=sample()
        with lock:messages=[str(x.get('MESSAGE','')) for x in rows]
        if any(FAULT.search(m) or 'fixed return check failed:' in m or 'fixed fallback failed:' in m for m in messages):raise ValueError('first kernel/check fault')
        if complete_at is None and any('fixed return check complete: lease=0 PPS=0 pump_ON=0' in m for m in messages):complete_at=time.monotonic()
        if complete_at is None and time.monotonic()-start>240:raise TimeoutError('fixed proof did not complete')
        if complete_at is not None:
            if d['tcpm'].get('POWER_SUPPLY_ONLINE')!='1' or int(d['tcpm']['POWER_SUPPLY_VOLTAGE_NOW'])!=9000000:raise ValueError('fixed9 contract lost after proof')
            if time.monotonic()-complete_at>=30:
                if d['usb'].get('POWER_SUPPLY_ONLINE')!='1' or '[PD]' not in d['usb'].get('POWER_SUPPLY_USB_TYPE','') or not 100000<=int(d['usb']['POWER_SUPPLY_INPUT_CURRENT_LIMIT'])<=1500000 or int(d['battery']['POWER_SUPPLY_CURRENT_NOW'])<=0:raise ValueError('ordinary switching charge did not recover')
                emit('verdict',verdict='PASS',boot=BOOT,observation_seconds=time.monotonic()-complete_at,endpoint=d,PPS=False,pump_ON=False);break
        time.sleep(1)
except BaseException as e:
    emit('verdict',verdict='FAIL',boot=BOOT,error=repr(e),stopped=True,PPS=False,pump_ON=False);sys.exit(1)
finally:
    if journal is not None:
        journal.terminate()
        try:journal.wait(timeout=2)
        except subprocess.TimeoutExpired:journal.kill();journal.wait()
    # Complete boot journal is primary evidence, including source timestamps.
    try:
        p=subprocess.run(['journalctl','-k','-b','--no-pager','-o','json'],capture_output=True,text=True,timeout=10)
        emit('complete-journal',returncode=p.returncode,data=p.stdout,stderr=p.stderr)
    except Exception as e:emit('journal-failure',error=repr(e))
