"""Decode source-defined bus transactions; never infer exact ADC duration.

I2C timestamps enclose software/core/transfer/scheduling overhead. They are not
on-wire timing or exact register-sampling instants. Completed-but-late samples
do not authorize a request, charging or a change to the frozen 100ms contract.
"""
import re

from analyse import records as frozen_records, require
from phase_collector import I2C_EVENTS

LINE = re.compile(r'\s*.+-(\d+)\s+\[(\d+)\]\s+(?:\S+\s+)?'
                  r'(\d+)\.(\d{6,9}):\s+(\w+):\s*(.*)')
MESSAGE = re.compile(r'i2c-(\d+) #(\d+) a=([0-9a-f]{3}) f=([0-9a-f]{4}) l=(\d+)'
                     r'(?: \[([0-9a-f-]*)\])?')
RESULT = re.compile(r'i2c-(\d+) n=(\d+) ret=(-?\d+)')


def records(raw, names):
    require(raw.endswith('\n'), 'truncated trace')
    rows = []
    for line in raw.splitlines():
        if line.startswith('#'):
            continue
        match = LINE.fullmatch(line)
        require(match is not None, 'malformed/unrecognized trace record')
        pid, cpu, sec, frac, event, data = match.groups()
        stamp = int(sec) * 10**9 + int(frac.ljust(9, '0'))
        require(not rows or stamp >= rows[-1]['ns'], 'clock reversal/unordered records')
        if event not in I2C_EVENTS:
            row = frozen_records(line + '\n', names)[0]
        else:
            row = dict(ns=stamp, pid=int(pid), cpu='cpu' + str(int(cpu)), event=event)
            payload = (RESULT if event == 'i2c_result' else MESSAGE).fullmatch(data)
            require(payload is not None, 'malformed I2C payload')
            row['adapter'] = int(payload[1])
            require(row['adapter'] == 0, 'wrong I2C adapter')
            if event == 'i2c_result':
                row.update(nr=int(payload[2]), ret=int(payload[3]))
                require(1 <= row['nr'] <= 65535 and -32768 <= row['ret'] <= row['nr'],
                        'I2C result range')
            else:
                row.update(msg=int(payload[2]), addr=int(payload[3], 16),
                           flags=int(payload[4], 16), length=int(payload[5]))
                require(0 <= row['msg'] < 65535 and 0 < row['length'] <= 65535,
                        'I2C message range')
                has_data = event in ('i2c_write', 'i2c_reply')
                require((payload[6] is not None) == has_data, 'I2C buffer presence')
                if has_data:
                    values = payload[6].split('-')
                    require(len(values) == row['length'] and
                            all(re.fullmatch('[0-9a-f]{2}', value) for value in values),
                            'I2C buffer length/encoding')
                    row['data'] = [int(value, 16) for value in values]
        rows.append(row)
    require(rows, 'empty trace')
    return rows


def transactions(rows):
    """One source-defined __i2c_transfer stream, inside one matched worker."""
    pending, completed = [], []
    for row in rows:
        event = row['event']
        if event in ('i2c_write', 'i2c_read'):
            require(not any(r['event'] == 'i2c_reply' for r in pending),
                    'new message before transfer result')
            messages = [r for r in pending if r['event'] in ('i2c_write', 'i2c_read')]
            require(row['msg'] == len(messages), 'I2C missing/duplicate message')
            require(row['addr'] == 0x63 and row['flags'] == int(event == 'i2c_read'),
                    'worker foreign address/unsupported flags')
            pending.append(row)
        elif event == 'i2c_reply':
            originals = [r for r in pending if r['event'] == 'i2c_read' and r['msg'] == row['msg']]
            require(len(originals) == 1 and not any(r['event'] == 'i2c_reply' and
                    r['msg'] == row['msg'] for r in pending), 'I2C unpaired/duplicate reply')
            require(all(row[k] == originals[0][k] for k in ('pid', 'adapter', 'addr', 'flags', 'length')),
                    'I2C reply identity')
            pending.append(row)
        else:
            require(event == 'i2c_result' and pending, 'I2C result without messages')
            messages = [r for r in pending if r['event'] in ('i2c_write', 'i2c_read')]
            replies = [r for r in pending if r['event'] == 'i2c_reply']
            require(row['nr'] == len(messages) and
                    all(r['pid'] == row['pid'] for r in pending), 'I2C transfer identity/count')
            require({r['msg'] for r in replies} == {r['msg'] for r in messages
                    if r['event'] == 'i2c_read' and r['msg'] < row['ret']}, 'I2C missing/excess reply')
            require(messages[0]['event'] == 'i2c_write', 'I2C register pointer absent')
            transfer = dict(start_ns=messages[0]['ns'], end_ns=row['ns'],
                            wall_ns=row['ns'] - messages[0]['ns'], messages=messages,
                            replies=replies, result=row)
            if row['ret'] != row['nr']:
                transfer.update(kind='error', register=messages[0]['data'][0])
            elif len(messages) == 1 and messages[0]['length'] == 2:
                transfer.update(kind='write', register=messages[0]['data'][0],
                                data=messages[0]['data'][1:])
            elif len(messages) == 2 and messages[0]['length'] == 1 and messages[1]['event'] == 'i2c_read':
                transfer.update(kind='read', register=messages[0]['data'][0], data=replies[0]['data'])
            else:
                raise ValueError('unsupported worker register transaction')
            completed.append(transfer)
            pending = []
    require(not pending and completed, 'I2C worker transfer missing/incomplete')
    return completed


