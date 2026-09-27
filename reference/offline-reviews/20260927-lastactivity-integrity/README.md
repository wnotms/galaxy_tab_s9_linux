# Snapshot integrity validation

Four targeted decoder tests passed, including the corrupt test-231 fixture and
a structurally valid changed pointer. --reference now compares canonical marker
SHA-256. Invalid UTF-8 no longer causes an uncaught traceback.

All scripts/*.sh, scripts/lib/*.sh and boot/*.sh passed individual bash -n.
BUILD_MODULES=0 USE_CCACHE=1 ARCH=arm64 LLVM=1 KERNEL_OUT_DIR=out/kernel-lastactivity-evidence ./scripts/build-kernel.sh passed.
The build is the default production profile, not a new flashed diagnostic.
Build hashes are in evidence-build.txt. No full regression was needed.
