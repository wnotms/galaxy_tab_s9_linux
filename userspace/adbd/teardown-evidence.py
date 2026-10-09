"""Host-only attribution of the pinned FunctionFS/DWC3 empty ep0 cleanup path.

Never silence a device log. Allow at most one exact diagnostic per recorded
owned unbind, within250ms in kernel/helper source monotonic time. All other
errors remain failures. This does not classify errors on a healthy live link.
"""
import json
import math
import re


MESSAGE=re.compile(r'^dwc3-qcom a600000\.usb: request [0-9a-f]{16} was not queued to ep0out$')


def classify(rows, before, unit_journal, boot, unit):
    old={row['__CURSOR'] for row in before}
    events=[]
    for line in unit_journal.splitlines():
        row=json.loads(line)
        message=row.get('MESSAGE','')
        if not message.startswith('{'):
            continue
        packet=json.loads(message)
        if (row.get('_BOOT_ID')!=boot.replace('-','') or row.get('_SYSTEMD_UNIT')!=unit or
                packet.get('boot_id')!=boot or packet.get('event') not in ('bind','unbind') or
                not isinstance(packet.get('monotonic'),(int,float)) or isinstance(packet['monotonic'],bool) or
                not math.isfinite(packet['monotonic']) or packet['monotonic']<=0):
            raise ValueError('owned teardown event attribution missing')
        if packet['event']=='unbind':
            events.append(packet['monotonic'])
    if len(set(events))!=len(events):
        raise ValueError('duplicate owned unbind event')
    used=set()
    classified=[]
    for row in rows:
        if row['__CURSOR'] in old or int(row['PRIORITY'])>3:
            continue
        if row['PRIORITY']!='3' or not MESSAGE.fullmatch(row['MESSAGE']):
            raise ValueError('new unclassified kernel error')
        # Receipt/wall-clock timestamps cannot replace kernel source time.
        source=row.get('_SOURCE_MONOTONIC_TIMESTAMP')
        if not isinstance(source,str) or not source.isdigit() or row.get('_BOOT_ID')!=boot.replace('-',''):
            raise ValueError('kernel teardown source timestamp missing')
        stamp=int(source)/1e6
        candidates=[i for i,event in enumerate(events) if abs(stamp-event)<=.25]
        if len(candidates)!=1 or candidates[0] in used:
            raise ValueError('unbounded/ambiguous/repeated ep0 diagnostic')
        used.add(candidates[0])
        classified.append(dict(cursor=row['__CURSOR'],message=row['MESSAGE'],
                               source_monotonic=stamp,unbind_monotonic=events[candidates[0]],
                               classification='source-explained empty ep0 teardown; pending transport gate'))
    return classified
