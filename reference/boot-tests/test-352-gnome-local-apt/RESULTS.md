# Test352 — GNOME installed and visible; render access correction pending

368new Debian packages and three GPU firmware files installed successfully.
Exact versions and pre-existing package identities checked. Temporary service
policy restored; GDM masks retained. Kernel/config/DT/modules/charging unchanged.
Root Vulkan query identifies Turnip Adreno740/Mesa25.0.7. This is initialization/
identity evidence, not a performance or rendering benchmark.

One60.045s GDM observation completed on the same331boot; owner confirmed normal
graphical login. A user GNOME Wayland session also appeared in raw logs.
No new kernel fault or reboot; GDM stopped and remasked at the registered end.
Ordinary user ms and Debian-gdm lack render-group membership. renderD128 is
0660 root:render; Mutter reports permission denied and software framebuffer
sharing. Therefore hardware-accelerated desktop is **not accepted** yet.

Next correction is userspace group membership and one ordinary-user renderer/
GNOME check, preserving original partial result. Touch remains unloaded. No
kernel rebuild/full suite (executed:false);29affected tests passed, including
realAPT local-deb simulation. Test348one1200s grant still unused/finalTWRP intact.
Raw installation/GPU/GDM archives and their hashes are retained here.
