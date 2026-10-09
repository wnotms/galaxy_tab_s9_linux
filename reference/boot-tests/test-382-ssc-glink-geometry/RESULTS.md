# Test382 — live geometry correction works; partial GLINK capture, STOP retained

Registration71993ca4 pushed before mutation.158 affected host tests PASS/no
skips; exact kernel/config/DTB/181/ARM64 qualification reused, no rebuild/CI.
One early-ADSP boot a2646473-4160-45e2-bb69-50b181ca72cc. Actual observer state
shows nop/local clock, all8CPU buffers131KiB and4KiB subbuffer. Watcher starts
normally, ADSP running, no failed units. This directly validates corrected
capacity admission; Test381 lacked these actual values and remains STOP.

The whole historical journal boot list exceeds10s on this boot. The original
candidate boots-after command and subsequent rollback boots-before command both
stop; errors/raw output remain unchanged. No RPC/SSC launch or hardware retry.
Device remains responsive through rootADB. Before cleanup, the owned trace was
stopped/collected in the same failed boot:2534bytes,17/17 events, all8CPU raw
loss counters0, 8 RPMSG endpoints and complete source-derived geometry evidence.
Version1 negotiation completes; IPCRTR and fastrpcglink-apps-dsp have tx/rx
OPEN/OPEN_ACK and native driver bindings. Other early channel names are
pcie_drv,mhi_sat,sleepmonglink-apps-adsp,adsp_apps,LOOPBACK_CTL_LPASS.
No DIAG-named channel or endpoint is observed. This is pre-RPC evidence only:
no conclusion about later DIAG/SSC publication, DSP parsing or sensor hardware.
Local clock: no precise cross-CPU duration claim. See postmortem/glink-analysis.
Full target kernel1102 JSON rows,0 fault counts/0 unclassified suspects.

Device systemd257 supports journalctl --list-boots -n5; read-only bounded query
returns immediately and contains old/current IDs. Recovery adapter only changes
that exact listing command to timeout8 journalctl --list-boots -n5 --no-pager,
retaining original failures. Existing attribution still requires the previous
ID, unique history and exactly one following new ID; missing old ID/extra boot
never passes. This completed the already required rollback, not another candidate.
No kernel/charging/USB settings change. Adapter code+actual command stored.

Exact370 restored boot23798bfb-fa61-4fac-8468-f656a8340969; all5 accepted partition
hashes,181 files, config/notes/DCC absence, ordinary charging/roles and full
kernel gates passed. GNOME/palm/default graphical target and rootADB restored,
ADSPoffline/RPCinactive/owned overlays+assets removed. No manualTWRP now required.
SSH/hostNCM TCP untested. PPS/pumpOFF. Verified31Windows duplicates removed
225122314bytes; WSL originals retained. Restoration evidence in the successful
rollback directory; original failed rollback and recovery-required.json preserved.

Final verdict remains STOP_HISTORY_QUERY_TIMEOUT_PARTIAL_GLINK_RESTORED370,
not complete registered SSC acceptance. Results-only tests executed:false,
registered qualification reused. No Test382 repeat. Next registration should
use bounded recent history for normal admission and reach the first ordered
RPC window; don't repeat metadata fixes/reset registry/modify DIAG routing.
