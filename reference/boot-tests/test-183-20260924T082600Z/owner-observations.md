# Owner observations during test-183

## 2026-09-24 ~10:13-10:17Z — a reboot that came up with only a cursor

Verbatim report (translated): "the previous reboot's screen had only a cursor,
keyboard input worked; this boot is normal, the one before it was the case
above."

What the round captures say about those two boots:

| round | boot (kick) | panel bring-up in the capture |
|---|---|---|
| 4 | 10:13:08Z | `panel id: 00 00 00` -> `first-enable zero panel ID recorded` -> `panel id: 80 00 04` -> `cycle 1 recovered panel ID 80 00 04` |
| 5 | 10:17:03Z | same sequence, twice in the window |

So the panel itself came up on both boots: the ANA38407 answered `80 00 04`,
which rules out the cold-boot panel-ID failure that `gts9-panel-recover` exists
to fix. What the owner saw - a black screen with a live text cursor and a
working keyboard - is therefore a **console repaint** problem on top of a
working display pipeline, i.e. the `drm_fb_helper_damage_work` / fbcon path
rather than DSI bring-up.

That distinction matters for the DPU work: the same damage-worker path is what
stops draining in a stall (`docs/DPU_TRACE.md`), and this is the first
observation of it failing *without* the whole system wedging - the machine
stayed usable, only the console content did not get painted.

No stall markers appear in either round's capture (`rpmh_write_batch`, soft
lockup, DPU timeouts: all zero), so this is a separate, less severe symptom.

Open question for the next session: whether the cursor-only screen correlates
with the fb0 blank/unblank cycle that `gts9-panel-recover` performs (which is a
full modeset), and whether a forced repaint (e.g. a VT switch) restores it.
