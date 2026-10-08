# Historical parser comparison correction

The first retained71-test run had two failures: Test346 and Test347 asserted that
their frozen copied parser body equals the current live parser. The new1200s
allowlist intentionally changes that live body. Historical guardians, inputs,
results and activation limits must not be modified to make this assertion pass.

The tests now obtain the exact historical parser Git object at
ac893e2d667f83b58c5fc8a37abe6e1f6f38fa0d, verify its complete SHA-256 against each
round's INPUTS.json, and retain the original full-body equality assertion against
that parser. Both historical guardians explicitly reject a1200s witness. Current
parser compatibility is separately tested by replaying real Test345 and Test347
PASS and Test344 STOP evidence at their own expected duration.

The initial failure log is retained compressed. An intermediate attempt used the
kernel-only5c90 revision, which precedes parser creation; its missing-file errors
are also retained. The corrected71-test run passed in0.670s. No deleted/skipped
or weakened safety test, historical manifest rewrite, or device command.
