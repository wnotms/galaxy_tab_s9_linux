# Test365 — STOP, exact Test331 restored

One candidate boot `2986590a-21aa-44d4-815d-7b2fd36f4207` passed early ADSP/native SoCinfo/identity/transport admission. Four qualified ARM64 runtime packages were installed behind an activation gate. RootPD and sensorsPD started once; accelerometer discovery did not find the SSC QMI service within the registered 60 seconds. No iio proxy, desktop, PPS or pump activation occurred.

The sensorsPD journal reported `Could not open oemconfig.so: No such file or directory`. This is a diagnostic lead, not a proven root cause. Runtime services were stopped and the volatile activation gate removed. Packages and the standard fastrpc account remain inactive as registered.

Automatic recovery stopped before any rollback partition write: the reused frozen Test364 helper checked `.gts9-test364-original` rather than the actual `.gts9-test365-original`. Its following hash check correctly rejected the still-installed candidate modules. Preserve the initial failure and `recovery-required.json`; this was an orchestration defect, not a proven CPU wedge.

`recovery-completion` restored the correct Test365 module slot. Its offline journal command lacked an absolute executable path and stopped without a boot. `recovery-completion-02` retrieved the failed boot kernel JSON, verified all 181 original files, removed owned firmware/registry assets, restored and read back both original partitions and all five partition identities, cleared the recovery request and booted ordinary Debian once. Current boot `78ec1906-4713-4837-9acc-fe245647d7cf` has the exact Test331 config/notes/181 modules, absent DCC, ordinary charging policy and working ADB, device NCM and authenticated Wi-Fi SSH. Kernel classification has no fault counts or unexplained suspects.

SSC discovery and automatic rotation are NOT PASS. No retry of this profile. Next: inspect the exact same-model DSP library/search-path requirements. Owner separately requests persistent GNOME startup and a terminal shortcut on the restored accepted kernel.

Host validation reused: 95 affected tests passed, zero skipped; exact existing kernel/artifact qualification reused. Results-only changes: `executed: false`. No fresh build/full run and no GitHub Actions. The historical full 3032-test run remains NOT PASS.
