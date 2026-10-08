# Owner-requested final TWRP endpoint

Owner: “已接回电脑，本轮完成后保持在twrp”. PC return passed on the same
candidate boot: ADB, device NCM, no Code43, pump OFF/unbound.

Use the existing qualified restoration helpers and exact paired Test331 manifest.
The one-time completion helper repeats the existing recovery restoration sequence
through all-five partition and 181 module verification, unmounts Debian, verifies
TWRP identity and stops. It has no Debian reboot or charging activation command.
The frozen charging inputs and historical restore() are unchanged.

The final report must distinguish exact offline restoration from a new restored
Debian runtime acceptance: the latter is intentionally not executed per owner
instruction. Earlier Test331 runtime qualification remains historical evidence.
No full build/test rerun: operational endpoint change only. Python syntax checked;
actual partition/module hashes and recovery identity determine restoration success.
