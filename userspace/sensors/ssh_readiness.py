#!/usr/bin/env python3
"""Bounded, same-boot SSH admission policy; injected probes, no device commands.

This is a future registered boot-readiness helper, not a Test364 retry. A DHCP
address/service-active packet alone does not prove authenticated SSH readiness.
Only explicit transient TCP/banner failures may remain pending. Trust/identity,
health or unknown failures stop immediately. No reboot or configuration callback.
"""
import re
import time

TRANSIENT = re.compile(r'Connection timed out during banner exchange|Connection timed out|Connection refused|No route to host|Network is unreachable')
AUTH_FAILURE = re.compile(r'REMOTE HOST IDENTIFICATION HAS CHANGED|Host key verification failed|Permission denied|Authentication failed', re.I)


class ReadinessError(ValueError):
    def __init__(self, message, summary):
        super().__init__(message)
        self.summary = dict(summary, verdict='STOP', reason=message)


def admit(probe, check_device, *, machine_id, boot_id, seconds=30,
          max_attempts=3, clock=time.monotonic, pause=time.sleep):
    """Probe(remaining)->{stdout,stderr,status}; check_device(remaining)->boot UUID.

    Caller preserves each raw probe and checks full device identity/health in
    check_device before returning the observed boot ID. Probe is authenticated
    using already enrolled SSH keys. Both callbacks must honor remaining budget.
    Failures are retained even if admission later succeeds. No repeated boot.
    """
    if (not re.fullmatch('[0-9a-f]{32}', machine_id) or
        not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot_id) or
        not 0 < seconds <= 90 or not 1 <= max_attempts <= 3):
        raise ValueError('invalid registered readiness bounds/identity')
    started = clock(); attempts = []
    summary = dict(attempts=attempts, boot_id=boot_id, deadline_seconds=seconds,
                   max_attempts=max_attempts, reboot_requested=False)

    def remaining():
        value = seconds-(clock()-started)
        if value <= 0:
            raise ReadinessError('SSH readiness deadline', dict(summary, elapsed_seconds=clock()-started))
        return value

    for i in range(max_attempts):
        try:
            observed = check_device(remaining())
        except Exception as exc:
            raise ReadinessError('device health/identity unavailable: '+str(exc), summary) from exc
        if observed != boot_id:
            raise ReadinessError('device boot changed during admission', summary)
        try:
            result = probe(remaining())
        except Exception as exc:
            raise ReadinessError('unclassified probe error: '+str(exc), summary) from exc
        if set(result) != {'stdout', 'stderr', 'status'} or not isinstance(result['stdout'], str) or not isinstance(result['stderr'], str):
            raise ReadinessError('invalid probe evidence', summary)
        attempts.append(dict(index=i+1, elapsed_seconds=clock()-started, **result))
        remaining()  # A late success cannot silently exceed the registered bound.
        if result['status'] == 0:
            if result['stdout'].replace('\r','').splitlines() != [machine_id, boot_id]:
                raise ReadinessError('authenticated peer identity mismatch', summary)
            # A reboot after probe/startup cannot be admitted using its old reply.
            try:
                observed = check_device(remaining())
            except Exception as exc:
                raise ReadinessError('post-probe device health unavailable: '+str(exc), summary) from exc
            remaining()
            if observed != boot_id:
                raise ReadinessError('device boot changed after authentication', summary)
            return dict(summary, verdict='READY_WITH_RECORDED_TRANSIENT' if i else 'READY',
                        elapsed_seconds=clock()-started, first_failure=attempts[0] if i else None)
        error = result['stderr']
        if AUTH_FAILURE.search(error) or result['status'] != 255 or not TRANSIENT.search(error):
            raise ReadinessError('SSH authentication/unknown failure', summary)
        if i+1 < max_attempts:
            pause(min(2, remaining()))
    raise ReadinessError('bounded SSH attempts exhausted', dict(summary, elapsed_seconds=clock()-started))
