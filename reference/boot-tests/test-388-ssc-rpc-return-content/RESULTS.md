# Test388 — observer budget STOP; exact Test370 restored

One candidate was executed after registration287d2b8c and admission0b46dd17
were pushed. Candidate boot `6b738d4a-a963-46e5-9cbb-31249e5f1173` was attributed
from accepted baseline622874b2. Test370 kernel/config/DTB/181 files were unchanged;
only the registered early vendor_boot and eight-file observer/328-asset overlay
were temporarily installed. RootPD/sensorsPD started once with native sensor_pd74.

**STOP_OBSERVER_BUDGET_RESTORED370**. The sensors daemon emitted
`RPCRETURN_LIMIT seq=701 reason=budget`: 2,103 records/524,052 message bytes reached
the registered512KiB per-process bound. The full unit JSON journal is3,961,461
bytes/3,137 rows, below its separate8MiB bound. The observer stops logging, not
the daemon; the host stopped this experiment and restored the accepted system.
The registered60s window was not completed. No retry or limit waiver occurred.

The original strict parser separately rejected the first incoming frame as extra
bytes: scalars00020200,41 bytes, two input buffers8/9 consume33 bytes, followed
by `08000000ff000000`. Qualcomm's reference `pack_out_lens` writes one unaligned
32-bit capacity per output after packed inputs. This is a host parser hypothesis
to verify against source and retained raw evidence, not a firmware/rootcause claim.
The original parser outputs and stop remain immutable; corrected offline analysis
must use a fresh namespace. No complete registry-content proof is claimed here.

Actual config stat metadata35/35 passed. At stop SSC400 was absent and no real
accelerometer sample had been collected. GLINK capture was complete with no
loss/fault. The full candidate kernel journal, including shutdown, was recovered
offline:1,111 rows, no CPU/panic signature or new unclassified severe fault under
the registered startup classification. This logging stop is not evidence that
the device failed, and also is not evidence that sensor acceptance passed.

Owned runtime/readiness/overlay/assets were removed, exact Test370 vendor_boot
restored, and all five partitions/181 module files read back successfully.
Normal restored boot `60384db6-dca3-4db5-b85a-89005923f497` passed identity and
health. GNOME/GDM/palm and rootADB/device NCM are active; ADSP offline, RPC inactive,
owned payload absent. Final read-only sample94%,33.5C, healthGood. Service/process
restoration was observed; no new user visual confirmation or Wi-Fi SSH test.

31 exact Windows staging files were removed,225,122,696 bytes. Source, artifacts
and complete raw evidence remain in WSL. PPS/pump/DCC remain OFF. Kernel/config/
DTS/USB/charging/input were not changed; no new kernel build or GitHub Actions.
Results tests executed:false; unchanged96 affected checks and qualified ARM64/
QEMU build were reused. Next correct the input-frame interpretation offline and
derive a separate bounded observer budget from actual frames, rather than replay
the same failed profile. Sensor samples and automatic rotation remain unfinished.
