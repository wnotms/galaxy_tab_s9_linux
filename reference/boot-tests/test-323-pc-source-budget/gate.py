#!/usr/bin/env python3
"""Pure PC source-budget evidence admission; no device mutation."""
import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('historical311_gate',Path(__file__).resolve().parent.parent/'test-311-serial-device-acceptance/gate.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
values=old.values
program_history=old.program_history

def battery_entry(raw):
    result=old.battery_entry(raw)
    if result['soc']<20: raise ValueError('flash reserve below20%')
    return result

def source_budget(tcpm):
    v=values(tcpm)
    if v.get('POWER_SUPPLY_ONLINE')!='1' or '[PD_PPS]' in v.get('POWER_SUPPLY_USB_TYPE',''):
        raise ValueError('source offline/PPS')
    if int(v['POWER_SUPPLY_VOLTAGE_NOW'])!=5000000 or int(v['POWER_SUPPLY_VOLTAGE_MAX'])!=5000000:
        raise ValueError('not fixed5V')
    ma=int(v['POWER_SUPPLY_CURRENT_MAX'])
    if not 100000<=ma<=3000000 or ma%1000: raise ValueError('invalid source grant')
    return min(ma//1000,1800)

def program_controls(raw,boot,budget):
    data=json.loads(raw)
    # Reuse all old provider/boot/read-only/fault/Q4/float checks unchanged.
    # Normalize only the two fields whose allowed targets this test changes.
    regs=data['stable_registers']
    if any(not 0 <= int(v,0) <= 255 for v in regs.values()): raise ValueError('invalid original register byte')
    input_code=int(regs['0x15'],0)&127;fast=int(regs['0x18'],0)
    if not 100<=budget<=1800: raise ValueError('invalid capped budget')
    if input_code>(budget-100)//25: raise ValueError('input exceeds source/board ceiling')
    expected_fast=7+(max(500,budget)*1000-109375)//15625
    if fast!=expected_fast: raise ValueError('pack charging target differs from grant')
    normalized=dict(data,stable_registers=dict(regs,**{'0x15':hex(min(input_code,16)),'0x18':'0x20'}))
    old.program_controls(json.dumps(normalized),boot)
    return dict(verdict='SOURCE_AUTHORIZED_PC_CONTROLS_VERIFIED',boot_id=boot,input_limit_ma=100+input_code*25,source_budget_ma=budget,fast_code=fast,float_code=int(regs['0x1a'],0)&63,AICL_lower_limit_allowed=True,pump_ON=False,PPS=False)


def debian_ready(sections, status):
    import re
    return (status == 0 and sections.get('services','').splitlines()==['active']*3
            and 'usb0    inet 169.254.42.1/' in sections.get('network','')
            and re.search(r'\bwlp1s0\s+inet\s+\d+\.\d+\.\d+\.\d+/', sections.get('network','')) is not None)
