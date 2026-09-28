# Cmdline framing check correction

The first attempt02 capture hit a host observer assertion: the saved native
ADB shell capture is1157 bytes with final CRLF; current SSH is1156 with LF.
Replacing only CRLF with LF produces identical byte content. Every cmdline
argument is unchanged; this is a transport framing difference, not device
identity drift. Raw captures/failure are preserved. The observer now compares
only CRLF-normalized framing, with tests for equivalence and actual cmdline
changes. Fresh evidence goes into preflight-verified/, never overwrites the
first capture. No hardware write, restart or reboot occurred during this check.
