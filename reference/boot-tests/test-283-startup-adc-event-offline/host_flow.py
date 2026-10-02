"""Small host recovery waiter; offline qualification only in Test283.

Native ADB 'recovery' means ready for a subsequent TWRP identity gate. This
helper never grants write admission or boots/loads/flashes anything itself.
"""
import time


def recovery_ready(raw, serial='R52X10045LT'):
    matches = []
    for line in raw.replace('\r', '').splitlines():
        fields = line.split()
        if fields and fields[0] == serial:
            matches.append(fields)
    if not matches:
        return False
    if len(matches) != 1 or len(matches[0]) < 2:
        raise ValueError('ambiguous recovery serial')
    state = matches[0][1]
    if state in ('recovery', 'device'):
        return True
    if state == 'offline':
        return False
    raise ValueError('unexpected recovery transport state: ' + state)


def wait_recovery(recorder, timeout=90, elapsed=time.monotonic, pause=time.sleep):
    """Fresh stage Recorder required; native state is preserved on each poll.

    Retain the existing 3s readiness polling interval and bounded transport
    timeout. Return as soon as native recovery is seen, not after a fixed wait.
    Caller must then verify recovery kernel/device/root/partition identities.
    """
    if timeout <= 0:
        raise ValueError('recovery deadline')
    start = elapsed()
    index = 0
    while elapsed() - start < timeout:
        remaining = timeout - (elapsed() - start)
        if remaining <= 0:
            break
        raw, status = recorder.host_adb(f'devices-{index:02}', 'devices',
                                       timeout=min(5, remaining), required=False)
        index += 1
        duration = elapsed() - start
        if duration >= timeout:
            break
        if status == 0 and recovery_ready(raw):
            return {'verdict': 'RECOVERY_TRANSPORT_READY_IDENTITY_STILL_REQUIRED',
                    'elapsed_seconds': duration, 'polls': index}
        pause(min(3, timeout-duration))
    raise TimeoutError('recovery unavailable; no automatic reboot or write')
