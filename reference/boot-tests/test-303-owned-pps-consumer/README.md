# Test303 — actual owned PPS consumer, offline only

Purpose: integrate real TCPM PPS/fixed APIs, checked battery switching lease,
standard pack reads, strict SM5440 physical OFF/fresh evidence, and PM drain in
one pump-OFF protocol roundtrip. Design precedes code in
`docs/X710_OWNED_PPS_CONSUMER.md`. Baseline a3d8bd4c/Test302; device remains
Test299/Test300. No deployment, PPS request on device, pump activation or
ordinary charge-current increase. This is not full direct-charge acceptance.

Changed-source host fault tests and one incremental ARM64 build of the existing
`sm5440-policy-offline` profile; no routine full suite/Actions. Audit exact prior
DTB, sole policy config n->y, protected fixed baseline and181 matched modules.
The consumer uses the unchanged100ms physical gate; startup refusal and measured
ADC latency remain unwaived blockers. A future physical scope requires separate
registration and accepted fixed baseline rescue. Stop at first build/test/identity
failure and preserve raw logs. No automatic hardware retry or new policy limits.
