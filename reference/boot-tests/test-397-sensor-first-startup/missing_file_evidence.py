"""Inspect attributed, acknowledged callback status; never infer DSP parsing."""
EXPECTED = ['12000000020000000d00000003000000',
            '414453505f4c4942524152595f5041544800', '3b00',
            '6f656d636f6e6669672e736f00', '726200']


def inspect(frames):
    if not frames.get('complete'):
        raise ValueError('incomplete RPC framing')
    observed = []
    for stream in frames['streams']:
        for call in stream['calls']:
            request = call.get('response_to')
            if request is None:  # Initial listener handshake has no callback.
                continue
            is_target = (stream['unit'] == 'hexagonrpcd-adsp-sensorspd.service' and
                         request.get('handle') == 1 and
                         request.get('scalars') == 0x13050100 and
                         request.get('buffers_hex') == EXPECTED and
                         request.get('output_capacities') == [4])
            if is_target:
                if call['status'] != 69 or call['transport_return'] != 0:
                    raise ValueError('missing-file status was not acknowledged ENOSUCHFILE69')
                observed.append(dict(sequence=call['sequence'], pid=stream['pid'],
                                     status=call['status'], transport_return=0))
            elif call['status'] != 0:
                raise ValueError('unexpected failed RPC callback')
    if len(observed) != 1:
        raise ValueError('missing-file callback attribution absent or duplicated')
    return dict(verdict='ONE_ACKNOWLEDGED_MISSING_FILE_STATUS69',
                boot_id=frames['boot_id'], calls=observed,
                DSP_parsing_proved=False, SSC_causality_proved=False)
