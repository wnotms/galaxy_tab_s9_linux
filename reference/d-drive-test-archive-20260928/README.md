# D-drive test artifact migration (2026-09-28)

Moved 639 historical test files (about 20 GiB) from `D:\android` and the
top-level `D:\gts9-*` test paths into this repository's local
`.work/d-drive-test-archive/2026-09-28/`. Original relative paths are
preserved beneath that directory, and the tracked `SHA256SUMS` records every
archived file. Before removal, a read-only `rsync -aicn` comparison found no
source/destination file differences. Only after that check did
`rsync --remove-source-files` remove the D-drive originals; empty historical
test directories were removed. The archive is intentionally outside Git
because it contains many complete boot images, modules and duplicate logs.

For a later integrity check, run from the archive root:

```sh
sha256sum -c /home/ms/Samsung/galaxy_tab_s9_linux/reference/d-drive-test-archive-20260928/SHA256SUMS
```

Windows retains only the operational paths under `D:\android`:

* `platform-tools/` for Windows ADB;
* `gts9-stock/` for stock rescue images;
* `gts9-test230/` with the original `backup-boot.img` and
  `backup-vendor_boot.img`;
* `gts9-test248/` with the passing diagnostic DCC-disabled rollback pair
  and matching module archive;
* `gts9-test249/` with the staged production pair, module archive and
  `rollback/` copies of the passing248 images.

Those five nonempty top-level directories hold 39 files, about 1.3 GiB.
Historical logs and images are no longer required on Windows. The live test249
runner refers to the retained Windows paths recorded in
`reference/boot-tests/test-249-no-dcc-production/backup-and-staging.json`.
