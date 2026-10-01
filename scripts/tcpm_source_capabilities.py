#!/usr/bin/env python3
"""Read-only classification of pinned TCPM logs; never negotiates or arms PPS."""
import re

LINE = re.compile(r'^\[\s*(\d+)\.(\d{6})\]\s+(.*)$')
RX = re.compile(r'^PD RX, header: (0x[0-9a-fA-F]+) \[([01])\]$')
PDO = re.compile(r'^PDO (\d+): type (\d+), (.*)$')
LIMIT = re.compile(r'^Setting voltage/current limit (\d+) mV (\d+) mA$')


def _object(index, kind, text):
    result = {'position': index + 1, 'type': kind}
    if kind == 0:
        m = re.fullmatch(r'(\d+) mV, (\d+) mA \[[RSHUDE]*\]', text)
        if not m:
            raise ValueError('malformed fixed PDO')
        mv, ma = map(int, m.groups())
        if not 5000 <= mv <= 20000 or mv % 50 or not 0 < ma <= 5000 or ma % 10:
            raise ValueError('invalid SPR fixed fields')
        result.update(kind='fixed', voltage_mv=mv, maximum_current_ma=ma)
    elif kind in (1, 2):
        unit = 'mW' if kind == 1 else 'mA'
        m = re.fullmatch(r'(\d+)-(\d+) mV, (\d+) ' + unit, text)
        if not m:
            raise ValueError('malformed variable/battery PDO')
        low, high, value = map(int, m.groups())
        if not 5000 <= low <= high <= 20000 or low % 50 or high % 50 or value <= 0:
            raise ValueError('invalid variable/battery fields')
        result.update(kind='battery' if kind == 1 else 'variable', minimum_voltage_mv=low,
                      maximum_voltage_mv=high)
        result['maximum_power_mw' if kind == 1 else 'maximum_current_ma'] = value
    elif kind == 3:
        m = re.fullmatch(r'PPS (\d+)-(\d+) mV, (\d+) mA', text)
        if not m:
            raise ValueError('unsupported or malformed APDO, including AVS/EPR')
        low, high, ma = map(int, m.groups())
        if not 3000 <= low < high <= 21000 or low % 100 or high % 100 or not 0 < ma <= 5000 or ma % 50:
            raise ValueError('invalid PPS APDO fields')
        result.update(kind='pps', minimum_voltage_mv=low, maximum_voltage_mv=high,
                      maximum_current_ma=ma)
    else:
        raise ValueError('unsupported PDO type')
    return result


def parse_source_capabilities(raw, *, same_boot=False, owner_confirmed=False,
                              fresh_log_boundary=False):
    """Complete current SOP Source_Capabilities, with explicit attribution gates.

    Header NDO bounds the exact decoded list; orphan/missing/duplicate objects,
    overflow and changing offers stay UNKNOWN. Repeated identical offers are
    retained, not counted as different supplies. Advertised voltage is distinct
    from selected voltage. TCPM limit entries are reported budgets (including Rp),
    not physical draw or proof of a completed contract. Never returns a grant.
    """
    result = {'classification': 'UNKNOWN', 'reason': None, 'objects': [],
              'source_frames': [], 'limits': [], 'limits_are_measured_draw': False,
              'PPS_request_authorized': False,
              'pump_ON_authorized': False, 'independently_measured': False}
    if not (same_boot and owner_confirmed and fresh_log_boundary):
        result['reason'] = 'missing same-boot/owner-attach/fresh-log attribution'
        return result
    pending = None
    seen = False
    try:
        for line in raw.replace('\r', '').splitlines():
            if not line:
                continue
            m = LINE.fullmatch(line)
            if not m:
                raise ValueError('malformed/truncated TCPM log line')
            sec, frac, text = m.groups()
            stamp = int(sec) * 1000000 + int(frac)
            if text == 'overflow':
                raise ValueError('TCPM ring overflow')
            rx = RX.fullmatch(text)
            if rx:
                if pending:
                    raise ValueError('incomplete Source_Capabilities before next RX')
                header, attached = int(rx[1], 16), int(rx[2])
                if header > 0xffff:
                    raise ValueError('invalid PD header')
                count = (header >> 12) & 7
                if header & 0x8000 or header & 0x1f != 1 or not count:
                    continue
                if not attached:
                    raise ValueError('source capabilities received while detached')
                pending = {'header': hex(header), 'source_timestamp_us': stamp,
                           'object_count': count, 'objects': []}
                continue
            obj = PDO.fullmatch(text)
            if obj:
                if pending is None:
                    raise ValueError('orphan/duplicate PDO outside counted source frame')
                index, kind = int(obj[1]), int(obj[2])
                if index != len(pending['objects']):
                    raise ValueError('missing/duplicate/out-of-order PDO position')
                pending['objects'].append(_object(index, kind, obj[3]))
                if len(pending['objects']) == pending['object_count']:
                    objects = pending['objects']
                    if objects[0]['kind'] != 'fixed' or objects[0]['voltage_mv'] != 5000:
                        raise ValueError('vSafe5V must be first')
                    types = [x['type'] for x in objects]
                    if types != sorted(types):
                        raise ValueError('source PDO type order')
                    fixed = [x['voltage_mv'] for x in objects if x['kind'] == 'fixed']
                    if any(a >= b for a, b in zip(fixed, fixed[1:])):
                        raise ValueError('duplicate/unsorted fixed voltage')
                    if seen and objects != result['objects']:
                        raise ValueError('changing source offers in one attach')
                    result['objects'] = objects
                    result['source_frames'].append(pending)
                    pending = None
                    seen = True
                continue
            if text.startswith('PDO ') or text.startswith('PD RX,'):
                raise ValueError('malformed PDO/RX log')
            limit = LIMIT.fullmatch(text)
            if limit:
                result['limits'].append({'voltage_mv': int(limit[1]), 'current_ma': int(limit[2]),
                                         'source_timestamp_us': stamp})
            # A later detach/reset invalidates the source cache for this attach.
            if seen and re.search(r'(-> SNK_UNATTACHED\b|HARD_RESET|SOFT_RESET|PORT_RESET)', text):
                raise ValueError('source lifecycle reset/detach after capabilities')
        if pending or not seen:
            raise ValueError('missing/incomplete current Source_Capabilities')
        result['classification'] = ('PPS_ADVERTISED' if any(x['kind'] == 'pps' for x in result['objects'])
                                    else 'NO_PPS_ADVERTISED')
        result['reason'] = 'complete attributed decoded source list'
    except ValueError as exc:
        result['reason'] = str(exc)
    return result


