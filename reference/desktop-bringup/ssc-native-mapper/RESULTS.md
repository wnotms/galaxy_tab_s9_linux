# Native mapper observer correction — read-only

Corrected the future observer to Linux auxiliary bus; Test365 historical files
remain unchanged. Current Test331 boot78ec has the native driver registered,
no mapper device, ADSP offline. Upstream creates the device during remoteproc
prepare. Exit2 is retained as no-device, not service/discovery PASS.

12 filesystem fixture tests PASS, zero skips. No kernel build or full suite was
executed: only this observer changed, no routing/kernel/config/DT/provider input.
No device writes, remoteproc/service start, flash, reboot, PPS or pump operation.
Test369 still requires USB connection and its independent physical acceptance.

Use this corrected observer plus bounded QRTR inventory/upstream RPC trace in
the next separately registered SSC scope. Binding alone is not a QMI response
or accelerometer/rotation proof. Source and device evidence are separate files.
