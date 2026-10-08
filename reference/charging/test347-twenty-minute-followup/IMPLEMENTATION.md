# Immutable1200s duration implementation

Kernel changes are limited to one duration constant, boot-parameter description,
and the existing exclusive one-shot allowlist. DefaultOFF/30000ms and300000ms
remain; only explicit exclusive once=1 permits1200000ms. The same single absolute
deadline is allocated once. No poll/refresh/current/voltage/register/thermal/PM/
source/lease/fallback algorithm changes. The reusable pure parser recognizes
1200000ms only when explicitly passed as the expected duration; historical
Test347/346 guardians and manifests are untouched and still bind300000ms.

96 affected tests passed in0.901s:85 actual-C tests (79 retained+6 new full1200s
and late-stop cases) and11 duration-parser tests (8 retained+3 new). Actual Test345
and Test347 PASS histories remain valid at their own duration; actual Test344 STOP
remains a failure. No tests skipped/removed or hardware operation performed.

Build/static/embedded-config/DT/module qualification still pending at this commit.
The device remains TWRP with restored Test331; no1200s physical registration or
authorization exists yet. Full charging port NOT_READY.
