#!/usr/bin/env python3
"""Boot-bound SSC provisioning/one start; no remoteproc, USB or charging commands.

Qualified passive packages/account remain on a failed hardware scope, gated and
inactive. Deactivation removes the volatile gate before stopping owned units.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import time

PREFIX = Path('/usr/share/qcom/sm8550/Samsung/gts9wifi')
STATE = Path('/var/lib/gts9-ssc-test382/runtime.json')
GATE = Path('/run/gts9-ssc-test/ready')
UNITS = ('hexagonrpcd-adsp-rootpd.service', 'hexagonrpcd-adsp-sensorspd.service', 'iio-sensor-proxy.service')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.test382.tmp')
    with temporary.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    temporary.chmod(mode); os.replace(temporary, path)


def validate(d, plan):
    if (d['boot_id'] != plan['boot_id'] or d['machine_id'] != plan['machine_id'] or
        d['config_sha256'] != plan['candidate_config_sha256'] or d['notes_sha256'] != plan['candidate_notes_sha256'] or
        d['cmdline'] != plan['runtime_cmdline'] or not d['dcc_absent'] or d['direct_default'] not in ('N','0')):
        raise ValueError('live SSC identity/ordinary charging gate')
    b=d['battery']
    if (b['POWER_SUPPLY_HEALTH'] != 'Good' or b['POWER_SUPPLY_PRESENT'] != '1' or
        b['POWER_SUPPLY_VOLTAGE_MAX_DESIGN'] != '4440000' or not 20 <= int(b['POWER_SUPPLY_CAPACITY']) <= 100 or
        not 100 <= int(b['POWER_SUPPLY_TEMP']) < 420 or not plan['voltage_observation_min_uv'] <= int(b['POWER_SUPPLY_VOLTAGE_NOW']) <= plan['voltage_observation_max_uv']):
        raise ValueError('SSC battery safety gate')
    if (d['failed_units'] or d['services']['gdm']=='active' or len(d['adsp'])!=1 or
        d['adsp'][0]['state']!='running' or d['adsp'][0]['firmware']!='qcom/sm8550/adsp.mdt' or
        '/dev/fastrpc-adsp' not in d['fastrpc'] or d['native_socinfo']['boot_id'] != d['boot_id']):
        raise ValueError('early ADSP/text/health prerequisites')


class Runtime:
    def __init__(self, plan, snapshot, translate, root=Path('/'), invoke=None, start_rpc=None):
        self.plan,self.snapshot,self.translate,self.root=plan,snapshot,translate,root
        self.invoke=invoke or self.command
        self.start_rpc=start_rpc

    def path(self, name):
        p=self.root/str(name).lstrip('/')
        if not p.resolve().is_relative_to(self.root.resolve()) or p.is_symlink():
            raise ValueError('unsafe owned path')
        return p

    def command(self, argv, required=True, timeout=15):
        r=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
        if required and r.returncode:raise ValueError(str(argv)+': '+r.stderr)
        return r.stdout.strip()

    def save(self,state):atomic(self.path(STATE),(json.dumps(state,indent=2)+'\n').encode(),0o600)

    def check(self):
        d=self.snapshot();validate(d,self.plan);return d

    def package_status(self,name):
        value=self.invoke(['dpkg-query','-W','-f=${Version}\t${db:Status-Status}',name],required=False)
        return value if value else 'absent'

    def prepare(self, incoming, packages, overrides):
        d=self.check()
        if self.path(STATE).exists() or self.path(GATE).exists():
            raise ValueError('one provisioning only; inspect prior state')
        mapping=self.translate(d['native_socinfo'])
        if set(mapping)!=set(('soc_id','hw_platform','platform_subtype','platform_subtype_id','platform_version')):
            raise ValueError('native mapping set')
        if self.path(PREFIX/'socinfo').exists():raise ValueError('existing SoC copy; no overwrite')
        if set(x['package'] for x in packages)!=set(('libprotobuf-c1','libssc2','gts9-hexagonrpc','iio-sensor-proxy')):
            raise ValueError('unexpected package/duplicate mapper')
        archives=[]
        for row in packages:
            path=incoming/row['filename']
            if path.is_symlink() or path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
                raise ValueError('qualified archive mismatch')
            value=self.package_status(row['package'])
            if value not in ('absent',row['version']+'\tnot-installed',row['version']+'\tinstalled','\tnot-installed','not-installed'):
                raise ValueError('preexisting different package')
            for name,expected in row['payload_files'].items():
                p=self.path(name)
                if p.exists() and (not p.is_file() or sha(p)!=expected):
                    raise ValueError('preexisting different payload: '+name)
            for name,expected in row['payload_links'].items():
                p=self.root/name
                if p.exists() or p.is_symlink():
                    if not p.is_symlink() or os.readlink(p)!=expected:raise ValueError('preexisting package link')
            archives.append(str(path))
        allowed={f'etc/systemd/system/{u}.d/90-gts9-controlled-test.conf' for u in UNITS+('hexagonrpcd-sdsp.service',)}
        if set(overrides)!=allowed:raise ValueError('unexpected runtime unit')
        for name,data in overrides.items():
            p=self.path(name)
            if p.exists() and p.read_text()!=data:raise ValueError('different existing override')
        state=dict(schema=1,test='Test382',machine_id=self.plan['machine_id'],boot_id=self.plan['boot_id'],phase='provisioning',started=False,
                   packages=[x['package'] for x in packages],qualified_passive_packages_retained=True)
        self.save(state)
        # Gates precede package exposure; no service enablement/auto-start scripts.
        if any(not self.path(name).exists() for name in overrides):
            raise ValueError('existing closed runtime gates required')
        try:
            # Exact passive packages already installed: no unpack/configure/start.
            if any(self.package_status(x['package']) != x['version']+'\tinstalled' for x in packages):
                raise ValueError('requires qualified installed passive packages')
            for row in packages:
                if self.package_status(row['package'])!=row['version']+'\tinstalled':raise ValueError('package configuration incomplete')
                for name,expected in row['payload_files'].items():
                    if sha(self.path(name))!=expected:raise ValueError('installed payload hash')
            self.invoke(['systemd-sysusers','/usr/lib/sysusers.d/gts9-fastrpc.conf'])
            account=pwd.getpwnam('fastrpc')
            if account.pw_uid==0 or account.pw_gid==0 or account.pw_shell!='/usr/sbin/nologin':raise ValueError('unsafe fastrpc account')
            sensors=self.path(PREFIX/'sensors')
            if not sensors.is_dir():raise ValueError('isolated sensor registry missing')
            for p in [sensors,*sensors.rglob('*')]:
                if p.is_symlink():raise ValueError('copied registry symlink')
                os.chown(p,account.pw_uid,account.pw_gid)
            soc=self.path(PREFIX/'socinfo');soc.mkdir()
            for n,data in mapping.items():atomic(soc/n,data.encode())
            node=self.path('/dev/fastrpc-adsp');s=node.stat()
            if not stat.S_ISCHR(s.st_mode):raise ValueError('FastRPC device missing')
            state['fastrpc_original']=dict(uid=s.st_uid,gid=s.st_gid,mode=stat.S_IMODE(s.st_mode),rdev=s.st_rdev)
            os.chown(node,0,account.pw_gid);node.chmod(0o660)
            self.invoke(['systemctl','daemon-reload'])
            self.check()
            state.update(phase='prepared-inactive',native_mapping=mapping,account_uid=account.pw_uid,account_gid=account.pw_gid)
            self.save(state)
            return state
        except Exception as exc:
            self.path(GATE).unlink(missing_ok=True)
            state.update(phase='provisioning-stopped',error=str(exc));self.save(state)
            raise

    def start(self):
        self.check();state=json.loads(self.path(STATE).read_text())
        if state.get('phase')!='prepared-inactive' or state['boot_id']!=self.plan['boot_id'] or state['started']:
            raise ValueError('one runtime start only')
        trace=self.path('/usr/local/lib/gts9-test382/hexagonrpcd')
        library=self.path('/usr/lib/aarch64-linux-gnu/libhexagonrpc.so.0.4')
        if (sha(trace)!=self.plan['trace_sha256'] or sha(library)!=self.plan['trace_library_sha256'] or
            not self.path('/usr/bin/stdbuf').is_file()):
            raise ValueError('qualified trace or library missing/altered')
        for unit in UNITS[:-1]:
            command=self.invoke(['systemctl','show',unit,'-p','ExecStart','--value'])
            if '/usr/bin/stdbuf' not in command or '/usr/local/lib/gts9-test382/hexagonrpcd' not in command:
                raise ValueError('resolved unit is not isolated line-buffered trace')
        if self.start_rpc is None:
            raise ValueError('qualified RPC lifecycle helper missing')
        self.path(GATE).parent.mkdir(parents=True,exist_ok=True)
        atomic(self.path(GATE),(self.plan['boot_id']+'\n').encode(),0o600)
        # Persist before launch: a lost reply is not permission for another start.
        state['proxy_started']=False
        return self.start_rpc(self.invoke,state,self.save)

    def start_proxy(self):
        self.check();state=json.loads(self.path(STATE).read_text())
        if state.get('phase')!='start-requested' or state.get('proxy_started') or state['boot_id']!=self.plan['boot_id']:
            raise ValueError('proxy start only after sensor service launch')
        # The host requires a real parsed accelerometer sample before this call.
        state.update(proxy_started=True,phase='proxy-start-requested');self.save(state)
        self.invoke(['systemctl','start','--no-block',UNITS[-1]])
        return state

    def deactivate(self):
        state=json.loads(self.path(STATE).read_text())
        if state.get('test')!='Test382' or state.get('machine_id')!=self.plan['machine_id']:
            raise ValueError('unqualified cleanup state')
        self.path(GATE).unlink(missing_ok=True)
        self.invoke(['systemctl','stop',*reversed(UNITS)],timeout=15)
        for unit in UNITS:
            if self.invoke(['systemctl','is-active',unit],required=False) not in ('inactive','failed','unknown'):
                raise ValueError('runtime stop not confirmed')
        state.update(phase='inactive-gated',gate_removed=True);self.save(state)
        return state


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','start','start-proxy','deactivate'))
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--incoming',type=Path,required=True)
    a=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('runtime operation requires root')
    cap=load('ssc372_capture',a.incoming/'capture.py')
    mapper=load('ssc372_mapper',a.incoming/'map-socinfo.py')
    lifecycle=load('ssc378_lifecycle',a.incoming/'ssc_lifecycle.py')
    runner=Runtime(json.loads(a.plan.read_text()),cap.capture,mapper.translate,start_rpc=lifecycle.start_rpc)
    if a.mode=='prepare':d=runner.prepare(a.incoming,json.loads((a.incoming/'runtime-packages.json').read_text()),json.loads((a.incoming/'runtime-overrides.json').read_text()))
    elif a.mode=='start':d=runner.start()
    elif a.mode=='start-proxy':d=runner.start_proxy()
    else:d=runner.deactivate()
    print(json.dumps(d,indent=2))
