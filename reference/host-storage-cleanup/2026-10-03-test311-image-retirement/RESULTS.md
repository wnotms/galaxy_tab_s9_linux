# Test311 window image retirement

Latest registered number: Test311; recent ten-round window: Test302–Test311.
Test300's historical Test263 rollback reference has expired. Seven image files
were deleted from out/, .work/build and Windows test300 staging after recording
size, SHA-256 and link count. The removed files total 376.718 MiB of logical
content; this is not a measured filesystem free-space increase. No expired image
was moved or archived. See manifest.json for the exact paths and original hashes.

Three unchanged vendor_boot/init_boot/dtbo files under the old Test263 bundle
remain solely because their exact hashes match the currently installed Test299
production partitions, as verified in Test310's final all-five readback. This
exception covers those three current running images, not the Test263 directory.
The old Test263 vbmeta does not match the installed image and was deleted.

Current Test299 production/rollback, qualified Test308 candidate, source, config,
DTB, modules, vmlinux, symbol CRC, generated headers and original evidence remain.
The old Test263 build Image/Image.gz are absent; preserved module-provider inputs
are not a complete incremental kernel cache. Historical paths remain evidence
of former files and must not be checked as currently existing images.

No device commands, build or host regression executed for this storage-only
change (`executed: false`). Review checked all seven deleted paths are absent.
