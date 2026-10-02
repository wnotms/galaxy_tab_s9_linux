"""Frozen pure Test275 observer gate, AST-identical; no device dependency."""
HEADER = dict(format='sm5440-fresh-observer-v1', maximum_calls='8', interval_ms='1000', PPS_authorized='0', pump_ON_authorized='0', independently_calibrated='0')
FIELDS = {'row', 'request_ms', 'return_ms', 'provider_status', 'status', 'usable', 'acquisition_ms', 'raw_vbus_uv', 'raw_vbat_uv', 'raw_ibus_ua', 'raw_die_decic', 'raw_online'}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def observer(raw):
    header, rows = ({}, [])
    for line in raw.splitlines():
        if line.startswith('row='):
            pairs = [x.split('=', 1) for x in line.split()]
            require(len(pairs) == len(FIELDS) and {x[0] for x in pairs} == FIELDS, 'row fields')
            rows.append({k: int(v) for k, v in pairs})
        else:
            k, sep, v = line.partition('=')
            require(sep and k not in header, 'header malformed/duplicate')
            header[k] = v
    require(set(header) == set(HEADER) | {'state', 'count'} and all((header[k] == v for k, v in HEADER.items())), 'observer contract')
    state, count = (int(header['state']), int(header['count']))
    require(state in (0, 1, 2, 3) and 0 <= count <= 8 and (count == len(rows)), 'state/count')
    failures = []
    for i, row in enumerate(rows, 1):
        require(row['row'] == i and row['request_ms'] > 0 and (row['return_ms'] >= row['request_ms']), 'row chronology')
        if i > 1:
            require(row['request_ms'] >= rows[i - 2]['return_ms'] + 1000, 'call interval')
        require(row['provider_status'] <= 0 and row['status'] <= 0 and (row['usable'] == int(row['status'] == 0)), 'signed status/usable')
        if row['provider_status']:
            require(row['status'] == row['provider_status'], 'provider refusal masked')
        if row['status']:
            failures.append(i)
            require(i == count and state == 2, 'request after first refusal')
        else:
            require(row['provider_status'] == 0 and row['return_ms'] - row['request_ms'] <= 100, 'delivery deadline')
            require(row['request_ms'] <= row['acquisition_ms'] <= row['return_ms'] and row['return_ms'] - row['acquisition_ms'] <= 100, 'fresh acquisition')
            require(row['raw_online'] == 1 and row['raw_ibus_ua'] == 0, 'OFF sample')
            require(4500000 <= row['raw_vbus_uv'] <= 5500000 and 3500000 <= row['raw_vbat_uv'] < 4300000 and (225 <= row['raw_die_decic'] < 420), 'sample bound')
    require((state != 1 or count == 8) and (state != 2 or failures), 'terminal state inconsistent')
    durations = [r['return_ms'] - r['request_ms'] for r in rows if r['status'] == 0]
    return dict(state=state, count=count, rows=rows, first_refusal=failures[0] if failures else None, successful_calls=len(durations), delivery_ms_min=min(durations, default=None), delivery_ms_max=max(durations, default=None), acquisition_outcome='REFUSED' if failures else 'EIGHT_FRESH_DELIVERIES' if state == 1 else 'INCOMPLETE', independently_calibrated=False, charging_authorized=False)
