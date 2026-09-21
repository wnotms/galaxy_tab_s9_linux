# Owner-extracted stock kernel config

These five files are byte chunks of one Base64 string. Decoding the concatenated
string produces a deterministic `gzip -n -9` stream; decompressing it produces
the exact Samsung SM-X710 stock kernel config supplied by the device owner.

Do not edit the parts. Use:

```bash
./scripts/materialize-stock-config.sh /tmp/SM-X710-stock.config
```

Expected uncompressed SHA-256:

`80693a069d406fbdafe01b73e65e8f1e15b681451bbb53b9d05fde7a93220112`

Expected uncompressed size: 191,842 bytes.

This config is used as the Kconfig seed for the pinned mainline kernel. It is
not proof that every Samsung 5.15 symbol exists in Linux 7.2; `olddefconfig`
drops obsolete/private symbols and the mainline fragment asserts the required
upstream options.
