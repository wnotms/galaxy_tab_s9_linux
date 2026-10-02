"""One diagnostic observer load/cache/unload; no trace/PPS/pump/deployment."""
import json
from pathlib import Path
import time
from observation_gate import observation

OBSERVER_SHA256 = '333fe5ee4f05580805ca6db6e57603055b4ed77ab49dd3d55d75880d986a18b9'
PROVIDER_NOTES_SHA256 = '925264595828674f61db47a301c306d4c489cc6d6b66b2a0a8e8fb630accbf0d'


def run_once(folder, ops, *, clock=time.monotonic, sleep=time.sleep):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    errors, parsed = [], None
    attempted = unloaded = same_boot = False
    boot = None
    start = clock()
    try:
        packet = ops.verified_identity()
        boot = packet['boot_id']
        (folder / 'identity.json').write_text(json.dumps(packet, indent=2)+'\n')
        before_ms = ops.boottime_ms()
        attempted = True
        ops.load(10)
        deadline = clock() + 5
        while True:
            raw = ops.cached_result()
            (folder / 'cache-last.txt').write_text(raw)
            parsed = observation(raw)
            if parsed['outcome'] != 'INCOMPLETE':
                break
            if parsed['state'] == 3 or clock() >= deadline:
                raise ValueError('cancelled/incomplete observer; no retry')
            sleep(0.025)
        after_ms = ops.boottime_ms()
        row = parsed['rows'][0]
        if not before_ms <= row['request_ms'] <= row['return_ms'] <= after_ms:
            raise ValueError('observer row outside owned BOOTTIME capture')
        if ops.boot() != boot:
            raise ValueError('boot changed during observation')
    except Exception as exc:
        errors.append(type(exc).__name__+': '+str(exc))
    finally:
        if attempted:
            try:
                ops.unload(10)
                unloaded = True
            except Exception as exc:
                errors.append('cleanup '+type(exc).__name__+': '+str(exc))
        if boot is not None:
            try:
                same_boot = ops.boot() == boot
                if not same_boot:errors.append('boot changed at endpoint')
            except Exception as exc:
                errors.append('endpoint '+type(exc).__name__+': '+str(exc))
    outcome = 'STOP_COLLECTION' if errors else parsed['outcome'] if parsed else 'STOP_PREFLIGHT'
    result = dict(verdict=outcome, observer=parsed, errors=errors,
                  observer_load_attempted=attempted, observer_unloaded=unloaded,
                  same_boot_after_unload=same_boot, elapsed_seconds=clock()-start,
                  charging_authorized=False, legacy_fresh_accepted=False,
                  physical_calibration=False, PPS=False, pump_ON=False,
                  device_endpoint_qualified=False)
    (folder / 'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
