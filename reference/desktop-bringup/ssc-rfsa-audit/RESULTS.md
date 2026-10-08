# Current X710 RFSA source inventory — read-only completed

Authenticated Wi-Fi SSH reached current Test331 boot 78ec1906-4713-4837-9acc-fe245647d7cf with ADSP offline. The validated vendor LP extent was mounted read-only and 66 entries inventoried in lib/rfsa/adsp, lib64/rfsa/adsp and dsp (the lib64 root is absent). None is named oemconfig.so. Captured ELF machine IDs distinguish Hexagon libraries from data. No binaries exported, stock files modified, partitions written or ADSP/services started. Temporary mount and loop were removed; same boot/offline ADSP verified afterwards.

This result is bounded to the inventoried roots; it does not claim every vendor filesystem path was searched. The prior full stock DSP manifest likewise contains no oemconfig.so. Consequently the single Test365 log message is not sufficient evidence that a required asset was omitted. Do not fetch a different model's oemconfig binary or fabricate one.

The failed SSC discovery remains unproven. Next diagnostic scope needs reverse-RPC calls/file access and QRTR service evidence to distinguish optional lookup, registry initialization and domain/service readiness.

12 existing LP layout tests passed, zero skipped; native inventory completed. New helper syntax reviewed. No kernel build, firmware change, flash, reboot, full regression or Actions. Initial ADB was unavailable but authenticated same-boot Wi-Fi was available; no device nonresponse claimed from the empty ADB list.
