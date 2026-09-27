# Production rollout of the verified DCC-path repair

Test248 passed its single120 s diagnostic repair startup, including DCC driver/
node/getty absence and ADB/NCM SSH. The device remains on that candidate while
this production build is prepared; original and candidate rollback pairs exist.

Build the default mainline profile with the explicit HVC_DCC-off repair and NO
diagnostic fragment or patches0022/0024/0026. Retain the exact pin, DTB, default
production cmdline and initramfs. Compare config against the actual original
boot image's extracted IKCONFIG, not an assumed out-directory baseline. Explain
every difference; assert absence of DCC write code and temporary diagnostic
capabilities. Build/verify matched modules and full bundle before any writes.

Register TWO production startup targets,120 s each: TWRP-entry then one ordinary
warm reboot. Each needs immutable boot attribution, immediate source-time
capture, DCC/config/node/getty absence, matching module hashes/notes, detector
state and service/ADB/NCM SSH checks. Stop on first failure/suspect/unattributed
transition; no repeat budget. This is regression of the concrete removed path
and two boot paths, not a claim of zero future fault probability.

The final accepted state must be the production repair, with temporary
instrumentation removed and owned module staging/backup directories cleaned
only after verified external rollback copies exist. No SSH/USB configuration
change or getty mask. Preserve both original230 backups and the passing248
kernel/module rollback pair; prefer the passing DCC-disabled pair if rollout
recovery is needed. Paired image/module verification must precede any reboot.
No249 hardware target has run at registration. Deployment controller and final
recovery gates remain to be reviewed after the build and before hardware.
