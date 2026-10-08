# Test353 results

Added only ms and Debian-gdm to the existing render group, preserving other memberships and device-node modes. Ordinary-user Vulkan identified Turnip Adreno740; surfaceless EGL identified freedreno FD740. GNOME/Wayland ran for 60.055 seconds with no new kernel fault or render-permission/software-fallback signature. This is bounded functional bring-up, not a benchmark or reliability proof.

Owner reported “能登录并打开设置”, subsequently clarified “上轮可以输入密码进入”. Password login is confirmed. GDM was stopped and all three persistent masks restored at the registered endpoint. Touch remains unloaded.

The recorded Xwayland termination belongs to Debian-gdm UID103 at 6287.65s, during the greeter-to-user transition after ms login at 6285.09s; it is not the final 6330s GDM stop. The separate ms GNOME session obtained an accelerated EGL context and GDM remained active throughout the sampled window. Preserve these messages as a userspace follow-up; do not call them a kernel fault or silently remove them. Optional keyring/rtkit/ibus/bolt messages are also retained.

Raw archives and SHA identities are in render/ and gdm/. Test352's original partial result remains unchanged. Same Test331 boot/config/modules/DT/charging; no flash, reboot or PPS/pump activation. Test348 remains unused and paused.

Validation: evidence hashes and summary reviewed. Host suites and kernel build executed: false (no source/build-input change).
