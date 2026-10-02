"""Strict one-call diagnostic cache decoder, no hardware/fresh charging grant."""
HEADER = dict(format='sm5440-passive-observer-v1', maximum_calls='1',
              collection_budget_ms='500', PPS_authorized='0', pump_ON_authorized='0',
              legacy_fresh_authorized='0', independently_calibrated='0')
FIELDS = {'row', 'request_ms', 'return_ms', 'provider_status', 'status',
          'diagnostic_valid', 'provider_request_ms', 'acquisition_ms', 'completed_ms',
          'provider_return_ms', 'oldest_age_ms', 'acquisition_seq', 'request_epoch',
          'raw_vbus_uv', 'raw_vbat_uv', 'raw_ibus_ua', 'raw_die_decic', 'raw_online'}
PROVIDER_FIELDS = FIELDS - {'row', 'request_ms', 'return_ms', 'provider_status',
                           'status', 'diagnostic_valid'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def observation(raw):
    header, rows = {}, []
    for line in raw.splitlines():
        if line.startswith('row='):
            pairs = [part.split('=', 1) for part in line.split()]
            require(all(len(p) == 2 for p in pairs) and len(pairs) == len(FIELDS)
                    and {p[0] for p in pairs} == FIELDS, 'row schema/duplicate')
            rows.append({key: int(value) for key, value in pairs})
        else:
            key, sep, value = line.partition('=')
            require(sep and key not in header, 'header malformed/duplicate')
            header[key] = value
    require(set(header) == set(HEADER) | {'state', 'count'} and
            all(header[k] == v for k, v in HEADER.items()), 'observer contract')
    state, count = int(header['state']), int(header['count'])
    require(count in (0, 1) and count == len(rows) and state in (0, 1, 2, 3),
            'state/count')
    require((state in (0, 3) and count == 0) or (state in (1, 2) and count == 1),
            'terminal/state row mismatch')
    result = dict(state=state, count=count, rows=rows, charging_authorized=False,
                  legacy_fresh_accepted=False, independently_calibrated=False,
                  ADC_duration_ms=None, outcome='INCOMPLETE')
    if not rows:
        return result
    row = rows[0]
    for key, value in row.items():
        if key in ('provider_status', 'status'):
            require(-4095 <= value <= 0, 'signed errno')
        elif key == 'raw_die_decic':
            require(-(2**31) <= value < 2**31, 'temperature width')
        else:
            limit = 2**32 if key in ('raw_vbus_uv', 'raw_vbat_uv', 'raw_ibus_ua') else 2**64
            require(0 <= value < limit, 'unsigned field width')
    require(row['row'] == 1 and row['request_ms'] > 0 and
            row['return_ms'] >= row['request_ms'], 'caller chronology')
    require(row['diagnostic_valid'] == int(row['status'] == 0) and
            ((state == 1 and row['status'] == 0) or (state == 2 and row['status'] < 0)),
            'status/diagnostic validity')
    result['delivery_ms'] = row['return_ms'] - row['request_ms']
    if row['provider_status']:
        require(row['status'] == row['provider_status'], 'provider refusal masked')
        require(all(row[k] == 0 for k in PROVIDER_FIELDS), 'failed provider output not cleared')
    if row['status']:
        result['outcome'] = 'PASSIVE_OBSERVATION_REFUSED'
        return result
    require(row['provider_status'] == 0 and result['delivery_ms'] <= 500,
            'diagnostic collection budget')
    require(row['request_ms'] <= row['provider_request_ms'] <= row['acquisition_ms']
            <= row['completed_ms'] <= row['provider_return_ms'] <= row['return_ms']
            and row['acquisition_seq'] > 0, 'provenance chronology/sequence')
    require(row['oldest_age_ms'] == row['provider_return_ms'] - row['acquisition_ms'],
            'reported age restamped/mismatch')
    require(row['raw_online'] == 1 and row['raw_ibus_ua'] == 0, 'passive online/OFF current')
    require(4500000 <= row['raw_vbus_uv'] <= 9500000 and
            3500000 <= row['raw_vbat_uv'] < 4300000 and
            225 <= row['raw_die_decic'] < 420, 'diagnostic sample bound')
    result.update(outcome='PASSIVE_OBSERVATION_VALID',
                  acquisition_to_software_completion_ms=row['completed_ms'] - row['acquisition_ms'],
                  provider_elapsed_ms=row['provider_return_ms'] - row['provider_request_ms'],
                  provider_oldest_age_ms=row['oldest_age_ms'],
                  consumer_oldest_age_ms=row['return_ms'] - row['acquisition_ms'])
    return result
