#!/usr/bin/env bash
set -euo pipefail

config=${1:?usage: audit-stock.sh STOCK_CONFIG LIVE_DTS}
dts=${2:?usage: audit-stock.sh STOCK_CONFIG LIVE_DTS}

for f in "$config" "$dts"; do
    [ -f "$f" ] || { echo "missing file: $f" >&2; exit 1; }
done

echo '=== SHA-256 ==='
sha256sum "$config" "$dts"

echo
echo '=== stock kernel config ==='
grep -E '^# Linux/arm64|^CONFIG_CC_VERSION_TEXT=|^CONFIG_ARCH_QCOM=|^CONFIG_ARM64=|^CONFIG_MODULES=|^CONFIG_MODULE_SIG=|^CONFIG_SERIAL_QCOM_GENI(_CONSOLE)?=|^CONFIG_BT_HCIUART(_QCA)?=' "$config" || true

echo
echo '=== board selectors ==='
grep -m1 -E '^[[:space:]]*model[[:space:]]*=' "$dts" || true
grep -m1 -E '^[[:space:]]*compatible[[:space:]]*=' "$dts" || true
grep -m1 -E '^[[:space:]]*qcom,msm-id[[:space:]]*=' "$dts" || true
grep -m1 -E '^[[:space:]]*qcom,board-id[[:space:]]*=' "$dts" || true

echo
echo '=== device hints ==='
grep -niE 'ANA38407|AMSA10FA01|fts1ba90a|wacom@|qca6490|sm5714|sm5440|ps5169|ptn3222|cs35l45|sdhci@8804000|ufshc@1d84000' "$dts" | head -n 120 || true
