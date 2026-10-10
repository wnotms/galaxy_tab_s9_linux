"""One registered sensors-PD then root-PD start, no restart or DSP operation.

Actual X710 stock starts sscrpcd in early_hal and adsprpcd in main. That is a
source-supported order hypothesis, not proof of a required mainline ordering.
Keep historical root-first helper unchanged for reproducibility. The caller
owns gate, preflight, attempt ledger and deactivation exactly as before.
"""
ROOT_PD = 'hexagonrpcd-adsp-rootpd.service'
SENSOR_PD = 'hexagonrpcd-adsp-sensorspd.service'
RPC_UNITS = (SENSOR_PD, ROOT_PD)


def start_rpc(invoke, state, persist):
    if state.get('phase') != 'prepared-inactive' or state.get('started') is not False:
        raise ValueError('RPC attempt not fresh')
    for unit in RPC_UNITS:
        if invoke(['systemctl', 'is-active', unit], required=False) != 'inactive':
            raise ValueError('RPC unit not inactive before start: ' + unit)
    # Consumed before the first externally visible operation; lost replies
    # never authorize another attachment. Save each exact unit intent first.
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
