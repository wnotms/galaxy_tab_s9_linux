# These files are NOT device evidence

Everything in this directory is **synthetic**. These logs were hand-written to pin
the branches of `../classify-round.sh`, and the commit that added them says so
("Three synthetic fixtures pin the branches").

**test-186 has never been run on the device.** There is no `../rounds/` directory
and no capture exists. The monotonic timestamps in these files - `13.400000` and
`14.270000` in particular - appear nowhere else in this repository, because no
boot ever printed them.

This banner exists because three separate documents cited these files as real
hardware measurements:

* `docs/GPU_GMU_RPMH_STALL_PLAN.md` §4 (corrected in round 2),
* `docs/RPMH_RSC_DEBUG_PATCH_STATUS.md` §6 (corrected in round 28),
* `docs/RPMH_TIMEOUT_LIFETIME_ANALYSIS.md` §5 (corrected in round 29).

In each case the correction changed the conclusion, not just the citation: a
result that had been read as "observed and negative" was in fact never measured.
If you are about to cite a line from this directory, cite the branch it pins
instead, and run the test.
