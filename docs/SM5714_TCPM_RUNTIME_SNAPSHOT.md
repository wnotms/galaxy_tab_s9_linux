# SM5714 standard TCPM runtime snapshot

Missing coordinator prerequisite: safe source PDO + current fixed TCPM budget
and standard power_supply observations from the actual port, without a raw
controller/port pointer escaping. This does not enable PPS or direct charging.

Source cache already has a transport mutex/generation. Add a single-provider
registry, monotonically unique instance ID, operation users and drain on unbind.
Acquire TCPM's standard power_supply once after port registration using the
upstream `tcpm-source-psy-<dev_name>` name (no adapter-number hardcode); put it
before tcpm_unregister_port. All active reads drain first. No property operation
under registry/TCPC/battery lock. Registry->tryTCPC only; IRQ never registry.

Mirror successful TCPM current-limit and charge callbacks under TCPC lock.
Bracket callbacks with pending count + monotonically changing budget sequence.
No I2C, voltage policy, source cache or battery programming sequence change.
Read four standard properties twice; require agreement, mirrored fixed budget,
no pending callback, unchanged source/budget/instance and no fault/removal.
Source/contract transitions refuse with zero output, no retries. Sequence/instance
exhaustion cannot make old evidence valid. These are bounded observations, not
an atomic upstream TCPM snapshot, physical VBUS/current or a charging grant.
Linux7.2 tcpm_psy_get_prop is lockless; mirror matching and before/after generations
are required, not a claim that property reads acquire the TCPM port mutex.

Export a kernel-only read operation. Optional0400 debugfs current-port file calls
that same operation, no raw I2C, parser-only fake facts or writable activation.
Default Request guard still passes pps_authorized=false. No DTS/config/TCPM core,
SM5714 charge policy/SM5440/USB/roles/current/thermal changes.

Host actual-C tests cover property errors, missing provider, pending/change/fault,
source withdrawal, duplicate/rebound instances, trylock, references, removal
while reading and zeroed refusal. Build the existing passive profile, reused
config/DTB qualification. Then separately register one short read-only Test298:
PCUSB, one current-port read, device endpoint, exact263 rollback. Test297 is
OFFLINE qualification only; it is not PPS/direct hardware acceptance.

Vendor pd_check_vbat_work forcibly sets val.intval=0 before the switch-off branch;
sm5440_convert_adc refuses ordinary CHG-OFF beforeCHECK_VBAT; Fedora starts from
fuel-gauge eligibility then active initialization/continuous ADC. Record these
operating-condition differences; do not port the vendor's bypass or waive the
current ADC/OCP/PM prerequisites. Test29620ms did not resolve startup discrepancy.
