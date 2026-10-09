"""Explicit, one-shot root/sensor RPC startup for future registered SSC scopes.

The caller owns the volatile gate, persisted attempt ledger and cleanup. Do not
use this to start ADSP: it must already be running from the admitted early boot.
Systemd active only establishes a process; real SSC discovery remains required.
"""
ROOT_PD = 'hexagonrpcd-adsp-rootpd.service'
SENSOR_PD = 'hexagonrpcd-adsp-sensorspd.service'
RPC_UNITS = (ROOT_PD, SENSOR_PD)


def start_rpc(invoke, state, persist):
    if state.get('phase') != 'prepared-inactive' or state.get('started') is not False:
        raise ValueError('RPC attempt not fresh')
    for unit in RPC_UNITS:
        if invoke(['systemctl', 'is-active', unit], required=False) != 'inactive':
            raise ValueError('RPC unit not inactive before start: ' + unit)
    # A timeout/lost reply consumes the attempt, too. Persist before starting.
    state.update(started=True, phase='start-requested', rpc_requested=[], rpc_active=[])
    persist(state)
    for unit in RPC_UNITS:
        state['rpc_requested'].append(unit)
        persist(state)
        invoke(['systemctl', 'start', unit], timeout=15)
        if invoke(['systemctl', 'is-active', unit], required=False) != 'active':
            raise ValueError('RPC unit did not activate: ' + unit)
        state['rpc_active'].append(unit)
        persist(state)
    return state
