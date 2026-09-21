# Owner-supplied SM-X710 stock evidence

These hashes identify the artifacts inspected when this repository was initialized.

| Artifact | SHA-256 | Notes |
|---|---|---|
| live DTB | `9d645c1d0051f65d43f22bc16aa0ebd92b4e7f465f0465c61a43a79d7be80bf3` | FDT v17, 1,109,836 bytes |
| decompiled live DTS | `7bf40be5a9ededd23bf3c1725252fc28973be9b18b68e25fc5019502e03d723c` | model `Samsung GTS9WIFI PROJECT (board-id,04)` |
| stock kernel config | `80693a069d406fbdafe01b73e65e8f1e15b681451bbb53b9d05fde7a93220112` | Linux/arm64 5.15.153, Android clang 14.0.7 |

The raw files were supplied directly by the device owner and are treated as hardware evidence. They are intentionally not used as the Linux 7.2 mainline build config or as a drop-in mainline DTS.

## Key facts extracted from the live DTS

```text
model = Samsung GTS9WIFI PROJECT (board-id,04)
compatible = qcom,kalama-mtp / qcom,kalama / qcom,mtp
qcom,board-id = <0x10008 0x04>
qcom,msm-id = <0x218 0x20000 0x207 0x20000 0x207 0x10000 0x218 0x10000>
panel = GTS9_ANA38407_AMSA10FA01
touch = STM FTS1BA90A
pen = Wacom W90xx / WEZ01 family
WLAN/BT = QCA6490
SDHCI = 0x8804000
UFS = 0x1d84000
charger/fuel gauge/PD = SM5714
direct charger = SM5440
Type-C redriver = PS5169
eUSB2 repeater = PTN3222
speaker amps = 4 x CS35L45
```

## Stock config facts

```text
Linux/arm64 5.15.153
CONFIG_ARCH_QCOM=y
CONFIG_ARM64=y
CONFIG_MODULES=y
CONFIG_MODULE_SIG=y
CONFIG_BT_HCIUART=y
CONFIG_BT_HCIUART_QCA=y
CONFIG_INPUT_TOUCHSCREEN=y
CONFIG_SERIAL_QCOM_GENI=y
CONFIG_SERIAL_QCOM_GENI_CONSOLE=y
```

Use `scripts/audit-stock.sh` when a refreshed stock config/DTS is captured. If a future agent commits raw stock artifacts, put them under `reference/stock/raw/`, document their source/firmware build, and keep them out of the mainline build path.
