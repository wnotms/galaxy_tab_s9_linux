# Test316 — fixed-contract capability classification

Offline correction before physical fixed9 context testing. Test315 is preserved
as its qualified but undeployed source; it has two overly strict readiness
assumptions: USB_TYPE_PD only and immediate refusal of the5V negotiation standby.

Linux7.2-rc3 tcpm_pd_select_pdo describes SOURCE CAPABILITY with PD/PD_PPS/SPR_AVS
labels, while tcpm_psy_get_online reports ACTUAL fixed/PPS/AVS mode as1/2/3. The
Test273 C1 raw capture directly shows ONLINE1/9V1.5A with USB_TYPE_PD_PPS.
Use the same four capability labels already accepted by sm5714_pd_read_snapshot;
continue requiring ONLINE1, !pps_contract and fixed9V1000..1500mA.

During the unchanged4s initial read-only wait, permit only a coherent fixed5V
snapshot advertising a fixed9V>=1A PDO to wait for TCPM's normal negotiation.
Pin its instance/source epoch; changed epoch, malformed/weak/no9V/PPS/EPR-only
source or a5V snapshot after handoff remains a refusal. No protocol request,
converter/settings/Q4 write before a complete fixed9 admission. Save first5V
snapshot and readiness count/timing in debugfs. No retry after actual admission
or fault, no wider observation/charging-release deadline.

Extend actual-C host tests using pinned Linux PDO helpers. Build existing
isolated ADC-condition profile in the same incremental cache, exact accepted311
config/DT/protected/module audit and W1/sparse; freeze315 symbols first. No new
profile, TCPC/core/battery/DTS/USB/rootfs change or physical operation. Stage3
remains NOT READY. Next separately register fixed9 one-shot acquisition and
unconditional accepted311 restore, then request the owner's charger/boot action.
