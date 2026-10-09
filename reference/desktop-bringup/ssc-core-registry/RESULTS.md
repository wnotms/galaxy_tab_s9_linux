# X710 core IMU cache comparison (offline)

The exact328-file archive6abc10ec was inspected without extraction, cache
rewriting or device mutation. Four core groups match their config leaves exactly:

| Saved group | Config source | Result |
| --- | --- | --- |
| lsm6dso_0_platform.config | kailua_lsm6dso_0_0.json | Exact match |
| lsm6dso_0_platform.orient | kailua_lsm6dso_0_0.json | Exact match |
| lsm6dso_0.accel.config | lsm6dso_0.json | Exact match |
| lsm6dso_0.gyro.config | lsm6dso_0.json | Exact match |

This includes bus_type3, bus_instance1, slave_config107, i3c_address10,
min/max bus speed400/12500kHz, encoded dri_irq_num7864393, sensor_vddio rail,
direction -y/+x/+z and DRI settings. These are **raw vendor encodings**. The
presence of `i3c_address` does not prove which transport is active. An earlier
commentary inferred I3C from that field; that inference is withdrawn. The
local S9 Ultra hardware-status document labels bus_type3 as SPI, but that
cross-model description is not a verified X710 electrical/enum definition.
Do not guess an AP I2C address, probe the sensor bus, change pinctrl or transfer
ownership based on either interpretation. Exact comparison values are preserved
in CORE_GROUPS.json and the reference source identities in INPUTS.json.

The helper compares only these strict-JSON hardware/config leaves; it does not
flatten arbitrary parent registry references, overwrite factory calibration,
apply config selector precedence or normalize nonstandard vendor JSON. MTP and
SoC519 appear in the core config selectors, but the stock ro.revision selector
is not newly proven. Neither a matching file nor this report establishes what
the live firmware selected, a cache hit, SSC400 publication or a sensor sample.

This narrows the next action: the copied core cache is not missing the IMU bus,
orientation, accel or gyro settings, so there is no present justification for
regenerating those groups. Test379's actual RPC metadata/init test remains the
next registered hardware question; if it matches without SSC, investigate
firmware initialization/service publication rather than patching these settings.

Eight new real archive/schema/mismatch checks and34 existing stock-asset/SoC
checks passed (42 total, no failures/errors/skips). The checker rejects corrupt
identity, duplicate/missing members, special entries and incorrect group schema;
it retains field differences rather than declaring a matching bus implementation.
No kernel build/full regression/CI or Test379 input modification occurred.

Fresh read-only admission is still the accepted boot a1e7570f with GDM/SSH/ADB
active,100%,27.1°C and VBAT4.445V. The registered<4.44V deployment gate remains
unsatisfied. The USB-disconnect request is pending; no new physical attempt,
partition write, ADSP start, package change, PPS/pump/current change or reboot
was issued. Keep Test379 registered but unexecuted until a fresh admission passes.
