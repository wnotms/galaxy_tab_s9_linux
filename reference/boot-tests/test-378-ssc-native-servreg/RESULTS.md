# Test378 results — native mapper answers, SSC remains absent

One registered attempt was executed. Candidate boot
`5b6c083c-65ba-4f89-bd5e-f42410087ea5` was uniquely attributed and passed early
ADSP/FastRPC/native-SoC identity and the37.36s startup observation. Wi-Fi
automatically connected within the registered90s admission window; ADB and
device NCM stayed available. The kernel, config, modules, DTS and charging
policy were unchanged.

The complete QRTR inventory contained exactly one native Servreg endpoint,
node1/port16385, service64/instance257. One read-only GET_DOMAIN_LIST returned
in approximately1ms with a complete six-domain response, including
`msm/adsp/sensor_pd`, instance74. Request and full response bytes are preserved
in `runtime-discovery/servreg-domains.json`. This directly verifies a domain
answer, beyond the older binding/advertisement observations.

RootPD and sensorsPD were explicitly started once, in that order. Both stayed
active. The60s discovery window still produced23 `SSC QMI Service not found`
accelerometer probes, no SSC400 endpoint and no sample. SensorProxy was not
started. The sensor trace read the registry and statted config JSONs; the only
reported lookup failure remained `oemconfig.so`, whose necessity is unproved.
There is no justification for another identical mapper/RPC retry.

The first bounded discovery failure stopped the test. The gate was removed,
both RPC units stopped, and the exact Test370 vendor/assets/desktop endpoint
restored. Boot `a1e7570f-4f1b-4068-b768-8e0edb0c457d` passed restored identity,
all five partitions and181 modules. GDM, SSH, ADB and the permanent USB
lifecycle are active, ADSP is offline and no unit is failed. A final read
also found GNOME Shell running, DSI enabled and backlight power0. Visual
login/desktop confirmation is separate from these process/output observations.

The complete failed candidate's persistent kernel journal was retrieved during
rollback and classified: no detected new fault signatures or unclassified
suspects. PPS/pump remained off and HVC DCC absent. This is not a CPU-stability
failure, but the missing SSC publication's cause remains unresolved and is not
proved to be exclusively userspace.

The native mapper response and complete process launch are verified partial
results. Sensors/rotation are **not accepted**. Next work should inspect the
sensorsPD initialization/service-publication boundary, keeping the exact X710
registry timestamps and checking RPC stat/result semantics against primary
source. Do not clear the registry, add another mapper, extend the same failed
window or change charging parameters to try again.

Validation reused105 affected host checks (zero failures/errors/skips) and the
byte-exact Test370 build. Results-only recording ran no build/new host regression
(`executed:false` in `summary.json`). No GitHub Actions or main merge.
