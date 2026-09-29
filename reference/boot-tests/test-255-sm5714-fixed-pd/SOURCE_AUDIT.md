# Prebuild Stage2 source audit

Reviewed before compilation,2026-09-29. [Machine audit](validation/prebuild-source-audit.json)
lists all21 TCPC functions (including the container helper) and21 register constants; [reference hashes](validation/reference-sources.json)
pin the actually read X710 sources. Fedora fetched origin/main equals audited
ab123e7d1dbc0cbcd35661f9761197e977b15aa9. No reference kernel-version bump or
Fedora advanced feature queue was imported.

TCPC callbacks init/get_vbus/get_current_limit/get_cc/set_cc/set_polarity/
set_vconn/set_vbus/set_current_limit/set_pd_rx/set_roles/pd_transmit use stock
struct tcpc_dev. TCPM7.2 registration mandates set_vconn/set_vbus/set_roles:
off-only/reject-Source/Sink-Device-only implementations satisfy that API. No
start_toggling/DRP, try_role, cable_comm, FRS, auto discharge or altmode callback.
Single-role Sink uses Rd directly. Polarity is read from CC_STATUS; no external
orientation hardware is operated. Registration graph exposes only USB2 data.
TCPM role-switch lookup is optional. Compiled-DTB review found an inherited
usb-role-switch flag from sm8550.dtsi. DWC3 peripheral mode does not register
that provider (core.c calls dwc3_drd_init only in OTG mode). The board deletes
the inherited flag, preventing permanent probe deferral. dr_mode remains
peripheral; no DWC3 source change or controller role switch is introduced.

## Register writes and sources

Samsung paths below are relative to local msm-kernel; source SHA pins are in
reference-sources.json. `typec.c` means drivers/usb/typec/sm/sm5714/sm5714_typec.c,
`typec.h` its matching include/linux header. Fedora means pinned
kernel/files/sm5714_usbpd.c. Numeric write values are exactly sourced; bit masks
select only documented fields. No parameter from another phone/X910 is used.

| Register/operation | Value/mask | Provenance and purpose |
| --- | --- | --- |
| CORR_CNTL5 0x24 / CORR_CNTL4 0x23 |0x00/0x00 | Fedora init; Samsung normal/init and release SBU water-detection sourcing. Does not claim full water detection |
| RX_BUF_ST0x5f |0x10 | Samsung protocol_layer_reset lines2104+; Fedora init, flush retained RX data |
| PD_CNTL4 0x3b after PD_STATE3 0xd8 &0x06 |0x01 | Samsung detach lines3638+ / Fedora init: **ResetDone acknowledgement**, not Samsung protocol-reset-bit3=0x08 |
| CC_CNTL5 0x2d |0x18 | Samsung set_vconn_source OFF lines288+ / Fedora callback; never enables VCONN |
| PD_CNTL2 0x39 |bits1:0 cleared, other bits preserved | Samsung set_ufp/set_snk lines199/217; Sink/UFP PD header roles only |
| CC_CNTL1 0x29 / CC_CNTL3 0x2b |0x45/0x82 | Samsung set_attach(TYPE_C_ATTACH_UFP) lines236+ / Fedora set_cc; force Rd/Sink |
| CC_CNTL3 |0x88 | Samsung force-detach bit3 / Fedora set_cc OPEN; no source/Rp value |
| INT_MASK1..5 0x06..0x0a |e6 cf ff08 ff; initial allff | Fedora masks / Samsung set_irq_enable. Unmask VBUS,attach/detach,Rp and transport only; masked before request |
| PD_CNTL1 0x38 |on0x08/off0x00 | Samsung set_pd_control lines3037+ / Fedora set_pd_rx; ordinary SOP receive |
| TX_HEADER0x60/TX_PAYLOAD0x62 |2-byte LE header / count*4 LE payload | Samsung write_msg_header/write_msg_obj / Fedora transmit; max header count7 |
| TX_REQ0x7e |0x07 only | Samsung typec.h MSG_SEND_TX_SOP_REQ and send_msg lines1998+ / Fedora transmit; no cable/DP SOP' |
| PD_CNTL4 hard reset |bit2=0x04 | Samsung hard_reset lines2640+ / Fedora transmit; HCRST_DONE completes TCPM TX |
| RX_BUF0x5e |0x80 | Samsung receive_message lines2694 / Fedora receive; acknowledge consumption even on partial read error |
| Charger VBUSCNTL0x15 |existing mask0x7f, max9V1500/5V1800 encoded by existing helper | Stage1/Samsung chg_set_input_current; added budget uses same unchanged register encoding |
| Charger CHGCNTL2/4, CNTL1 |existing2100/thermal500 current,4440 float, Q4 sequence | Stage1 accepted helper sequences unchanged; TCPM budget/charge/suspend/fault are additional gates |

