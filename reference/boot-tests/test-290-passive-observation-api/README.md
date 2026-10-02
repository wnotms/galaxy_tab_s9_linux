# Test290 — offline passive observation API

Purpose: retain100ms fresh/active refusal contracts and add a distinct OFF-mode
kernel diagnostic observation with genuine acquisition/completion/delivery age.
Design: docs/SM5440_PASSIVE_OBSERVATION_API.md. Source baseline850f868d;
Test289 first refusal/raw remain immutable. No reinterpretation as timing pass.

Only passive driver/header, necessary host tests/documentation change. ADC sequence,
DTS/config, fixed5V<=1.8A/9V<=1.5A,4440mV/thermal, USB/adbd/rootfs and TCPM untouched.
No PPS or pumpON/current capability, live adapter, device command or deployment.
One settled build and final full host suite, with exact config/DT/protected audit;
results/status follow-up reuses qualification. Installed exact263 remains unchanged.
