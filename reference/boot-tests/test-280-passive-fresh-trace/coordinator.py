#!/usr/bin/env python3
"""Single-process passive trace/observer coordinator. No executable entry point.

Test280 uses mock operations ONLY. Deployment/preflight/rollback and device health
qualification require a future registered wrapper. This file never changes any
charging setting or requests ADC directly; the corrected observer owns its calls.
"""
import json
from pathlib import Path
import time

from collector import Session, boot_id
from analyse import analyse
from observer_gate import observer, require


OBSERVER_SHA256 = '9aafabf63a18ebf31b593c97dd3edc1d0fb43a7348936e10b02f0773e5661582'
MAXIMUM_SECONDS = 30
TAIL_SECONDS = .5


def bind(raw, parsed):
    """Bind request records to observer's BOOTTIME-ms envelope, not jiffies."""
    require(raw['verdict'] == 'BOUNDED_TRACE_ATTRIBUTED', 'trace attribution UNKNOWN')
    requests = raw['requests']
    require(len(requests) == parsed['count'], 'observer/trace request count differs')
    for request, row in zip(requests, parsed['rows']):
        require(request['return_code'] == row['provider_status'], 'observer/trace provider return differs')
        # Outer observer timestamps are floor(ms); probes occur inside its call.
        # Fast boot tracing may be anomalous: do not widen for undocumented drift.
        lower = row['request_ms'] * 10**6
        upper = (row['return_ms'] + 1) * 10**6
        require(lower <= request['entry_ns'] <= request['return_ns'] < upper,
                'trace outside observer BOOTTIME envelope')
    return {'request_count': len(requests), 'observer_trace_bound': True,
            'timing_acceptance': False, 'charging_authorized': False}


def run_once(fs, output, ops, elapsed=time.monotonic, pause=time.sleep):
    """ops provides verified_identity/boot/kallsyms/load/cached_result/unload.

    verified_identity MUST represent a new accepted registration + paired install
    and current full health gates; current STOPPED Test280 can never supply it.
    load/unload must record raw command status and enforce 5s/10s timeouts. The
    future physical wrapper supplies ops; this library does not deploy anything.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    result = {'verdict': 'STOP', 'observer_load_attempted': False,
              'observer_unloaded': False, 'device_endpoint_qualified': False,
              'PPS': False, 'pump_ON': False, 'current_increase': False,
              'timing_acceptance': False, 'errors': []}
    session = None
    expected = None
    started = None
    try:
        verified = ops.verified_identity()
        require(verified['verdict'] == 'READY_FOR_REGISTERED_PASSIVE_TRACE', 'accepted physical preflight absent')
        require(verified['paired_install_verified'] is True and verified['normal_cmdline_verified'] is True,
                'paired installation/cmdline unverified')
        require(verified['observer_sha256'] == OBSERVER_SHA256, 'original/unknown observer forbidden')
        require(verified['observer_absent'] is True and verified['health_rescue_verified'] is True,
                'observer ownership/health/rescue unverified')
        expected = boot_id(verified['boot_id'])
        require(boot_id(ops.boot()) == expected, 'boot changed before trace setup')
        session = Session(fs, output / 'trace')
        session.setup(ops.kallsyms(), expected)
        session.start()
        started = elapsed()
        require(boot_id(ops.boot()) == expected, 'boot changed before load')
        result['observer_load_attempted'] = True  # Unknown return must never reload.
        ops.load(timeout=5)
        while True:
            require(elapsed() - started < MAXIMUM_SECONDS, 'observer observation deadline')
            require(boot_id(ops.boot()) == expected, 'boot changed during observation')
            raw = ops.cached_result()
            parsed = observer(raw)
            if parsed['state'] != 0:
                (output / 'terminal-observer.txt').write_text(raw)
                result['observer'] = parsed
                require(parsed['state'] in (1, 2), 'observer cancelled')
                result['observation_seconds'] = elapsed() - started
                # Fixed, pre-registered tail; no new request/load/adaptive wait.
                pause(TAIL_SECONDS)
                result['tail_seconds'] = TAIL_SECONDS
                break
            pause(.025)
    except BaseException as exc:
        result['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        # Even a cache/read/load error preserves available raw result before unload.
        if result['observer_load_attempted']:
            try:
                with (output / 'observer-before-unload.txt').open('x') as stream:
                    stream.write(ops.cached_result())
            except Exception as exc:
                result['errors'].append('cached evidence: ' + str(exc))
        if session is not None:
            try:
                if session.created:
                    session.snapshot(ops.boot())
            except Exception as exc:
                result['errors'].append('trace snapshot: ' + str(exc))
            try:
                if session.output_owned:
                    session.finish('; '.join(result['errors']) or None)
                    if session.meta['cleanup_errors']:
                        result['errors'].append('trace cleanup: ' + '; '.join(session.meta['cleanup_errors']))
            except Exception as exc:
                result['errors'].append('trace finalization: ' + str(exc))
        # Release probes before module unload. Initial absence means this attempt
        # owns any ambiguous load; ops must verify absence after one unload.
        if result['observer_load_attempted']:
            try:
                ops.unload(timeout=10)
                result['observer_unloaded'] = True
            except Exception as exc:
                result['errors'].append('observer unload: ' + str(exc))
        if expected is not None:
            try:
                require(boot_id(ops.boot()) == expected, 'boot changed at endpoint')
                result['same_boot_after_unload'] = True
            except Exception as exc:
                result['errors'].append('endpoint boot: ' + str(exc))
        if session is not None and (session.output / 'manifest.json').exists():
            result['trace_analysis'] = analyse(session.output)
            if not result['errors'] and 'observer' in result:
                try:
                    result['binding'] = bind(result['trace_analysis'], result['observer'])
                except Exception as exc:
                    result['errors'].append('trace binding: ' + str(exc))
        if not result['errors'] and result.get('binding', {}).get('observer_trace_bound'):
            result['verdict'] = ('PASSIVE_REFUSAL_CAPTURED' if result['observer']['first_refusal']
                                 else 'EIGHT_PASSIVE_DELIVERIES_CAPTURED')
        if started is not None:
            result['elapsed_seconds_with_cleanup'] = elapsed() - started
        with (output / 'summary.json').open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
    return result
