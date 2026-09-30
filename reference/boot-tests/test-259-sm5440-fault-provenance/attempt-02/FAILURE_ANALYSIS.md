# First-fault analysis

New boot08af1c86643545918043f69d36d93807. Probe revision2 on0-0063 at1.673735s.
First source fault1.676898s, software bitmap0x80=REVBLK only (not prior0x82):

    INT=00 00 62 00 STATUS=00 00 20 00
    INT4-disable=00 INT4-wait=01 mode=01/01
    CNTL2=f2 VBUSCNTL=e7 VBATCNTL=37 PRTNCNTL=fe
    ADC=18 18 7a e0 00 00 5d 38 0c 76 20
    VBUS=4867000uV VBAT=3938000uV IBUS=0uA die=285 deciC

Mode fieldCNTL5[3:2] is0 at both boundaries; raw01 is NOT pumpON. REVBLK is
in the PRE-conversion read-to-clear INT3, not live STATUS3. INT3 also carries
UVLO/VBUSPOK indications; liveSTATUS3 onlyVBUSPOK. ADC completion is newly
observed, not a timeout; full raw sample agrees with vendor arithmetic. This
proves provenance separation works. It does not prove when/why the old latch
was set, independent ADC calibration, or benign origin of Test258 VBAT_OVP.

Samsung sm5440_irq_thread logs REVBLK but reports forced charge cutoff only
when direct state>PRESET and opmodeOFF. This is evidence that context matters,
not authority to ignore all inactive faults. Keep current conservative stop.
CNTL2/PRTNCNTL readf2/fe match vendor aggregate init values, whose software OCP
requirement remains unresolved; port did not write them. VBATCNTL low6bits55
encodes4487.5mV nominal (vendor integer getter4487), not an assumed3800mV
reset. VBUSCNTL low3bits7 maps vendor11V protection. These inherited settings
are NOT accepted active protection and are NOT changed to obtain a pass.
SM5714 switching float4440mV and5/9V current caps remain separate/unmodified.

First NCM SSH identity command failedstatus255 with TCP timeout. ADB responds,
usb0 has169.254.42.1, ssh/adbd/USB servicesactive, Sink/Device, WiFi address
10.191.121.103. No evidence supports CPU wedge attribution. Windows-side
failure remains unclassified; no USB/config repair or retry-to-clean. Full
ADB kernel JSON and supplies preserve this sameboot, config/notes identities.
Initial SSH could not assign boot, so rollback uses the independently agreeing
candidate-boot and freshADB boot identities; original null/error retained.

Immediate STOP, no clean samples/no150s pass, no PPS/pump/current/protection
change. ExactTest255 pair and181modules restored; allfive partitions readback
match. Test259 failed modules retained separately, Test258 tested slot retained.
Next requires separately registered passive startup-latch semantics audit plus
fresh rescue transport acceptance; no blanketfault whitelist/activeStage3.