def parse_partner_sysfs(raw):
    """Derived source PDO list from the current Type-C partner symlink only."""
    objects = []
    current = None
    link = None
    for line in raw.splitlines():
        if line.startswith('PD_PARTNER_LINK='):
            if link is not None:
                raise ValueError('duplicate partner PD symlink')
            link = line.split('=', 1)[1]
            if not link.startswith('/sys/devices/'):
                raise ValueError('partner PD symlink unavailable')
        elif line.startswith('PDO_PATH='):
            if link is None or not line.split('=', 1)[1].startswith(link + '/source-capabilities/'):
                raise ValueError('object outside current partner source capabilities')
            name = line.rsplit('/', 1)[-1]
            m = re.fullmatch(r'(\d+):(fixed_supply|programmable_supply|variable_supply|battery)', name)
            if not m:
                raise ValueError('unsupported partner source object')
            current = {'position': int(m[1]), 'kind': m[2], 'attrs': {}}
            objects.append(current)
        elif '=' in line:
            if current is None:
                raise ValueError('source attribute outside object')
            key, value = line.split('=', 1)
            if key in current['attrs']:
                raise ValueError('duplicate source attribute')
            current['attrs'][key] = value
        elif line.strip():
            raise ValueError('malformed source attribute')
    if not objects:
        raise ValueError('partner source capabilities absent')
    if [x['position'] for x in objects] != list(range(1, len(objects) + 1)):
        raise ValueError('missing/duplicate source sysfs position')
    return objects


def corroborate_partner(parsed, raw):
    if parsed['classification'] == 'UNKNOWN':
        raise ValueError(parsed['reason'])
    partner = parse_partner_sysfs(raw)
    if len(partner) != len(parsed['objects']):
        raise ValueError('log/sysfs source count mismatch')
    kinds = {'fixed': 'fixed_supply', 'pps': 'programmable_supply',
             'variable': 'variable_supply', 'battery': 'battery'}
    fields = {'voltage_mv': ('voltage', 'mV'), 'minimum_voltage_mv': ('minimum_voltage', 'mV'),
              'maximum_voltage_mv': ('maximum_voltage', 'mV'),
              'maximum_current_ma': ('maximum_current', 'mA'),
              'maximum_power_mw': ('maximum_power', 'mW')}
    for obj, peer in zip(parsed['objects'], partner):
        if obj['position'] != peer['position'] or kinds[obj['kind']] != peer['kind']:
            raise ValueError('log/sysfs source kind/position mismatch')
        for field, (name, unit) in fields.items():
            if field in obj and peer['attrs'].get(name) != str(obj[field]) + unit:
                raise ValueError('log/sysfs source value mismatch: ' + name)
    return partner
