# X710 GNOME deployment bundle

This bundle is host-prepared only. It contains the exact Debian ARM64/all GNOME
packages, pinned X710 SQE/GMU/ZAP firmware and controlled installer. It does not
flash, reboot, start GNOME, enable charging or load touch automatically.

After the independently registered Test348 charging test closes, transfer the
tar to Debian and extract into a **new empty directory**, then:

```sh
cd gts9-gnome
sha256sum -c checksums.sha256
python3 tools/install.py packages.json --cache packages --firmware firmware
```

Those commands only validate files. Native device installation requires an
independent desktop stage and the explicit installer `--execute`, current
`--expected-boot-id` and new `--evidence` arguments. See the repository's
`userspace/gnome/README.md`; do not execute during the frozen charging test.
GDM remains persistently masked after installation until its controlled first
activation. Existing user `ms` is available; no root auto-login is configured.

`optional-touch/` contains the unmodified Fedora X710 FTS1BA90A module and its
offline qualification. Its provider is Test348, not an already accepted Test331
load. Do not copy it into the original 181-file module directory or force-load
it. Deployment needs exact provider/CRC checks and a separate bounded first
probe/touch test. The installer does not consume or load it. No S Pen driver,
touch firmware update, GPU driver replacement or automatic desktop start is
included.

GPU hardware acceleration, visible GNOME, touch coordinates, gestures and PM
remain untested. Package/firmware hashes and offline module compilation do not
prove those capabilities. Preserve working rescue and collect the first fault;
do not rebind display components or change charging as a desktop recovery step.

The tar is a temporary transfer artifact under WSL `out/`. Retire it after the
deployment is closed; keep source, manifests and results. Do not create another
Windows mirror or retain duplicate historical deployment archives.
