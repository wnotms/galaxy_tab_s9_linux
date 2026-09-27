# Closed test246 host execution record

This records the completed restoration sequence; it is not a new trial command.
The Python call was run from the repository root with out/test246 on sys.path.
The archived runner sources are copied from those executed files. Afterward,
`python3 out/test246/check_transport.py` performed the final production check.
All underlying ADB calls, statuses and UTC timestamps are preserved in their
phase directories. The shell session finished with exit0.

```python
import control, modules, observe
assert target_verdict['verdict'] == 'clean_window'
control.recover('to-recovery')
control.poll('restore-poll', recovery=True, tries=10)
control.recovery_capture('twrp-restore')
modules.swap('module-restore', restore=True)
manifest = modules.push('module-cleanup', 'candidate-module-checksums.txt')
path = '/mnt/debian/usr/lib/modules/.gts9-test246-tested'
s, _ = control.shell(
    'module-cleanup', 'verified-remove',
    'test "$(find ' + path + ' -type f | wc -l)" -eq 181 && (cd ' + path +
    ' && sha256sum -c ' + manifest + ') && rm -rf -- ' + path +
    ' && test ! -e ' + path,
    serial=control.RECOVERY, timeout=25)
assert s.count(': OK') == 181
control.flash('restore', restore=True)
modules.reboot('production-reboot', 'restore', 'module-restore', restore=True)
observe.run(production=True)
```

`target_verdict` above is the parsed existing target-run/verdict.json. The
restoration operation did not start a second candidate target. The final audit
in validation/final_audit.py is offline and can be replayed without hardware.
