# Exact331 restoration after bring-up entry refusal

Test333 stopped at SOC80, VBAT4.288V, pack27.4C. Native fixed check also refused
with -ERANGE (-34), lease0; read pumpCNTL5 confirms OFF. Full journal/history are
saved. No successful proof or 30-second acceptance exists. No repeat allowed.

The active candidate entry gate remains SOC20–<80/VBAT3.5–<4.3V. Restoring the
ordinary known-good331 kernel is not entry into direct/PPS/check charging.
Use restoration.py only for exact331 rollback; its separate baseline endpoint
accepts normal SOC up to100/VBAT up to the unchanged4.44V design. All existing
kernel/config/cmdline/notes/pack temperature/health/OFF/failedunits/transports and
unique boot gates stay. Candidate phase is explicitly rejected. Five affected
mock tests PASS. No kernel/hardware policy/current/thermal changes. Paired writes,
allfive readbacks, BCBclear/unmount and one normal restart use frozen runner.
Register/push before recovery. No new candidate or Test333 replay.
