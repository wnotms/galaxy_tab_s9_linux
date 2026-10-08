# Native SoCinfo kernel candidate — offline preparation

Owner authorized kernel recompilation, and requested continued porting after
Test348. Test348's first non-clean evidence and restored Test331 acceptance
are committed/pushed at 3911e89f before new kernel inputs change.

Enable only CONFIG_QCOM_SOCINFO=y in the normal fragment and build assertion.
Existing QCOM_SMEM and SOC_BUS dependencies are already built-in. Use the
unchanged pinned Linux 7.2-rc3 driver; no SoC IDs or board values invented.
Do not change charging, PPS ceilings, USB, DTS, input sources or firmware.
QCOM_SOCINFO exposes native SoC/SMEM identity; it does not start ADSP.

Reuse the current sm5440-fedora profile's existing source/build directories,
JOBS=8 and shared ccache; preserve formal Test331/Test348 artifacts. Freeze
provider hashes before reuse and invalidate its old provider qualification.
Resolved config must differ from accepted Test331 only in QCOM_SOCINFO n→y;
DTB unchanged, DCC disabled and Docker/UPower/SM5714 retained. Build Image,
dtbs and all paired modules once; run affected tests and one full regression.

This is not a new charging test or device deployment. Candidate notes/config
will differ from Test331; existing exact-identity touch/pen loaders must not be
relaxed. Rebuild their accepted paired source against the new provider and
qualify hashes/CRCs in a separate offline step before any new desktop candidate
is deployed. Keep the currently restored Test331 device untouched.

Next physical scope must separately register fresh boot attribution, native
SoCinfo capture/mapping and controlled early signed ADSP firmware availability.
Do not late-start ADSP on the current tablet or install SSC during this build.