Reads: INT1..5=0x01..05 (read-to-clear), STATUS1=0x0b VBUS_POK only (not ADC),
CC_STATUS=0x28 attach[2:0]/Rp[4:3]/flip[5], PD_STATE3=0xd8,
RX_SRC=0x41 low nibble0=SOP, RX_HEADER/PAYLOAD. All definitions match Samsung
typec.h and Fedora. Full original source is read, not only copied constants.

## Failure, concurrency and bounded policy

Transport mutex protects multi-register TX/RX/CC and source-PDO cache. TCPM
notifications queue events or complete TX without acquiring its state mutex;
IRQ does not call a synchronous TCPM state transition while holding that lock.
Any I2C error records a first-fault latch, inhibits switching charge and does
not automatically reset/retry. Failed level-low interrupt clearing disables
the IRQ to prevent a storm. IRQ starts disabled until a live registered port;
explicit pre-registration init handles TCPM ignoring init's return. Removal/
shutdown disables IRQ and joins resync before port teardown. Resync is a single
Fedora1.5s attach fallback, not a repeated reset/recovery loop.

Charger global companion lock pins lifetime through each callback; chg_lock
serializes contract/charge/fault/suspend and register programming. Unpublish
runs before devres frees supplies/state. No raw driver pointer escapes. Zero/
<100mA budget opens Q4 and lowers the input register to its100mA hardware
minimum. Q4 does not isolate all VSYS consumption: this is not zero VBUS draw.
Valid charging/standby budgets>=100mA are honored without rounding upward.
Stage2 charger probe is inhibited before TCPC claim, including a retained9V
startup; every early-return path first lowers the input cap. Pre-Q4 programming
uses min(500mA,budget), avoiding a brief500mA setting for a smaller grant. First fault
is not cleared by live rebind. Thermal poller also respects TCPM charge-off;
suspend flag is set before cancelling work so callbacks cannot restart charge.
Delayed BC1.2 classification can conservatively hold a default-Rp source at
500mA until another detection event; physical BC1.2/PD timing remains unverified.

Request validation checks actual source-PDO position/type/voltage/current. The
stock CAP_MISMATCH RDO can state a desired maximum above a weak source offer,
but operating current remains bounded by that source; desired maximum stays
within the approved sink cap. The guard respects this Linux/PD distinction;
it does not select/rewrite a PDO or import a policy framework. Both sink PDOs
are fixed, max9V; actual9V input<=1500mA(13.5W),5V<=1800mA and<=granted budget.
Pack charge cap2100mA and float4440mV unchanged. 100mA hardware minimum and25mA
steps are Stage1/vendor limits; below100mA is inhibited. Thermal warm/cold/hot
thresholds/hysteresis, mandatory pack thermistor and read/programming fail-safe
are retained. The existing optional SM5440 DT child is disabled and its TCPM
link removed; hub3/GPI controller setup is unchanged and no pump access occurs.

| Boundary | Result |
| --- | --- |
| TCPM core modified |false |
| DWC3 / gadget / FunctionFS / Test253 adbd modified |false |
| SM5440 driver or registers touched |false |
| PPS enabled / APDO requested |false |
| Max PD voltage |9V fixed |
| Max charger input at9V |1500mA |
| Float |4.44V unchanged |
| Thermal/suspend |Stage1 preserved, extra TCPM gates |
| Test254 config |must pass existing container gate and exact one-symbol delta |

Source review/host tests cannot prove electrical safety, correct chip timing,
measured VBUS or PC enumeration. GPIO/pin/PD initialization and charger->PC
reconnect need the future bounded Test255. Water detection, USB3 orientation,
suspend/resume PD continuity and dock roles are not accepted features.
