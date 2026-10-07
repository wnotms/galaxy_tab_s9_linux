# Test336 expired-image retirement

Test336 is closed; the latest ten-round window is Test327–Test336.
Four exact-hash Test326 image files were retired after checking the current
327–336 package consumers and the qualified Test336 package. None was an
active consumer. Logical file sizes total 324,132,788 bytes (309.12 MiB),
including 192 MiB of Windows-stage images; this is not a measured filesystem
free-space increase.

Current Test331 accepted boot/modules, the accepted Test323 secondary provider
and qualified Test336 boot/Image/modules were retained. Test326 source/config,
DTB/modules, original journals/hashes and nonimage stage files remain. No
additional device action was performed for this cleanup.

`deletion-plan.json` records paths, pre-deletion hashes and consumers;
`summary.json` records completed removals. This is a result-only record:
host tests/build `executed: false`, unchanged qualification reused.
