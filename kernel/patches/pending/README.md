# Patches held back from the default build

`prepare-kernel.sh` applies `kernel/patches/*.patch` and ignores subdirectories,
so anything in here is deliberately *not* applied.

## Why these two are here

Both come from the SM-X910 port (agcarbajo/ubuntu-galaxy-tab-s9-ultra) and both
address symptoms this board has:

- `qmp-ufs-clear-tx-pull-down-on-power-on.patch` — the bootloader leaves the UFS
  PHY with RX_INTERFACE_MODE bit 6 set, which pulls the TX lines down, so the
  link never trains.
- `snps-eusb2-match-samsung-sm8550-init.patch` — Samsung's eUSB2 init sequence,
  which the port needs before a host can read the gadget's descriptors.

They were applied for test 019 (boot 307207ce) together with the PDC config fix.
That test never reached its armed power-off, so it could not say whether they
helped or hurt, and the run had two independent changes in it.  Test 020 carries
the PDC fix alone: the microSD card and the RTC only need SPMI to work, and once
either of them can hold the report, the deferred-probe list and the regulator
summary will say what UFS is actually waiting for - which is better evidence
than another guess.  These two go back in one at a time afterwards.
