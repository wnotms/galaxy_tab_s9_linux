"""Source-qualified exact negative compatibility replies, never arbitrary -5."""
import struct

UNIT = 'hexagonrpcd-adsp-sensorspd.service'
REGISTRY_REQUEST = dict(handle=0, scalars=0x00020200,
                       buffers_hex=[struct.pack('<II',13,255).hex(), b'sns_registry\0'.hex()],
                       output_capacities=[8,255])
PROPERTY_REQUEST = dict(handle=0xffffffff, scalars=0x00020100,
                       buffers_hex=[struct.pack('<II',12,200).hex(), b'ro.revision\0'.hex()],
                       output_capacities=[200])


def matches(request, expected):
    return request is not None and all(request.get(k)==v for k,v in expected.items())


def classify(frames, *, max_pairs=6):
    """Report only exact acknowledged localctl/property pairs in the sensor PD.

    Counts bound the Test401 observed six probes; this does not establish SSC
    parsing or make the frameworkless negative replies functional successes.
    The independent runner must separately require framing to be complete.
    """
    known, faults = [], []
    for stream in frames['streams']:
        registry = set()
        for call in stream['calls']:
            req = call.get('response_to')
            if req is None:
                continue
            if stream['unit'] != UNIT:
                continue
            seq = call['sequence']
            if matches(req, REGISTRY_REQUEST):
                if (call['status'] != 0xfffffffb or call['transport_return'] != 0
                        or call['returned_buffers_hex'] != [struct.pack('<II',0,0xfffffffb).hex(), (b'\0'*255).hex()]):
                    faults.append(dict(sequence=seq,reason='unexpected sns_registry negative reply'))
                else:
                    registry.add(seq)
                    known.append(dict(unit=UNIT,pid=stream['pid'],sequence=seq,
                                      kind='unregistered sns_registry interface',status=0xfffffffb))
            elif matches(req, PROPERTY_REQUEST):
                if (seq-1 not in registry or call['status'] != 20 or call['transport_return'] != 0
                        or call['returned_buffers_hex'] or call.get('error_output_omitted') is not True):
                    faults.append(dict(sequence=seq,reason='unexpected/unpaired ro.revision negative reply'))
                else:
                    known.append(dict(unit=UNIT,pid=stream['pid'],sequence=seq,
                                      kind='unregistered ro.revision handle',status=20))
        if len(registry)>max_pairs:
            faults.append(dict(reason='compatibility probe count exceeds registered bound',count=len(registry)))
        property_count=sum(x['pid']==stream['pid'] and x['kind']=='unregistered ro.revision handle'for x in known)
        if property_count!=len(registry):
            faults.append(dict(reason='incomplete registry/property negative pair',registry=len(registry),property=property_count))
    return dict(complete=not faults, known_negative_replies=known, faults=faults,
                max_pairs=max_pairs, interface_implemented=False, SSC_publication_proved=False)
