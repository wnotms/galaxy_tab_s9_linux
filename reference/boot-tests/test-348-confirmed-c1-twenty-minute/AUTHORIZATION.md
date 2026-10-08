# Test348 one-attempt execution authorization

Owner explicitly replied “允许执行 20 分钟测试” to the independently prepared
Test348 scope: one1200s PPS attempt, hardware1700mA/PPS+raw1800mA ceiling,
exact331 restoration and finalTWRP. See owner-physical-authorization.json.
Registration and scope flags now reflect that reply; old offline flags and
manifests are preserved in authorization-enrollment. No Test347 grant is reused.

This permits the registered baseline boot, staging, installation and one test,
not another activation after failure. Fresh current identity/rescue/battery
preflight and candidate-bound C1 reply remain required. Physical acceptance
is still pending. Full charging port remains NOT_READY.
