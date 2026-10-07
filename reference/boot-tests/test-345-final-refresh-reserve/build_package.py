#!/usr/bin/env python3
"""Package exact qualified kernel with sole one-shot opt-in; offline only."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
original=ROOT/'reference/charging/sm5440-fedora-port/build_package.py'
source=original.read_text().replace('QUALIFIED = R', "QUALIFIED = ROOT/'reference/charging/test344-refresh-deadline'")
source=source.replace('OFFLINE_FEDORA_PORT_PASS','OFFLINE_REFRESH_RESERVE_PASS')
source=source.replace('reference/boot-tests/test-323-pc-source-budget','reference/boot-tests/test-331-pps-fix-default-off')
source=source.replace('accepted Test323 source-authorized ordinary PC charging','accepted Test331 exact ordinary charging')
source=source.replace('out/boot-bundle-x710-fedora','out/boot-bundle-x710-refresh-reserve-on')
source=source.replace('UNREGISTERED_FEDORA_SOURCE_CANDIDATE','Test345')
source=source.replace("'--cmdline', ''", "'--cmdline', 'sm5440_fedora.direct_charge_once=1'")
source=source.replace('same-model Fedora SM5440/PPS source port; default direct charging off','One registered <=30s attempt: 1.7A hardware setpoint, unchanged PPS/raw 1.8A ceiling, no restart')
exec(compile(source,str(original),'exec'),globals())
