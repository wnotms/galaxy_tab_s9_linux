# Bounded SM5440 fresh-acquisition consumer

Design before implementation: Test274 offline, installed263 unchanged. Use the
Test272 kernel-only sm5440_passive_request_fresh API from a stand-alone loadable
diagnostic module; no production Kconfig, DTS, I2C driver or rootfs changes.
Its new compiled .ko is kept separate from the matched181module-directory files.
It cannot load on old263 and must never be force-loaded there.

## Ownership

One kthread starts only when a future registered operator explicitly loads the
module. At most8 calls,1s between successes, no retry after any nonzero provider
or consumer status. The existing API owns lifetime/PM/worker serialization. The
observer holds no lock across that API, wait or sleep. A short result mutex only
publishes/copies bounded cached rows. exit stops/joins thread before removing
safe debugfs proxies; reading results causes no acquisition or register writes.
No sysfs fast-charge control, parameters, PPS, pump enable or arming grant.

Each row keeps independent provider/validation status, request/return BOOTTIME,
actual acquired BOOTTIME and raw copied uV/uA/deciC. Refuse time reversal, total
delivery>100ms, old/future acquisition, offline/nonzero pumpIBUS/invalid voltage/
temperature. Failed raw rows remain explicitly diagnostic/status!=0/usable=0;
no policy facts or grants are returned. Do not restamp an old sample. This
consumer qualifies passive delivery behavior only, not converter timing under
active current, independent accuracy or hardware OCP. An in-flight converter can
outlast the request timeout; never cancel/clear/retry the normal monitor to pass.

## Qualification and next physical boundary

Compile external module against sealed272 config/Module.symvers/headers and same
clang21/ccache, check ELF/imports/W1/sparse, host-execute actual C lifecycle/return/
validation/stop/unload paths. One final full host run retains all previous IDs.
Config and DT diff must be empty; Image/181modules untouched. No device command.

Future Test275 only: verified272provider+paired181modules and exact263rollback,
PC fixed5V/SDP500mA, pumpOFF/fault0/thermal<38C/rescue, one explicit module load
within30s window. Save all rows, raw snapshot and boundary/first-fault kernel
journal; first nonzero status ends requests and preserves failure. No reload.
Unload verifies the kthread stopped; sameboot ADB/deviceNCM/Wi-Fi endpoint. Timing
success is not PPS/pump/current admission; nonzero ADC/OCP/livePM remain separate.

Cached result state:0=RUNNING,1=COMPLETED,2=STOPPED,3=CANCELLED; each row's
provider_status and status are signed Linux errno, usable is only passive evidence.
External diagnostic .ko is unsigned, force-signature config is off; future load
may add O/E diagnostic taints. This is not a reason to suppress any kernel fault.
