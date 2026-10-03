# SM5440 OFF park and native PPS resume

Terminal actuator stop restores original fields and inhibits later ON. It
cannot be used as a pause for the existing transaction core's PPS refresh or
retarget. This extension supplies that distinct register lifecycle; it is still
offline/unlinked, has no actual PPS caller, worker or charging activation.

[FEDORA ab123e7d] `sm5440_renegotiate_pps()` parks CNTL5 mode OFF, negotiates
through native TCPM properties, verifies physical VBUS settled and returns to
CHG_ON. It keeps prepared settings and the enabled watchdog across the park.
We retain that sequence and add exact readback/ownership/error checks, rather
than resetting chip/protections or adopting continuous ADC data as fresh.
[MAINLINE pinned7.2-rc3] property setters execute an AMS and await completion.
Our TCPC permits PPS Request only during its owned `pps_operation_active`,
with matching source/lease/target and the SM5714 switching inhibit checked.
Uncontrolled PPS requests remain refused; TCPM remains protocol-policy owner.

Caller drains the active monitor/ADC before park. `pause()` requires admitted
ON, matching generation, verified prepared settings/WDT and ADC enable clear.
It records the old budget generation and native start before the actual OFF
write; verifies OFF/live health while retaining settings/ENHIZ/watchdog ownership.
It does not authorize a PDO write. A pending/foreign conversion, status fault,
clock/cancellation or expired service budget invokes terminal stop once,
preserving the first error. An uncertain first park-OFF write/readback instead
latches terminal failure with OFF unverified and watchdog/settings retained;
neither this helper nor a later stop issues a hidden second OFF. No register
wait or cross-device lock.

After the existing native owned PPS API returns, `resume()` requires same
instance/source/lease and a **new** budget generation from the real producer;
the native source snapshot must begin after park. The producer ticks on each
budget callback, including unchanged PPS refresh. Capability labels on fixed
ONLINE1, old generation/snapshot, changed attach/APDO or malformed receipt are
refused. All original pack/OCP/APDO/physical100ms/current/facts gates apply;
zero OFF IBUS and real VBUS within100mV are mandatory, acquired at or after the
new native PPS completion. An earlier sample remains refused even if its age
is below100ms and the refreshed voltage is unchanged. The OFF park and watchdog
age each remain <=the existing1s software service budget; this is not a new
analog watchdog/current protection qualification.

An unchanged target keeps original settings. Retarget may alter voltage only
within8.2–10.5V and **reduce** current within1.0–1.8A; it cannot increase current.
Under verified OFF, update only the previously owned IBUS/frequency fields with
exact readback, retaining original cleanup bytes. Full prepared-field/witness
validation follows. Float/regulation stays4440mV requested/rounded-down encoding;
no margin/protection/thermal change. Then actual CHG_ON is written/read back and
generation/freshness rechecked. New physical post-ON monitoring is mandatory;
successful register resume alone is not direct-charge acceptance.

Each park has one resume attempt. Failure is terminal, never a second resume
or hidden retry. Successful park/resume cycles can repeat with advancing budget
generations; sequence overflow stops. The serialized owner supplies a fresh
supervisor instance after successful resume, based on the new post-ON guard
clock; it must not restamp/reuse an old ADC or restart a terminated monitor.
Active100ms deadlines still apply while ON. Terminal cancel/PM/unbind/fault
always uses full checked stop, not park.

No changes to current316/317 kernel, TCPM/TCPC, SM5714, DTS, rootfs, USB or
fixed5V1.8A/fixed9V1.5A. No Image relink, device PPS/pump operation or hardware
acceptance. Real sensor/current/cutoff qualification and native live integration
remain required; `software_ocp_verified` has no accepted device producer.
