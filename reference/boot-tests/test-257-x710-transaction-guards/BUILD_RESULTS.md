# Test257 offline build results

Qualified source `31ca86caf0a9af23789f3da89113b9b06c069266`.
Linux7.2-rc3 a13c140c; LLVM21.1.8, ccache4.12.3, JOBS=8, BUILD_MODULES=1.
Both full ARM64 Image.gz/DTB/module builds passed. No device deployment.

| Artifact | Fixed default SHA-256 | Policy-offline SHA-256 |
| --- | --- | --- |
| Image.gz | bcd9304c301b235ce66578a8a357d7740c21ca5bd9382f23837c0cb1c8a83f03 | 609f0ad5a2152d38ba8597902e44f76e2b1bc44e3f87aea2584709346bde2c6f |
| sm8550-samsung-gts9wifi.dtb | c6148471113c5cb7589c64dee776e17b2fc20235cfeff4482616817a8b4e1c0b | 233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e |
| config | db85d66a2ce9c68b1bc060f637aac1f9b9259d24c3acd05878ca2ef1ce735e95 | 8dd8de24726ef8f185590066cfffdf03f42f2a7257fde96a2cfdbbdfa0788645 |
| kernel-notes.bin | bf482262d94553fb751ac159b2d0d8d50c3e1c99b85bcefccfa7faa4673093d8 | fc7541b417c6abee5fddfad94adebc014029de99cd1c785317cf032766f4dece |
| modules-x710.tar.gz | 467eb2d411f0e59c83c6859785b2fbb9df18516d3ee2f807b41477554079b793 | 13b2985281dc252c9168f2ebb6b8ebaf862ce369b02bb429eb207671bff6c9f4 |

Both profiles contain181 paired regular module-directory files,167 .ko files.
All module hashes are in validation/*-artifacts.json. Full resolved configurations,
notes and manifests are in validation/fixed and validation/policy. Exact Test255
configuration diffs are preserved as *.config.diff; comparison with Test256 finds
no config/DT change. Default artifacts are all byte-identical to Test256.

Builds run from immutable `.work/charging-source-257-code/scripts/build-kernel.sh`:

```sh
GTS9_WORKDIR="$PWD/.work" JOBS=8 USE_CCACHE=1 BUILD_MODULES=1 \
KERNEL_WORKTREE="$PWD/.work/build/linux-src-x710-charging" \
KERNEL_BUILD_DIR="$PWD/.work/build/linux-out-x710-charging" \
KERNEL_OUT_DIR="$PWD/out/kernel-x710-257-fixed" \
.work/charging-source-257-code/scripts/build-kernel.sh
```

Policy build adds GTS9_CHARGING_PROFILE=sm5440-policy-offline and uses its distinct
out/kernel-x710-257-policy output directory. This existing explicit profile compiles
the passive monitor and unused transaction core; it does not wire PPS/pump ON.

W=1/C=2 checked all four relevant drivers with actual sparse0.6.5-rc1; no driver
diagnostic, retained upstream VDSO declaration warning. Targeted SM5440 schema
and completed dtbs_check retain the known unbound PS5169 role-switch type error.
This is not a clean whole-board schema result. Logs are preserved.

No CPU/USB/charging policy changes. HVC_DCC=n, all85 container gates retained.
96 protected files and accepted Stage2 artifacts match. Actual protection and
ADC/sensors are unaccepted. **Active PPS/direct candidate: NOT READY.**
