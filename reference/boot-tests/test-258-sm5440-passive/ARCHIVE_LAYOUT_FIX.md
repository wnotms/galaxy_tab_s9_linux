# Offline archive adapter after the stopped attempt

The immutable Test258 install/stop/result records are not rewritten. This fix
was prepared after stopping and was not pushed to or executed on the tablet.

build-kernel.sh produces a release-root modules archive. The inherited
module-swap.sh expected lib/modules/release. New module-swap-release-root.sh
normalizes extraction into stage/lib/modules, rejects other roots/traversal,
and retains the same181-file/hash/link/current-backup/rename/restore guards.
No driver/config/DTS/TCPM/gadget/adbd/current/thermal change or kernel rebuild.
The original sealed module-swap.sh and its staged Windows copy stay unchanged.

Focused host command:

```sh
sh -n reference/boot-tests/test-258-sm5440-passive/module-swap-release-root.sh
python3 -m unittest discover -s tests -p test_sm5440_module_staging.py
```

5 tests passed in2.671s, zero failures/errors/skips. The real qualified181-file
candidate archive installs into a temporary root, preserves its old181 files,
then restores the old pair and retains the tested candidate. Other tests refuse
legacy archive root, traversal, incomplete candidate and preexisting backup
before current-directory rename. The host fixture substitutes only sync to
avoid global WSL/Windows filesystem waits; deployed helper still uses real sync.
This validates file transactions, not physical flash/pump/ADC safety.

Kernel candidate source/artifacts still match f3a266b5 qualification. No repeated
full1264 run/build; the new5 focused checks are not represented as a new full1269
pass. Test routing and retained tests are unchanged.

Future deployment: register a fresh attempt, verify rescue (including resolving
the returned-baseline Wi-Fi reachability failure), select this helper explicitly
and seal its hash together with the same candidate/rollback files. Do not reuse
the old stopped install script unmodified or retry the old attempt. Existing
accepted Test255 remains installed; no new physical test is performed here.