def cycle(transfers):
    """Match the frozen sample_once recipe, not guessed elapsed/poll counts."""
    failures = [t for t in transfers if t['kind'] == 'error']
    if failures:
        require(len(failures) == 1 and failures[0] is transfers[-1], 'I2C activity after failure')
        return dict(verdict='I2C_FAILURE_OBSERVED', transfers=transfers,
                    first_transfer_failure=failures[0], adc_duration_ns=None,
                    hardware_acceptance=False)
    index = 0
    def take(kind, register, length):
        nonlocal index
        require(index < len(transfers), 'incomplete passive sequence')
        t = transfers[index]; index += 1
        require(t['kind'] == kind and t['register'] == register and len(t['data']) == length,
                'unexpected passive register sequence')
        return t
    def rmw(mask, value):
        old = take('read', 0x1c, 1)
        target = (old['data'][0] & ~mask) | value
        wrote = None
        if target != old['data'][0]:
            wrote = take('write', 0x1c, 1)
            require(wrote['data'] == [target], 'ADC masked write disagreement')
        return old, wrote, target
    before = take('read', 0x10, 1)
    require(before['data'][0] & 0x0c == 0, 'pump was not OFF')
    take('read', 0x00, 4)
    rmw(0x03, 0)  # Disable ADC + rate before consuming post-disable latch.
    after_disable = take('read', 0x03, 1)
    channels = take('write', 0x1d, 1)
    require(channels['data'] == [0xdf], 'ADC channel setting changed')
    old, enable, target = rmw(0x09, 0x09)
    require(old['data'][0] & 0x03 == 0 and target & 0x03 == 1 and enable is not None,
            'one-shot enable edge unproved')
    polls = []
    while index < len(transfers) and transfers[index]['register'] == 0x03:
        polls.append(take('read', 0x03, 1))
        require(len(polls) <= 12, 'ADC poll bound')
        if polls[-1]['data'][0] & 1:
            break
    require(polls and polls[-1]['data'][0] & 1, 'ADC ready not observed')
    adc = take('read', 0x1e, 11)
    status = take('read', 0x08, 4)
    after = take('read', 0x10, 1)
    require(after['data'][0] & 0x0c == 0, 'pump became active')
    protection = {hex(reg): take('read', reg, 1)['data'][0] for reg in (0x0d, 0x13, 0x14, 0x19)}
    require(protection == {'0xd': 0xf2, '0x13': 0xe7, '0x14': 0x37, '0x19': 0xfe},
            'passive protections changed')
    require(index == len(transfers), 'extra worker register activity')
    gaps = [b['start_ns'] - a['end_ns'] for a, b in zip(transfers, transfers[1:])]
    require(all(g >= 0 for g in gaps), 'overlapping I2C transfer envelopes')
    return dict(verdict='PASSIVE_SINGLE_SHOT_SEQUENCE_OBSERVED', transfers=transfers,
                poll_count=len(polls), poll_values=[p['data'][0] for p in polls],
                post_disable_latch=after_disable['data'][0], enable_write=enable,
                last_notready_poll=polls[-2] if len(polls) > 1 else None,
                first_ready_poll=polls[-1], adc_read=adc, status_read=status,
                protection=protection, mode_before=before['data'][0], mode_after=after['data'][0],
                enable_call_to_ready_reply_wall_ns=polls[-1]['replies'][0]['ns'] - enable['start_ns'],
                transaction_wall_ns_sum=sum(t['wall_ns'] for t in transfers),
                between_transaction_wall_ns_sum=sum(gaps), adc_duration_ns=None,
                hardware_acceptance=False,
                limitations=['register sampling instant within transfer is not captured',
                             'I2C envelopes include scheduling/core/tracing; not on-wire time',
                             'inter-transfer gaps include sleeps/locks/scheduling; not ADC duration'])


def phases(rows, workers):
    assigned, result = set(), []
    for worker in workers:
        selected = [(i, r) for i, r in enumerate(rows) if r['event'] in I2C_EVENTS and
                    r['pid'] == worker['pid'] and worker['poll_entry_ns'] <= r['ns'] <= worker['poll_return_ns']]
        require(not assigned.intersection(i for i, _ in selected), 'ambiguous I2C worker assignment')
        assigned.update(i for i, _ in selected)
        result.append(dict(worker=worker, phase=cycle(transactions([r for _, r in selected]))))
    return dict(workers=result, unassigned_background_i2c_records=sum(
                r['event'] in I2C_EVENTS and i not in assigned for i, r in enumerate(rows)),
                adc_duration_ns=None, hardware_acceptance=False)
