# Test364 — early ADSP/native SoC identity observed, registered flow stopped

One controlled candidate boot: `86f583ce-9b2c-47ed-bb0a-cda2912d6884`, uniquely
attributed after the accepted331 boot. Boot/vendor_boot and all181 candidate
files were verified at installation. Actual embedded config/notes match the
qualified native SoCinfo candidate; cmdline/DTB/ordinary charging unchanged.

At17.07s the device snapshot directly reported signed ADSP `running`,
`/dev/fastrpc-adsp`, SM8550/id519/SMEMformat0.16/hardwareplatform8(MTP)/
subtype0(Unknown)/platformversion65536. These are native measured fields,
not fixtures or silicon revision substituted for board version.

The first authenticated WiFi SSH probe on newly assigned10.175.236.65 timed
out during banner exchange. The original runner stopped and restored331;
no second candidate boot/SSC service activation/PPS/pump attempt. This is
**STOP_FIRST_SSH_BANNER_TIMEOUT**, not completed Test364 acceptance or rotation.
The snapshot had ADB, device usb0, ssh service and WiFi address; it does not
prove why the host SSH banner was delayed. Do not call this a CPU wedge.

The failed boot's complete persistent kernel JSON was retrieved after restore.
Boot/timestamps/start record validated, no detected CPU/panic/Oops faults and
no new unbounded suspects. ADSP/remoteproc/FastRPC records are also preserved.
The first failure and raw SSH error remain unmodified.

Exact331 boot/vendor_boot/allfive and original181 restored; only newly owned
328stock assets removed. Original persist untouched. Normal Debian returned:
`ea91d666-9535-4e8b-9147-23996700a0e2`. Final exact config/notes/modules/partitions,
30s health observation, authenticatedWiFi10.175.236.198, ADB/deviceNCM/noCode43,
complete kernel journal/no new fault/no failed units passed. No stay-TWRP
requirement applies under the owner's updated instruction.

Next correct readiness to admit a new WiFi path within a bounded boot deadline,
recording initial failure/recovery rather than conflating service-active with
an immediately available authenticated path. Preserve strict key/boot identity
and fault gates; qualify the change offline before a separately registered SSC
discovery/rotation test. Native ADSP support is physically observed, but the
full sensor task remains incomplete. Do not start higher-power charging yet.

Host build/tests executed:false for results-only recording; reuse registered
80affected pass/zero skip and prior exact kernel/DTB/181 qualification. Full3032
NOTPASS remains historical; no Actions. Test348 remains STOP; current1.8A is
a bring-up PPSinput/rawstop limit, not proven X710 maximum.
